import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Type

from engine.common import Alert, Detector
from engine.baseline_b0 import BaselineB0
from engine.baseline_b1 import BaselineB1
from engine.baseline_b2 import BaselineB2
from agent.detector_agent import AgentDetector
from eval.metrics import ScenarioOutcome, compute_aggregate_metrics, evaluate_scenario

# Detector registry: easily extensible for AGENT and others
DETECTOR_REGISTRY: Dict[str, Type[Detector]] = {
    "B0": BaselineB0,
    "B1": BaselineB1,
    "B2": BaselineB2,
    "AGENT": AgentDetector,
}


def register_detector(name: str, detector_cls: Type[Detector]) -> None:
    """Register a new detector into the evaluation registry."""
    DETECTOR_REGISTRY[name] = detector_cls


def stream_scenario(
    detector: Detector,
    readings_file: Path,
    truth_file: Path
) -> List[Alert]:
    """Streams a scenario through the detector under the strict no-lookahead rule."""
    with open(truth_file, "r", encoding="utf-8") as f:
        truth = json.load(f)

    # Sanitize scenario_meta: NEVER expose ground truth fields
    meta = {
        "scenario_id": truth["scenario_id"],
        "node_coordinates_m": truth.get("node_coordinates_m", {}),
        "blast_schedule": truth.get("blast_schedule", [])
    }
    detector.reset(meta)

    # Read readings and sort by timestamp
    all_readings = []
    with open(readings_file, "r", encoding="utf-8") as f:
        for line in f:
            all_readings.append(json.loads(line))

    # Group strictly by timestamp
    by_time: Dict[str, Dict[str, Any]] = {}
    for r in all_readings:
        ts = r["timestamp"]
        if ts not in by_time:
            by_time[ts] = {}
        by_time[ts][r["node_id"]] = r

    # Feed in strictly chronological order, one timestep at a time
    alerts: List[Alert] = []
    for ts in sorted(by_time.keys()):
        step_readings = by_time[ts]
        step_alerts = detector.update(ts, step_readings)
        if step_alerts:
            alerts.extend(step_alerts)

    return alerts


def run_evaluation(
    detector_names: List[str],
    scenarios_dir: str,
    out_dir: str,
    seed: int = 42
) -> Dict[str, Any]:
    scen_path = Path(scenarios_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(scen_path / "index.json", "r", encoding="utf-8") as f:
        index_data = json.load(f)

    scenarios = index_data["scenarios"]
    summary: Dict[str, Any] = {"detectors": {}}

    for name in detector_names:
        if name not in DETECTOR_REGISTRY:
            raise ValueError(f"Unknown detector '{name}'. Registered: {list(DETECTOR_REGISTRY.keys())}")

        det_cls = DETECTOR_REGISTRY[name]
        detector = det_cls()

        outcomes: List[ScenarioOutcome] = []
        per_scenario_file = out_path / f"per_scenario_{name}.jsonl"

        scen_count = 0
        total_scens = len(scenarios)

        with open(per_scenario_file, "w", encoding="utf-8") as out_f:
            for scen in scenarios:
                rf = scen_path / scen["readings_file"]
                tf = scen_path / scen["truth_file"]

                with open(tf, "r", encoding="utf-8") as f:
                    truth = json.load(f)

                alerts = stream_scenario(detector, rf, tf)
                outcome = evaluate_scenario(alerts, truth)
                outcomes.append(outcome)

                rec = {
                    "scenario_id": outcome.scenario_id,
                    "type": outcome.scenario_type,
                    "is_hazard": outcome.is_hazard,
                    "false_alarm": outcome.false_alarm,
                    "detected": outcome.detected,
                    "time_to_detect": outcome.time_to_detect,
                    "lead_time": outcome.lead_time,
                    "detected_before_collapse": outcome.detected_before_collapse,
                    "total_episodes": outcome.total_episodes,
                    "alert_count": len(alerts)
                }
                out_f.write(json.dumps(rec) + "\n")

                scen_count += 1
                if name == "AGENT":
                    if hasattr(detector, "analyst"):
                        spent = detector.analyst.total_cost_spent
                        cands = len(detector.candidate_history)
                        if scen_count % 10 == 0 or scen_count == total_scens:
                            print(f"[AGENT progress] scenarios: {scen_count}/{total_scens}, candidates: {cands}, USD spent: ${spent:.4f}", flush=True)

        # Compute aggregate metrics overall and per type
        overall_metrics = compute_aggregate_metrics(outcomes, seed=seed)

        type_metrics: Dict[str, Any] = {}
        for stype in sorted(list(set(o.scenario_type for o in outcomes))):
            type_outcomes = [o for o in outcomes if o.scenario_type == stype]
            type_metrics[stype] = compute_aggregate_metrics(type_outcomes, seed=seed)

        summary["detectors"][name] = {
            "overall": overall_metrics,
            "by_type": type_metrics
        }

    # Save summary.json
    with open(out_path / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Print markdown results table
    print_markdown_table(summary, detector_names)

    return summary


def print_markdown_table(summary: Dict[str, Any], detector_names: List[str]):
    # Extract all scenario types
    sample_det = detector_names[0]
    types = list(summary["detectors"][sample_det]["by_type"].keys())

    print("\n" + "=" * 110)
    print("CANARY ANALYST: BASELINE EVALUATION REPORT (300 Scenarios)")
    print("=" * 110)

    header = f"| Scenario Type | Metric | " + " | ".join([f"{d}" for d in detector_names]) + " |"
    sep = "|---|---|" + "|".join(["---" for _ in detector_names]) + "|"
    print(header)
    print(sep)

    for stype in types:
        # False alarm rate
        fa_row = f"| **{stype}** | False Alarm Rate | "
        for d in detector_names:
            m = summary["detectors"][d]["by_type"][stype]
            rate = m["false_alarm_rate"] * 100
            ci = (m["false_alarm_ci"][0] * 100, m["false_alarm_ci"][1] * 100)
            fa_row += f"{rate:.1f}% [{ci[0]:.1f}, {ci[1]:.1f}] | "
        print(fa_row)

        # Detection rate if hazard
        m0 = summary["detectors"][sample_det]["by_type"][stype]
        if m0["detection_rate"] is not None:
            det_row = f"| | Detection Rate | "
            for d in detector_names:
                m = summary["detectors"][d]["by_type"][stype]
                rate = m["detection_rate"] * 100
                ci = (m["detection_ci"][0] * 100, m["detection_ci"][1] * 100)
                det_row += f"{rate:.1f}% [{ci[0]:.1f}, {ci[1]:.1f}] | "
            print(det_row)

            # Lead time if accelerating_creep
            if stype == "accelerating_creep":
                lead_row = f"| | Median Lead Time | "
                for d in detector_names:
                    m = summary["detectors"][d]["by_type"][stype]
                    lead = m["median_lead_time_min"]
                    ci = m["lead_time_ci"]
                    lead_row += f"{lead:.1f}m [{ci[0]:.1f}, {ci[1]:.1f}] | " if lead is not None else "N/A | "
                print(lead_row)

        # Mean episodes
        ep_row = f"| | Mean Episodes | "
        for d in detector_names:
            m = summary["detectors"][d]["by_type"][stype]
            ep = m["mean_alert_episodes"]
            ep_row += f"{ep:.2f} | "
        print(ep_row)

    # Overall Summary
    print("|---|---|---|" + "|".join(["---" for _ in detector_names]) + "|")
    overall_fa = "| **OVERALL** | False Alarm Rate | "
    for d in detector_names:
        m = summary["detectors"][d]["overall"]
        rate = m["false_alarm_rate"] * 100
        ci = (m["false_alarm_ci"][0] * 100, m["false_alarm_ci"][1] * 100)
        overall_fa += f"{rate:.1f}% [{ci[0]:.1f}, {ci[1]:.1f}] | "
    print(overall_fa)

    overall_det = "| | Detection Rate (Hazards) | "
    for d in detector_names:
        m = summary["detectors"][d]["overall"]
        rate = m["detection_rate"] * 100
        ci = (m["detection_ci"][0] * 100, m["detection_ci"][1] * 100)
        overall_det += f"{rate:.1f}% [{ci[0]:.1f}, {ci[1]:.1f}] | "
    print(overall_det)

    overall_ep = "| | Mean Episodes / Scenario | "
    for d in detector_names:
        m = summary["detectors"][d]["overall"]
        ep = m["mean_alert_episodes"]
        overall_ep += f"{ep:.2f} | "
    print(overall_ep)
    print("=" * 110 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run Canary Analyst evaluation harness.")
    parser.add_argument("--detectors", type=str, default="B0,B1", help="Comma-separated detector names")
    parser.add_argument("--split", type=str, default="dev", choices=["dev", "test"], help="Dataset split to evaluate: dev or test")
    parser.add_argument("--final", action="store_true", help="Confirmation flag required to run on the held-out test split")
    parser.add_argument("--scenarios", type=str, default=None, help="Explicit path to scenarios directory (overrides --split)")
    parser.add_argument("--out", type=str, default="results", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Seed for bootstrap confidence intervals")

    args = parser.parse_args()
    if args.split == "test" and not args.final:
        raise ValueError("Running on held-out test split requires explicit '--final' flag to prevent leakage.")

    if args.scenarios is not None:
        scenarios_dir = args.scenarios
    else:
        scenarios_dir = "data/scenarios_test" if args.split == "test" else "data/scenarios"

    detector_list = [d.strip() for d in args.detectors.split(",") if d.strip()]
    run_evaluation(detector_list, scenarios_dir, args.out, seed=args.seed)


if __name__ == "__main__":
    main()

