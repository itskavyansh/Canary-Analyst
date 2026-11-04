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

def format_compact_summary(tool_name: str, res: Dict[str, Any]) -> str:
    """Format 2 to 4 key numbers per tool from the actual tool JSON."""
    if not isinstance(res, dict) or not res:
        return "No data recorded"

    if tool_name == "get_sensor_health":
        flags = res.get("status_flags", {})
        flag_summary = "ok" if all(v == "ok" for v in flags.values()) else ",".join([f"{k}:{v}" for k, v in flags.items() if v != "ok"])
        noise_ratio = res.get("noise_ratio_versus_profile", 0.0)
        max_step_tilt = res.get("max_step_change_tilt_deg", 0.0)
        healthy = res.get("is_healthy", True)
        return f"healthy={healthy}, flags={flag_summary}, noise_ratio={noise_ratio:.2f}x, step_tilt={max_step_tilt:.2f}°"

    elif tool_name == "compare_neighbor_nodes":
        ch = res.get("channel", "tilt")
        pnc = res.get("per_node_change", {})
        changes_str = " ".join([f"{k}:{v:.2f}" for k, v in pnc.items()])
        strongest = res.get("strongest_node", "N/A")
        decay = res.get("amplitude_decays_with_distance", False)
        return f"channel={ch}, changes=[{changes_str}], strongest={strongest}, spatial_decay={decay}"

    elif tool_name == "get_node_history":
        nid = res.get("node_id", "")
        ch = res.get("channel", "")
        peak = res.get("peak_value", 0.0)
        slope = res.get("slope_per_min", 0.0)
        baseline_std = res.get("baseline_noise_std", 0.0)
        returned = res.get("returned_to_baseline", False)
        unit = "°" if ch == "tilt" else "g" if ch == "vibration" else "cm" if ch == "distance" else "V"
        return f"node={nid}, peak={peak:.3f}{unit}, slope={slope:.4f}/m, base_std={baseline_std:.3f}, returned={returned}"

    elif tool_name == "project_time_to_threshold":
        nid = res.get("node_id", "")
        ch = res.get("channel", "")
        slope = res.get("slope_per_minute", 0.0)
        t_stat = res.get("t_statistic_adjusted", res.get("t_statistic", 0.0))
        r2 = res.get("r_squared", 0.0)
        mins = res.get("minutes_to_threshold")
        mins_str = f"{mins:.1f}m" if mins is not None else "never"
        return f"node={nid}, slope={slope:.4f}/m, t_adj={t_stat:.2f}, R²={r2:.2f}, eta={mins_str}"

    elif tool_name == "check_blast_schedule":
        sched = res.get("blast_scheduled_within_30min", False)
        mins_since = res.get("time_since_last_scheduled_blast_min")
        mins_str = f"{mins_since:.0f}m ago" if mins_since is not None else "none"
        nearby = len(res.get("nearby_blasts", []))
        return f"scheduled_±30m={sched}, last_blast={mins_str}, nearby_blasts={nearby}"

    # Generic fallback
    items = [f"{k}={v}" for k, v in res.items() if not k.startswith("ev_") and isinstance(v, (int, float, str, bool))][:3]
    return ", ".join(items)


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
                for tc_idx, tc in enumerate(analyst_res.tool_calls):
                    fname = tc.get("function", {}).get("name", "unknown")
                    fargs = tc.get("function", {}).get("arguments", "{}")
                    try:
                        parsed_args = json.loads(fargs) if isinstance(fargs, str) else fargs
                    except Exception:
                        parsed_args = {}

                    # Match result by numbered key or function name
                    res_obj = t_results.get(f"{fname}_{tc_idx + 1}")
                    if not res_obj:
                        res_obj = t_results.get(fname, {})
                    if not res_obj:
                        # find by tool field
                        for _, v in t_results.items():
                            if isinstance(v, dict) and v.get("tool") == fname:
                                res_obj = v
                                break

                    ev_id = res_obj.get("evidence_id", "") if isinstance(res_obj, dict) else ""
                    summary_text = format_compact_summary(fname, res_obj)

                    steps.append({
                        "as_of": parsed_args.get("as_of", dec["timestamp"]),
                        "tool_name": fname,
                        "arguments": parsed_args,
                        "result_summary": summary_text,
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

        # Ground truth reveal
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

    # Compile demo/summary.json (clean text with no raw LaTeX math tokens)
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
            "test_total_usd": 2.85577,
            "test_mean_usd": 0.02147,
            "test_candidates": 133,
            "test_mean_tokens": 17668.3,
            "test_mean_latency_sec": 15.48,
            "evidence_validity_rate": 100.0
        },
        "limitations": [
            "Silent sensor faults remain unresolved (12 of 43 test scenarios still alarm; 128 of 139 baseline alarm-minutes come from silent sensor faults).",
            "Simulated data from physics-inspired mathematical models rather than raw underground mine seismic records.",
            "Noise profiles informed by prototype test sensor readings (data/real_readings.csv).",
            "Sensor noise was measured on prototype bench logs sampled about once per second, then applied to simulated 1-minute readings, and the generator caps noise levels (distance 0.35 cm, tilt 0.20 degrees, vibration 0.015 g), so simulated noise is an approximation. The generator has no temperature drift, which real tiltmeters show.",
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
