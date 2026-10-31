from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pytest

from engine.common import Alert, Detector
from engine.baseline_b0 import BaselineB0
from engine.baseline_b1 import BaselineB1
from eval.metrics import bootstrap_ci, evaluate_scenario, group_alert_episodes
from eval.run_eval import stream_scenario


class SpyDetector(Detector):
    """Spy detector to audit data leakage and time violations."""
    def __init__(self):
        self.received_meta: Dict[str, Any] = {}
        self.call_history: List[Tuple[str, List[str]]] = []

    def reset(self, scenario_meta: Dict[str, Any]) -> None:
        self.received_meta = scenario_meta
        self.call_history = []

    def update(self, timestamp: str, readings_by_node: Dict[str, Any]) -> List[Alert]:
        self.call_history.append((timestamp, sorted(list(readings_by_node.keys()))))
        return []


def test_harness_no_lookahead_and_no_ground_truth_leak():
    """Verify harness never exposes future rows or ground truth fields to detectors."""
    spy = SpyDetector()
    rf = Path("data/scenarios/SCENARIO_0000_blast.jsonl")
    tf = Path("data/scenarios/SCENARIO_0000_blast_truth.json")

    # If file not present, find first scenario from index
    if not rf.exists():
        with open("data/scenarios/index.json") as f:
            idx = json.load(f)
        rf = Path("data/scenarios") / idx["scenarios"][0]["readings_file"]
        tf = Path("data/scenarios") / idx["scenarios"][0]["truth_file"]

    stream_scenario(spy, rf, tf)

    # 1. Verify no ground truth leaked into scenario_meta
    forbidden_keys = {"type", "is_hazard", "onset_time", "collapse_time", "events", "simulated"}
    for k in forbidden_keys:
        assert k not in spy.received_meta, f"Ground truth key '{k}' was leaked in scenario_meta!"

    # 2. Verify strictly monotonically increasing timestamps fed into update()
    timestamps = [call[0] for call in spy.call_history]
    assert len(timestamps) == 360  # 360 timesteps (1 per minute for 6 hours)
    for i in range(1, len(timestamps)):
        t_prev = datetime.fromisoformat(timestamps[i - 1].replace("Z", "+00:00"))
        t_curr = datetime.fromisoformat(timestamps[i].replace("Z", "+00:00"))
        assert t_curr > t_prev, f"Non-increasing time violation: {timestamps[i-1]} -> {timestamps[i]}"


def test_b0_alerts_on_single_spike_and_b1_does_not_critical():
    """B0 must alert on a synthetic single-spike reading, while B1 does not trigger CRITICAL on it."""
    b0 = BaselineB0()
    b1 = BaselineB1()

    meta = {"scenario_id": "SPIKE_TEST", "node_coordinates_m": {}}
    b0.reset(meta)
    b1.reset(meta)

    # Feed 30 baseline readings
    base_time = datetime(2026, 10, 27, 8, 0, 0)
    for i in range(30):
        ts = (base_time + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        readings = {
            "NODE_01": {
                "node_id": "NODE_01",
                "timestamp": ts,
                "tilt_x": 0.0,
                "tilt_y": 0.0,
                "vibration": 0.05,
                "distance": 18.0,
                "mpu6050_status": "ok",
                "hc_sr04_status": "ok",
                "ads1115_status": "ok"
            }
        }
        b0.update(ts, readings)
        b1.update(ts, readings)

    # Single spike at minute 31: vibration = 2.0g (exceeds critical threshold 1.5g)
    spike_ts = (base_time + timedelta(minutes=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
    spike_readings = {
        "NODE_01": {
            "node_id": "NODE_01",
            "timestamp": spike_ts,
            "tilt_x": 0.0,
            "tilt_y": 0.0,
            "vibration": 2.0,
            "distance": 18.0,
            "mpu6050_status": "ok",
            "hc_sr04_status": "ok",
            "ads1115_status": "ok"
        }
    }

    alerts_b0 = b0.update(spike_ts, spike_readings)
    alerts_b1 = b1.update(spike_ts, spike_readings)

    # B0 should trigger an immediate alert on the single spike
    assert len(alerts_b0) == 1
    assert alerts_b0[0].level == "CRITICAL"

    # B1 persistence rule requires 3 of last 5 readings to exceed threshold,
    # so a single isolated spike cannot trigger CRITICAL
    crit_b1 = [a for a in alerts_b1 if a.level == "CRITICAL"]
    assert len(crit_b1) == 0


def test_metrics_on_handcrafted_scenarios():
    """Verify metrics calculation on tiny hand-crafted examples."""
    # Example 1: Known False Alarm on non-hazard
    truth_non_hazard = {
        "scenario_id": "SCEN_NH_01",
        "type": "rain_tilt",
        "is_hazard": False
    }
    alerts_fa = [
        Alert("SCEN_NH_01", "2026-10-27T08:45:00Z", ["NODE_01"], "WARNING", "test", "B0")
    ]
    outcome_fa = evaluate_scenario(alerts_fa, truth_non_hazard)
    assert outcome_fa.false_alarm is True
    assert outcome_fa.total_episodes == 1
    assert outcome_fa.detected is False

    # Example 2: Known Miss on hazard
    truth_hazard_miss = {
        "scenario_id": "SCEN_H_MISS",
        "type": "slow_creep",
        "is_hazard": True,
        "onset_time": "2026-10-27T09:00:00Z"
    }
    outcome_miss = evaluate_scenario([], truth_hazard_miss)
    assert outcome_miss.false_alarm is False
    assert outcome_miss.detected is False
    assert outcome_miss.time_to_detect is None

    # Example 3: Known Lead Time on accelerating_creep
    truth_accel = {
        "scenario_id": "SCEN_ACCEL_01",
        "type": "accelerating_creep",
        "is_hazard": True,
        "onset_time": "2026-10-27T09:00:00Z",
        "collapse_time": "2026-10-27T11:00:00Z"  # 120 minutes after onset
    }
    # Alert at 10:15 (75 min after onset, 45 min before collapse)
    alerts_accel = [
        Alert("SCEN_ACCEL_01", "2026-10-27T10:15:00Z", ["NODE_02"], "CRITICAL", "test", "B1")
    ]
    outcome_accel = evaluate_scenario(alerts_accel, truth_accel)
    assert outcome_accel.detected is True
    assert outcome_accel.time_to_detect == 75.0
    assert outcome_accel.lead_time == 45.0
    assert outcome_accel.detected_before_collapse is True


def test_bootstrap_determinism():
    """Verify bootstrap CI is completely deterministic given the seed."""
    vals = [1.2, 4.5, 7.8, 2.3, 9.1, 5.4, 3.2, 6.7, 8.9, 10.1, 2.8, 4.1]
    ci1 = bootstrap_ci(vals, np.mean, n_resamples=500, seed=123)
    ci2 = bootstrap_ci(vals, np.mean, n_resamples=500, seed=123)
    ci3 = bootstrap_ci(vals, np.mean, n_resamples=500, seed=999)

    assert ci1 == ci2
    assert ci1 != ci3
