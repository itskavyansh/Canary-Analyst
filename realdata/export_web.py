"""Export real recording session for web demo.
Reads data/real/session_nov03.csv (or resampled scenario), layout, alerts, and agent output,
and writes web/public/demo/real_session.json and web/public/real_session.json.
"""
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

def main():
    root = Path(__file__).resolve().parent.parent
    
    # 1. Load layout
    layout_path = root / "data" / "real" / "session_nov03_layout.json"
    with open(layout_path, "r", encoding="utf-8") as f:
        node_coords = json.load(f)
    
    # 2. Load 1-minute scenario readings
    scenario_path = root / "results" / "real" / "nov03" / "scenario" / "REAL_nov03.jsonl"
    raw_readings = []
    with open(scenario_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_readings.append(json.loads(line))
                
    # Group readings by minute timestamp
    # Map UTC timestamp to IST (+05:30)
    ist_offset = timedelta(hours=5, minutes=30)
    
    by_time = {}
    for r in raw_readings:
        ts = r["timestamp"]
        if ts not in by_time:
            by_time[ts] = {}
        node_id = r["node_id"]
        # Compute tilt magnitude: sqrt(tilt_x^2 + tilt_y^2)
        tx = float(r.get("tilt_x", 0.0) or 0.0)
        ty = float(r.get("tilt_y", 0.0) or 0.0)
        tilt_mag = round(math.sqrt(tx*tx + ty*ty), 4)
        
        by_time[ts][node_id] = {
            "tilt_x": tx,
            "tilt_y": ty,
            "tilt_mag": tilt_mag,
            "vibration": float(r.get("vibration", 0.0) or 0.0),
            "distance": float(r.get("distance", 0.0) or 0.0),
            "piezo_peak": float(r.get("piezo_peak", 0.0) or 0.0),
            "piezo_rms": float(r.get("piezo_rms", 0.0) or 0.0),
            "mpu6050_status": r.get("mpu6050_status", "ok"),
            "hc_sr04_status": r.get("hc_sr04_status", "ok"),
            "ads1115_status": r.get("ads1115_status", "ok"),
        }
        
    sorted_times = sorted(by_time.keys())
    minute_series = []
    for idx, ts in enumerate(sorted_times):
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_ist = dt_utc + ist_offset
        time_ist_str = dt_ist.strftime("%H:%M")
        minute_series.append({
            "minute_index": idx,
            "timestamp_utc": ts,
            "timestamp_ist": time_ist_str,
            "is_baseline": idx < 30, # first 30 minutes (0 to 29)
            "nodes": by_time[ts]
        })
        
    # 3. Load alerts from B0, B1, B2
    def load_alerts(fname, source_name):
        fpath = root / "results" / "real" / "nov03" / fname
        res = []
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        al = json.loads(line)
                        dt_utc = datetime.fromisoformat(al["time"].replace("Z", "+00:00"))
                        dt_ist = dt_utc + ist_offset
                        res.append({
                            "source": source_name,
                            "time_utc": al["time"],
                            "time_ist": dt_ist.strftime("%H:%M"),
                            "level": al["level"],
                            "reason": al["reason"],
                            "node_ids": al["node_ids"]
                        })
        return res

    b0_alerts = load_alerts("alerts_b0.jsonl", "B0")
    b1_alerts = load_alerts("alerts_b1.jsonl", "B1")
    b2_alerts = load_alerts("alerts_b2.jsonl", "B2")
    
    # 4. Load agent decisions and transcript
    agent_decision = None
    dec_path = root / "results" / "real" / "nov03_agent" / "agent_decisions.jsonl"
    if dec_path.exists():
        with open(dec_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    agent_decision = json.loads(line)
                    break
                    
    transcript_info = None
    tr_path = root / "results" / "real" / "nov03_agent" / "transcripts.jsonl"
    if tr_path.exists():
        with open(tr_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    tr_obj = json.loads(line)
                    res = tr_obj.get("result", {})
                    parsed = res.get("parsed", {})
                    token_usage = res.get("token_usage", {})
                    cost_usd = res.get("cost_usd", 0.0)
                    evidence_store = res.get("evidence_store", {})
                    tool_calls_raw = res.get("tool_calls", [])
                    transcript_info = {
                        "parsed": parsed,
                        "token_usage": token_usage,
                        "cost_usd": cost_usd,
                        "evidence_store": evidence_store,
                        "tool_calls": tool_calls_raw
                    }
                    break

    # 5. Build disturbances info
    unlabelled_disturbances = [
        {
            "time_ist": "13:38",
            "time_utc": "08:08:00Z",
            "node_id": "NODE_02",
            "channel": "distance",
            "event": "Distance Step",
            "details": "Step from 3.92 cm to 5.20 cm (delta: +1.28 cm, or 1.29 cm relative to initial 3.91 cm).",
            "impact": "Did not exceed 3.0 cm threshold, so no baseline alert triggered."
        },
        {
            "time_ist": "13:52",
            "time_utc": "08:22:00Z",
            "node_id": "NODE_01",
            "channel": "distance & piezo_peak",
            "event": "Distance Jump & Piezo Spike",
            "details": "Distance stepped from 42.82 cm to 38.16 cm (delta: -4.66 cm). Simultaneously, piezo acoustic peak spiked to 0.5569 V (baseline mean ~0.0176 V).",
            "impact": "Triggered persistent distance check at end of 30-min baseline window (13:56 IST / 08:26 UTC) across B0, B1, and B2."
        },
        {
            "time_ist": "14:03",
            "time_utc": "08:33:00Z",
            "node_id": "NODE_01 & NODE_02",
            "channel": "vibration",
            "event": "Synchronous Vibration Excursion",
            "details": "Vibration peaked simultaneously on both nodes (0.131 g on NODE_01, 0.127 g on NODE_02).",
            "impact": "Both peaks remain well below the 1.0 g blast/impact threshold, so no shock alert was raised."
        }
    ]

    # Step 5 explanation
    step5_explanation = {
        "finding": "Agent reported NODE_02 moved 0.29 cm, whereas raw data showed a 1.28-1.29 cm step at 13:38 IST.",
        "cause": "The compare_neighbor_nodes tool calculates each node's baseline using the first 30 minutes of available data (07:58Z to 08:26Z / 13:28 to 13:56 IST). Because NODE_02 stepped at 13:38 IST (minute 10), 20 out of 30 baseline readings were already at the post-step ~5.20 cm value, contaminating the reference baseline median to 4.89 cm.",
        "verdict": "The agent faithfully reported the tool output, but the tool window includes post-step readings, rendering the 0.29 cm value inconsistent with the true 1.28 cm step."
    }

    payload = {
        "title": "2-Node Prototype Real Recording",
        "session_id": "REAL_nov03",
        "recorded_date": "2026-11-03",
        "duration_minutes": 37,
        "baseline_window_minutes": 30,
        "disclaimer": "Real 2-node prototype recording, 37 minutes, one session. No ground truth labels were given to any detector. This is a demonstration, not a benchmark. Alert time reflects the end of the 30 minute baseline window, not the time of the physical change. Thresholds are demonstration values.",
        "fail_closed_note": "With 2 nodes the neighbour gates are inert, so KEEP here is fail-closed behaviour.",
        "node_coordinates_m": node_coords,
        "unlabelled_disturbances": unlabelled_disturbances,
        "step5_explanation": step5_explanation,
        "alerts": {
            "b0": b0_alerts,
            "b1": b1_alerts,
            "b2": b2_alerts
        },
        "agent_decision": agent_decision,
        "transcript": transcript_info,
        "minute_series": minute_series
    }

    # Write to web/public/demo/real_session.json and web/public/real_session.json
    out1 = root / "web" / "public" / "demo" / "real_session.json"
    out2 = root / "web" / "public" / "real_session.json"
    
    with open(out1, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {out1} ({out1.stat().st_size} bytes)")

    with open(out2, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {out2} ({out2.stat().st_size} bytes)")

if __name__ == "__main__":
    main()

