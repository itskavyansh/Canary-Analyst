import argparse
import concurrent.futures
from datetime import datetime
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from agent.analyst import Analyst
from agent.detector_agent import AgentDetector
from agent.guard import SafetyGuard
from engine.baseline_b0 import BaselineB0
from engine.baseline_b1 import BaselineB1
from engine.baseline_b2 import BaselineB2
from engine.common import Alert, Detector
from eval.metrics import ScenarioOutcome, compute_aggregate_metrics, evaluate_scenario

DETECTOR_REGISTRY = {
    "B0": BaselineB0,
    "B1": BaselineB1,
    "B2": BaselineB2,
    "AGENT": AgentDetector,
}


def stream_scenario_eval(
    detector: Detector,
    rf: Path,
    tf: Path
) -> Tuple[List[Alert], Dict[str, Any], Any]:
    with open(tf, "r", encoding="utf-8") as f:
        truth = json.load(f)

    meta = {
        "scenario_id": truth["scenario_id"],
        "node_coordinates_m": truth.get("node_coordinates_m", {}),
        "blast_schedule": truth.get("blast_schedule", [])
    }
    detector.reset(meta)

    all_readings = []
    with open(rf, "r", encoding="utf-8") as f:
        for line in f:
            all_readings.append(json.loads(line))

    by_time: Dict[str, Dict[str, Any]] = {}
    for r in all_readings:
        ts = r["timestamp"]
        if ts not in by_time:
            by_time[ts] = {}
        by_time[ts][r["node_id"]] = r

    alerts: List[Alert] = []
    for ts in sorted(by_time.keys()):
        step_alerts = detector.update(ts, by_time[ts])
        if step_alerts:
            alerts.extend(step_alerts)

    return alerts, truth, detector


def run_full_dev_evaluation():
    print("=" * 80)
    print("CANARY ANALYST: FULL DEV EVALUATION (300 SCENARIOS)")
    print("Detectors: B2 (Frozen Rules Baseline) vs AGENT (Muse Spark 1.3 + Guard)")
    print("=" * 80)

    scen_path = Path("data/scenarios")
    with open(scen_path / "index.json", "r") as f:
        idx = json.load(f)
    scenarios = idx["scenarios"]

    # Shared analyst with thread-safe disk cache
    shared_analyst = Analyst(budget_usd=20.0)
    shared_guard = SafetyGuard()

    # Worker function for parallel execution across scenarios
    def evaluate_one_scenario(scen_info):
        rf = scen_path / scen_info["readings_file"]
        tf = scen_path / scen_info["truth_file"]
        agent_det = AgentDetector(analyst=shared_analyst, guard=shared_guard)
        alerts, truth, det_instance = stream_scenario_eval(agent_det, rf, tf)
        outcome = evaluate_scenario(alerts, truth)
        return outcome, det_instance.decisions_log, det_instance.candidate_history

    print(f"Executing 300 scenarios across 4 worker threads...")
    start_t = time.time()
    all_outcomes: List[ScenarioOutcome] = []
    all_decisions: List[Dict[str, Any]] = []
    all_candidates: List[Any] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(evaluate_one_scenario, s): s for s in scenarios}
        done_count = 0
        for fut in concurrent.futures.as_completed(futures):
            outcome, dec_log, cand_hist = fut.result()
            all_outcomes.append(outcome)
            all_decisions.extend(dec_log)
            all_candidates.extend(cand_hist)
            done_count += 1
            if done_count % 30 == 0 or done_count == len(scenarios):
                print(f"  [{done_count:03d}/300] scenarios evaluated ({time.time()-start_t:.1f}s)")

    # Sort outcomes by scenario_id for determinism
    all_outcomes.sort(key=lambda o: o.scenario_id)

    # Load B2 outcomes for direct comparison
    b2_records = []
    b2_file = Path("results/per_scenario_B2.jsonl")
    if b2_file.exists():
        with open(b2_file, "r") as f:
            for line in f:
                b2_records.append(json.loads(line))

    # Compute aggregate metrics for AGENT
    agent_overall = compute_aggregate_metrics(all_outcomes, seed=42)
    types = sorted(list(set(o.scenario_type for o in all_outcomes)))
    agent_by_type = {}
    for stype in types:
        t_outcomes = [o for o in all_outcomes if o.scenario_type == stype]
        agent_by_type[stype] = compute_aggregate_metrics(t_outcomes, seed=42)

    # 1. Held candidates split into hazard vs non-hazard
    hazard_candidates_held = 0
    non_hazard_candidates_held = 0
    total_candidates_evaluated = len(all_decisions)

    # Truth lookup by scenario_id
    truth_by_scen = {}
    for s in scenarios:
        with open(scen_path / s["truth_file"]) as f:
            t = json.load(f)
            truth_by_scen[t["scenario_id"]] = t

    # 2. Guard rejection counts by reason
    guard_rejection_counts = {}

    # 3. Hypothesis confusion matrix against true scenario type
    hypotheses_classes = [
        "blast", "machinery_impact", "environmental_tilt", "sensor_fault",
        "sensor_stuck", "ground_movement", "unclear"
    ]
    confusion_matrix = {st: {h: 0 for h in hypotheses_classes} for st in types}

    # 4. Evidence validity rate
    total_cited_evidence_ids = 0
    valid_cited_evidence_ids = 0

    # 5. Usage metrics
    total_cost_usd = 0.0
    total_tokens = 0
    total_tool_calls = 0
    total_latency_sec = 0.0

    for item in all_decisions:
        ep_id = item["episode_id"]
        scen_id = ep_id.split("_")[0] + "_" + ep_id.split("_")[1] + "_" + ep_id.split("_")[2] if "_" in ep_id else ep_id
        # extract base scenario ID
        for sid in truth_by_scen:
            if ep_id.startswith(sid):
                scen_id = sid
                break

        truth = truth_by_scen.get(scen_id, {})
        is_haz = truth.get("is_hazard", False)
        true_type = truth.get("type", "unknown")

        guard_dec = item["guard_decision"]
        analyst_res = item["analyst_result"]

        if guard_dec.action == "DOWNGRADE":
            if is_haz:
                hazard_candidates_held += 1
            else:
                non_hazard_candidates_held += 1
        else:
            if guard_dec.failed_conditions:
                for cond in guard_dec.failed_conditions:
                    cond_name = cond.split(":")[0]
                    guard_rejection_counts[cond_name] = guard_rejection_counts.get(cond_name, 0) + 1

        if analyst_res and analyst_res.parsed:
            hyp = analyst_res.parsed.get("hypothesis", "unclear")
            if true_type in confusion_matrix and hyp in confusion_matrix[true_type]:
                confusion_matrix[true_type][hyp] += 1

            # Evidence validity
            cited = analyst_res.parsed.get("cited_evidence_ids", [])
            total_cited_evidence_ids += len(cited)
            known_ids = set()
            for k, v in analyst_res.tool_results.items():
                if isinstance(v, dict) and v.get("evidence_id"):
                    known_ids.add(v.get("evidence_id"))
            valid_cited_evidence_ids += sum(1 for c in cited if c in known_ids)

            total_cost_usd += analyst_res.cost_usd
            total_tokens += analyst_res.token_usage.get("total_tokens", 0)
            total_tool_calls += len(analyst_res.tool_calls)
            total_latency_sec += analyst_res.latency_sec

    n_cand = max(1, total_candidates_evaluated)
    evidence_validity_rate = (valid_cited_evidence_ids / max(1, total_cited_evidence_ids)) * 100.0

    # Save summary json
    results_summary = {
        "hazard_candidates_held": hazard_candidates_held,
        "non_hazard_candidates_held": non_hazard_candidates_held,
        "total_candidates": total_candidates_evaluated,
        "guard_rejections": guard_rejection_counts,
        "confusion_matrix": confusion_matrix,
        "evidence_validity_rate": evidence_validity_rate,
        "total_cost_usd": total_cost_usd,
        "mean_cost_per_candidate": total_cost_usd / n_cand,
        "mean_tokens_per_candidate": total_tokens / n_cand,
        "mean_tool_calls_per_candidate": total_tool_calls / n_cand,
        "mean_seconds_per_candidate": total_latency_sec / n_cand,
        "overall": agent_overall,
        "by_type": agent_by_type
    }

    with open("results/agent_eval_summary.json", "w") as f:
        json.dump(results_summary, f, indent=2)

    # Save per scenario jsonl
    with open("results/per_scenario_AGENT.jsonl", "w") as f:
        for o in all_outcomes:
            f.write(json.dumps({
                "scenario_id": o.scenario_id,
                "type": o.scenario_type,
                "is_hazard": o.is_hazard,
                "false_alarm": o.false_alarm,
                "detected": o.detected,
                "time_to_detect": o.time_to_detect,
                "lead_time": o.lead_time,
                "total_episodes": o.total_episodes
            }) + "\n")

    print("\n" + "=" * 80)
    print("FULL DEV EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Candidate Episodes Intercepted: {total_candidates_evaluated}")
    print(f"Hazard Candidates Held (SAFETY MANDATE - MUST BE 0): {hazard_candidates_held}")
    print(f"Non-Hazard Candidates Held (Benign Downgrades): {non_hazard_candidates_held}")
    print(f"Evidence Validity Rate: {evidence_validity_rate:.1f}% ({valid_cited_evidence_ids}/{total_cited_evidence_ids})")
    print(f"Total API Cost: ${total_cost_usd:.4f} (Mean: ${total_cost_usd/n_cand:.4f}/cand)")
    print(f"Mean Tokens / Candidate: {total_tokens/n_cand:.0f}")
    print(f"Mean Tool Calls / Candidate: {total_tool_calls/n_cand:.2f}")
    print(f"Mean Latency / Candidate: {total_latency_sec/n_cand:.2f}s")
    print(f"Overall Hazard Detection Rate: {agent_overall['detection_rate']*100:.1f}%")
    print(f"Overall False Alarm Rate: {agent_overall['false_alarm_rate']*100:.1f}%")
    print("=" * 80)

if __name__ == "__main__":
    run_full_dev_evaluation()

