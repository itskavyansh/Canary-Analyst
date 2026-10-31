import concurrent.futures
import json
import time
from pathlib import Path
import numpy as np

from engine.baseline_b2 import BaselineB2, B2_CONFIG
from eval.metrics import evaluate_scenario, compute_aggregate_metrics
from eval.run_eval import stream_scenario

def evaluate_single(item):
    proj, scen = item
    cfg = dict(B2_CONFIG)
    cfg["trend_projection_minutes"] = proj
    det = BaselineB2(cfg)
    alerts = stream_scenario(det, scen["rf"], scen["tf"])
    outcome = evaluate_scenario(alerts, scen["truth"])
    return proj, outcome

def main():
    scen_path = Path("data/scenarios")
    with open(scen_path / "index.json") as f: idx = json.load(f)

    scenarios = []
    for s in idx["scenarios"]:
        rf = scen_path / s["readings_file"]
        tf = scen_path / s["truth_file"]
        with open(tf) as f: truth = json.load(f)
        scenarios.append({"rf": rf, "tf": tf, "truth": truth})

    print("Evaluating projection values: [80, 90, 100] across worker pool...")
    tasks = []
    for proj in [80.0, 90.0, 100.0]:
        for s in scenarios:
            tasks.append((proj, s))

    results_by_proj = {80.0: [], 90.0: [], 100.0: []}
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:
        for proj, outcome in pool.map(evaluate_single, tasks, chunksize=25):
            results_by_proj[proj].append(outcome)

    summary = {}
    print("\n" + "=" * 70)
    print("PROJECTION SWEEP RESULTS (DEV Split, 300 Scenarios)")
    print("=" * 70)
    for proj in [80.0, 90.0, 100.0]:
        outcomes = results_by_proj[proj]
        agg = compute_aggregate_metrics(outcomes, seed=42)
        det_rate = agg["detection_rate"] * 100.0
        fa_rate = agg["false_alarm_rate"] * 100.0
        
        accel_outcomes = [o for o in outcomes if o.scenario_type == "accelerating_creep"]
        leads = [o.lead_time for o in accel_outcomes if o.lead_time is not None]
        med_lead = float(np.median(leads)) if leads else 0.0
        diff = 54.0 - med_lead

        print(f"trend_projection_minutes={int(proj)}: Detection={det_rate:.1f}%, FA={fa_rate:.1f}%, Median Lead={med_lead:.1f}m (Diff from B1: {diff:.1f}m)")
        summary[str(int(proj))] = {
            "trend_projection_minutes": proj,
            "detection_rate": det_rate,
            "false_alarm_rate": fa_rate,
            "median_lead_time": med_lead,
            "diff_from_b1": diff
        }

    Path("results").mkdir(exist_ok=True)
    with open("results/projection_sweep.json", "w") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    main()

