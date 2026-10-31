"""Export script to package scenario replay data and summary metrics for the static web demo.

Outputs to web/public/demo/:
- demo/index.json
- demo/summary.json
- demo/<scenario_id>.json (4 selected scenarios)
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from agent.analyst import Analyst
from agent.detector_agent import AgentDetector
from agent.guard import SafetyGuard
from engine.baseline_b2 import BaselineB2
from generator.run_dev_agent_eval import stream_scenario_eval

def main():
    print("=" * 70)
    print("Canary Analyst: Export Demo Scenarios and Benchmark Summaries")
    print("=" * 70)

    out_dir = Path("web/public/demo")
    out_dir.mkdir(parents=True, exist_ok=True)

    scen_path = Path("data/scenarios_test")
    with open(scen_path / "index.json", "r", encoding="utf-8") as f:
        all_test_scenarios = json.load(f)["scenarios"]

    # 4 Selected scenarios shuffled with fixed seed=5 so creep scenarios are not first:
    # 1. SCENARIO_0054_rain_tilt (Criterion C: rain_tilt false alarm cleared by AGENT)
    # 2. SCENARIO_0056_sensor_fault (Criterion B: sensor fault alert where guard vetoed downgrade for safety)
    # 3. SCENARIO_0005_accelerating_creep (Criterion D: ordinary accelerating creep detection, lead time 52 min)
    # 4. SCENARIO_0029_accelerating_creep (Criterion A: creep + blast overlay, KEEP ground_movement, lead time 57 min)
    selected_scenarios = [
        ("SCENARIO_0054_rain_tilt", "Array 1", "C"),
        ("SCENARIO_0056_sensor_fault", "Array 2", "B"),
        ("SCENARIO_0005_accelerating_creep", "Array 3", "D"),
        ("SCENARIO_0029_accelerating_creep", "Array 4", "A")
    ]

    subtitle_common = "Monitoring chunk, 4 nodes, 6 hours"

    shared_analyst = Analyst(budget_usd=20.0)
    shared_guard = SafetyGuard()

    exported_index = []

    for sid, neutral_title, criterion_tag in selected_scenarios:
        scen_meta = next(s for s in all_test_scenarios if s["scenario_id"] == sid)
        rf = scen_path / scen_meta["readings_file"]
        tf = scen_path / scen_meta["truth_file"]

        with open(tf, "r", encoding="utf-8") as f:
            truth = json.load(f)

        # Run B2.1
        b2 = BaselineB2()
        b2_alerts, _, _ = stream_scenario_eval(b2, rf, tf)

        # Run AGENT
        agent_det = AgentDetector(analyst=shared_analyst, guard=shared_guard)
        agent_alerts, _, det_instance = stream_scenario_eval(agent_det, rf, tf)

        # Read full readings (all 1-min timesteps, 4 nodes)
        readings_by_ts: Dict[str, Dict[str, Any]] = {}
        with open(rf, "r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                ts = r["timestamp"]
                nid = r["node_id"]
                if ts not in readings_by_ts:
                    readings_by_ts[ts] = {"timestamp": ts, "nodes": {}}
                readings_by_ts[ts]["nodes"][nid] = {
                    "tilt_x": round(r["tilt_x"], 3),
                    "tilt_y": round(r["tilt_y"], 3),
                    "vibration": round(r["vibration"], 3),
                    "distance": round(r["distance"], 3),
                    "mpu6050_status": r.get("mpu6050_status", "ok"),
                    "hc_sr04_status": r.get("hc_sr04_status", "ok"),
                    "ads1115_status": r.get("ads1115_status", "ok"),
                    "piezo_peak": round(r.get("piezo_peak", 0.0), 3)
                }

        readings_list = [readings_by_ts[k] for k in sorted(readings_by_ts.keys())]

        # Extract B2.1 alerts
        b2_alerts_export = [
            {
                "time": a.time,
                "level": a.level,
                "node_ids": a.node_ids,
                "reason": a.reason
            }
            for a in b2_alerts
        ]

        # Extract AGENT alerts + review holds
        agent_alerts_export = [
            {
                "time": a.time,
                "level": a.level,
                "node_ids": a.node_ids,
                "reason": a.reason
            }
            for a in agent_alerts
        ]

        # Extract hold resolutions
        hold_resolutions_export = [
            {
                "episode_id": r.episode_id,
                "outcome": r.outcome,
                "reason": r.reason
            }
            for r in det_instance.hold_manager.hold_resolutions_log
        ]

        # Extract investigations
        investigations_export = []
        for dec in det_instance.decisions_log:
            analyst_res = dec["analyst_result"]
            guard_dec = dec["guard_decision"]
            ep_id = dec["episode_id"]

            steps = []
            if analyst_res:
                t_results = analyst_res.tool_results or {}
                for tc in analyst_res.tool_calls:
                    fname = tc.get("function", {}).get("name", "unknown")
                    fargs = tc.get("function", {}).get("arguments", "{}")
                    try:
                        parsed_args = json.loads(fargs) if isinstance(fargs, str) else fargs
                    except Exception:
                        parsed_args = {}

                    res_obj = t_results.get(fname, {})
                    ev_id = res_obj.get("evidence_id", "") if isinstance(res_obj, dict) else ""
                    steps.append({
                        "as_of": parsed_args.get("as_of", dec["timestamp"]),
                        "tool_name": fname,
                        "arguments": parsed_args,
                        "result_summary": res_obj,
                        "evidence_id": ev_id
                    })

            inv_data = {
                "episode_id": ep_id,
                "timestamp": dec["timestamp"],
                "steps": steps,
                "final_structured_result": analyst_res.parsed if analyst_res else {},
                "guard_verdict": {
                    "action": guard_dec.action,
                    "reason": guard_dec.reason,
                    "approved": guard_dec.action == "DOWNGRADE",
                    "failed_conditions": guard_dec.failed_conditions
                },
                "cost_usd": analyst_res.cost_usd if analyst_res else 0.0,
                "latency_sec": analyst_res.latency_sec if analyst_res else 0.0
            }
            investigations_export.append(inv_data)

        # Ground truth reveal: strictly quarantined so UI only reveals it on user completion
        reveal_data = {
            "scenario_type": truth["type"],
            "is_hazard": truth["is_hazard"],
            "onset_time": truth.get("onset_time"),
            "collapse_time": truth.get("collapse_time"),
            "events": truth.get("events", []),
            "b2_detected": any(a.level in ("WARNING", "CRITICAL") for a in b2_alerts) if truth["is_hazard"] else None,
            "b2_false_alarm": any(a.level in ("WARNING", "CRITICAL") for a in b2_alerts) if not truth["is_hazard"] else False,
            "agent_detected": any(a.level in ("WARNING", "CRITICAL") for a in agent_alerts) if truth["is_hazard"] else None,
            "agent_false_alarm": any(a.level in ("WARNING", "CRITICAL") for a in agent_alerts) if not truth["is_hazard"] else False
        }

        scenario_doc = {
            "scenario_id": sid,
            "title": neutral_title,
            "subtitle": subtitle_common,
            "criterion_tag": criterion_tag,
            "node_coordinates_m": truth.get("node_coordinates_m", {}),
            "blast_schedule": truth.get("blast_schedule", []),
            "readings": readings_list,
            "b2_alerts": b2_alerts_export,
            "agent_alerts": agent_alerts_export,
            "hold_resolutions": hold_resolutions_export,
            "investigations": investigations_export,
            "reveal": reveal_data
        }

        with open(out_dir / f"{sid}.json", "w", encoding="utf-8") as f:
            json.dump(scenario_doc, f, indent=2)

        exported_index.append({
            "scenario_id": sid,
            "title": neutral_title,
            "subtitle": subtitle_common,
            "criterion_tag": criterion_tag,
            "file": f"{sid}.json"
        })
        print(f"  [Exported] {sid} -> {neutral_title}")

    # Write demo/index.json
    with open(out_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump({"scenarios": exported_index}, f, indent=2)
    print("  [Exported] demo/index.json")

    # Load test and dev summaries
    with open("results/test_final/summary.json", "r", encoding="utf-8") as f:
        test_summary = json.load(f)

    with open("results/agent_v1/summary.json", "r", encoding="utf-8") as f:
        dev_summary = json.load(f)

    # Compile demo/summary.json
    summary_doc = {
        "dev_metrics": dev_summary["detectors"],
        "test_metrics": test_summary["detectors"],
        "paired_comparison": {
            "non_hazard_removed": 8,
            "non_hazard_added": 0,
            "non_hazard_both": 15,
            "non_hazard_neither": 191,
            "p_value": 0.0078125,
            "all_removed": 8,
            "all_added": 0,
            "all_both": 16,
            "all_neither": 276
        },
        "hold_outcomes": {
            "REEMITTED_BY_CRITICAL": {"hazard": 0, "non_hazard": 0},
            "REEMITTED_BY_WORSENING": {"hazard": 0, "non_hazard": 0},
            "REEMITTED_BY_TIMEOUT_PERSISTENCE": {"hazard": 0, "non_hazard": 0},
            "CLEARED": {"hazard": 0, "non_hazard": 8}
        },
        "alarm_minutes": {
            "blast": {"B2.1": 4.0, "AGENT": 1.0, "scenarios_B2": 4, "scenarios_AGENT": 1},
            "machinery_impact": {"B2.1": 1.0, "AGENT": 0.0, "scenarios_B2": 1, "scenarios_AGENT": 0},
            "rain_tilt": {"B2.1": 4.0, "AGENT": 1.0, "scenarios_B2": 4, "scenarios_AGENT": 1},
            "sensor_fault": {"B2.1": 128.0, "AGENT": 12.0, "scenarios_B2": 12, "scenarios_AGENT": 12},
            "stuck_sensor": {"B2.1": 2.0, "AGENT": 1.0, "scenarios_B2": 2, "scenarios_AGENT": 1}
        },
        "ablation": [
            {"tier": "B0", "name": "Raw Instantaneous Thresholds", "test_fa_rate": 40.0, "test_lead_time": 10.0, "failure_mode": "Single transient spikes trigger false alarms; missed early creep."},
            {"tier": "B1", "name": "Stateful Persistence (3/5) + OLS Trend", "test_fa_rate": 39.3, "test_lead_time": 57.0, "failure_mode": "High early sensitivity, but high false alarms from rain and ultrasonic rail jumps."},
            {"tier": "B2.1", "name": "Engineered Rules Baseline", "test_fa_rate": 8.0, "test_lead_time": 52.0, "failure_mode": "Common-mode rain rejection and rail-jump suppression filter spurious noise drift."},
            {"tier": "AGENT", "name": "Muse Spark 1.3 + Guard + 15m Review Hold", "test_fa_rate": 5.3, "test_lead_time": 52.0, "failure_mode": "Multi-tool investigation disambiguates complex multi-channel context, removing 8 false alarms with 0 added."}
        ],
        "costs": {
            "test_total_usd": 2.99488,
            "test_mean_usd": 0.02109,
            "test_candidates": 142,
            "test_mean_tokens": 17676.0,
            "test_mean_latency_sec": 15.33,
            "evidence_validity_rate": 100.0
        },
        "limitations": [
            "Silent sensor faults remain unresolved (12 of 43 test scenarios still alarm; 128 of 139 baseline alarm-minutes come from silent sensor faults).",
            "Simulated data from physics-inspired mathematical models rather than raw underground mine seismic records.",
            "Noise profiles calibrated against prototype bench sensor readings (data/real_readings.csv).",
            "Synthetic hazard profiles follow continuous deterministic acceleration; real collapse dynamics can feature brittle stick-slip behavior.",
            "Thresholds (15 deg, 2.0 cm, 1.0 g) are engineering demonstration values requiring site-specific geotechnical tuning."
        ]
    }

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_doc, f, indent=2)
    print("  [Exported] demo/summary.json")

    print("\n[SUCCESS] Export complete.")

if __name__ == "__main__":
    main()
