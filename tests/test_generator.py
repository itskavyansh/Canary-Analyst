import json
from pathlib import Path
import pytest
import numpy as np

from generator.schema import NodeReading
from generator.scenarios import generate_scenario


SCENARIO_TYPES = [
    "blast",
    "machinery_impact",
    "rain_tilt",
    "sensor_fault",
    "stuck_sensor",
    "slow_creep",
    "accelerating_creep",
]


def test_schema_validity():
    readings, truth = generate_scenario("blast", "TEST_001", seed=123)
    assert len(readings) == 360 * 4
    for r in readings[:10]:
        assert isinstance(r, NodeReading)
        assert r.node_id in ["NODE_01", "NODE_02", "NODE_03", "NODE_04"]
        assert r.mpu6050_status in ("ok", "fault")
        assert r.hc_sr04_status in ("ok", "fault")
        assert r.ads1115_status in ("ok", "fault")


def test_determinism():
    r1, t1 = generate_scenario("slow_creep", "TEST_DET", seed=999)
    r2, t2 = generate_scenario("slow_creep", "TEST_DET", seed=999)

    assert len(r1) == len(r2)
    assert t1 == t2
    for item1, item2 in zip(r1, r2):
        assert item1.model_dump() == item2.model_dump()


def test_row_counts_all_types():
    for st in SCENARIO_TYPES:
        readings, truth = generate_scenario(st, f"TEST_{st}", seed=42)
        assert len(readings) == 1440  # 360 steps * 4 nodes
        assert truth["simulated"] is True
        assert truth["type"] == st


def test_blast_hits_all_nodes_and_impact_hits_one():
    # Blast hits all 4 nodes
    _, truth_blast = generate_scenario("blast", "BLAST_TEST", seed=101)
    assert len(truth_blast["affected_nodes"]) == 4

    # Machinery impact hits only 1 node
    readings_impact, truth_impact = generate_scenario("machinery_impact", "IMPACT_TEST", seed=202)
    assert len(truth_impact["affected_nodes"]) == 1
    affected_node = truth_impact["affected_nodes"][0]

    # Find the step where the impact occurred
    event_time = truth_impact["onset_time"]
    impact_readings = [r for r in readings_impact if r.timestamp == event_time]
    affected_reading = [r for r in impact_readings if r.node_id == affected_node][0]
    unaffected_readings = [r for r in impact_readings if r.node_id != affected_node]

    # Affected node should have elevated vibration
    assert affected_reading.vibration >= 0.5
    # Other nodes should remain near baseline
    for ur in unaffected_readings:
        assert ur.vibration < 0.2


def test_stuck_sensor_constant():
    readings, truth = generate_scenario("stuck_sensor", "STUCK_TEST", seed=303)
    frozen_node = truth["affected_nodes"][0]
    onset_time = truth["onset_time"]

    # Filter readings for the frozen node starting at onset_time
    frozen_readings = [r for r in readings if r.node_id == frozen_node]
    onset_idx = [i for i, r in enumerate(frozen_readings) if r.timestamp == onset_time][0]

    tail_readings = frozen_readings[onset_idx:]
    assert len(tail_readings) >= 120  # At least 2 hours

    first_val_tilt_x = tail_readings[0].tilt_x
    first_val_dist = tail_readings[0].distance
    for r in tail_readings:
        assert r.tilt_x == first_val_tilt_x
        assert r.distance == first_val_dist
        # Silent failure: status must be ok
        assert r.mpu6050_status == "ok"
        assert r.hc_sr04_status == "ok"


def test_collapse_time_present_only_for_accelerating_creep():
    for st in SCENARIO_TYPES:
        _, truth = generate_scenario(st, f"COLLAPSE_TEST_{st}", seed=404)
        if st == "accelerating_creep":
            assert truth["collapse_time"] is not None
            assert truth["is_hazard"] is True
        else:
            assert truth["collapse_time"] is None


def test_slow_creep_below_thresholds_first_half():
    # Demo thresholds: tilt 15 deg, vibration 1.0 g, distance change 2.0 cm
    # for at least the first half of the hazard window in slow_creep
    for test_seed in [501, 502, 503, 504]:
        readings, truth = generate_scenario("slow_creep", f"CREEP_TEST_{test_seed}", seed=test_seed)
        affected_nodes = truth["affected_nodes"]
        onset_time = truth["onset_time"]

        for nid in affected_nodes:
            node_r = [r for r in readings if r.node_id == nid]
            onset_step = [i for i, r in enumerate(node_r) if r.timestamp == onset_time][0]
            hazard_len = 360 - onset_step
            half_window = onset_step + (hazard_len // 2)

            baseline_dist = node_r[0].distance

            # Check readings in the first half of hazard window
            for r in node_r[onset_step:half_window]:
                assert abs(r.tilt_x) < 15.0
                assert abs(r.tilt_y) < 15.0
                assert r.vibration < 1.0
                assert abs(r.distance - baseline_dist) < 2.0
