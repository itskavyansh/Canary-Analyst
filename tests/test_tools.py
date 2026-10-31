import json
from pathlib import Path
import pytest

from agent.tools import (
    get_node_history,
    compare_neighbor_nodes,
    get_sensor_health,
    check_blast_schedule,
    project_time_to_threshold
)
from agent.tool_schemas import ToolDispatcher, TOOL_SCHEMAS


def _make_dummy_readings(n_steps=60):
    readings = []
    base_time = "2026-10-27T08:"
    for i in range(n_steps):
        ts = f"2026-10-27T08:{i:02d}:00Z"
        for nid in ["NODE_01", "NODE_02", "NODE_03", "NODE_04"]:
            tilt_val = 0.1 * i if nid == "NODE_01" else 0.0
            readings.append({
                "node_id": nid,
                "timestamp": ts,
                "tilt_x": tilt_val,
                "tilt_y": 0.0,
                "vibration": 0.04,
                "distance": 18.0 + (0.05 * i if nid == "NODE_01" else 0.0),
                "mpu6050_status": "ok",
                "hc_sr04_status": "ok",
                "ads1115_status": "ok",
                "piezo_peak": 0.02,
                "piezo_rms": 0.008,
                "piezo_peak_to_peak": 0.04,
            })
    return readings


def test_no_lookahead_invariant():
    """Outputs must be 100% identical when all rows after as_of are replaced with garbage."""
    clean_readings = _make_dummy_readings(60)
    as_of = "2026-10-27T08:30:00Z"

    # Create corrupted copy where future readings (after 08:30:00Z) are overwritten with extreme garbage
    corrupted_readings = []
    for r in clean_readings:
        r_copy = dict(r)
        if r["timestamp"] > as_of:
            r_copy["tilt_x"] = 9999.9
            r_copy["tilt_y"] = -8888.8
            r_copy["vibration"] = 777.7
            r_copy["distance"] = -999.0
            r_copy["mpu6050_status"] = "fault"
        corrupted_readings.append(r_copy)

    # 1. get_node_history
    res1 = get_node_history(clean_readings, as_of, "NODE_01", "tilt_x", 30)
    res2 = get_node_history(corrupted_readings, as_of, "NODE_01", "tilt_x", 30)
    assert res1 == res2

    # 2. compare_neighbor_nodes
    c1 = compare_neighbor_nodes(clean_readings, as_of, "tilt_x", 30)
    c2 = compare_neighbor_nodes(corrupted_readings, as_of, "tilt_x", 30)
    assert c1 == c2

    # 3. get_sensor_health
    h1 = get_sensor_health(clean_readings, as_of, "NODE_01")
    h2 = get_sensor_health(corrupted_readings, as_of, "NODE_01")
    assert h1 == h2

    # 4. project_time_to_threshold
    p1 = project_time_to_threshold(clean_readings, as_of, "NODE_01", "tilt", 30)
    p2 = project_time_to_threshold(corrupted_readings, as_of, "NODE_01", "tilt", 30)
    assert p1 == p2


def test_determinism():
    """Tools must return identical outputs given the same inputs."""
    readings = _make_dummy_readings(45)
    as_of = "2026-10-27T08:40:00Z"

    h1 = get_node_history(readings, as_of, "NODE_01", "distance", 30)
    h2 = get_node_history(readings, as_of, "NODE_01", "distance", 30)
    assert h1 == h2
    assert h1["evidence_id"] == h2["evidence_id"]


def test_correct_values_on_handcrafted_series():
    """Verify exact values on handcrafted series."""
    readings = []
    # 35 readings: first 30 constant at 18.0, last 5 stepping up by 1.0 cm per minute
    for i in range(35):
        ts = f"2026-10-27T08:{i:02d}:00Z"
        dist = 18.0 if i < 30 else 18.0 + (i - 29) * 1.0
        readings.append({
            "node_id": "NODE_01",
            "timestamp": ts,
            "tilt_x": 0.0,
            "tilt_y": 0.0,
            "vibration": 0.03,
            "distance": dist,
            "mpu6050_status": "ok",
            "hc_sr04_status": "ok",
            "ads1115_status": "ok",
            "piezo_peak": 0.02,
            "piezo_rms": 0.008,
            "piezo_peak_to_peak": 0.04
        })

    as_of = "2026-10-27T08:34:00Z"
    # Fit OLS on the last 5 readings (values: 19.0, 20.0, 21.0, 22.0, 23.0 -> slope = 1.0 cm/min)
    res = project_time_to_threshold(readings, as_of, "NODE_01", "distance", fit_minutes=5, threshold=25.0)
    assert res["slope_per_minute"] == 1.0
    assert res["current_value"] == 5.0  # abs change from baseline 18.0 -> 23.0 - 18.0 = 5.0 cm
    assert res["target_threshold"] == 25.0
    # Remaining = 25.0 - 5.0 = 20.0 cm -> at 1.0 cm/min = 20.0 minutes
    assert res["minutes_to_threshold"] == 20.0
    assert res["r_squared"] == 1.0

    # Blast schedule test: +-30 minute window
    blast_sched = [
        {"scheduled_time": "2026-10-27T08:05:00Z", "location": "North Wall"},  # 25 min prior (within +-30 min)
        {"scheduled_time": "2026-10-27T08:55:00Z", "location": "East Pit"},    # 25 min after (within +-30 min)
        {"scheduled_time": "2026-10-27T07:15:00Z", "location": "Far West"},    # 75 min prior (outside +-30 min)
        {"scheduled_time": "2026-10-27T10:00:00Z", "location": "South Pit"}     # 90 min after (outside +-30 min)
    ]
    b_res = check_blast_schedule(blast_sched, as_of="2026-10-27T08:30:00Z")
    assert b_res["blast_scheduled_within_30min"] is True
    assert len(b_res["nearby_blasts"]) == 2
    delta_mins = sorted([b["delta_minutes"] for b in b_res["nearby_blasts"]])
    assert delta_mins == [-25.0, 25.0]
    assert b_res["time_since_last_scheduled_blast_min"] == 25.0


def test_dispatcher_invalid_args_returns_json_error():
    """Invalid arguments must return structured JSON error dictionary without raising exception."""
    readings = _make_dummy_readings(10)
    dispatcher = ToolDispatcher(readings=readings, blast_schedule=[], as_of="2026-10-27T08:05:00Z")

    # Missing required argument 'channel'
    res1 = dispatcher.dispatch("get_node_history", {"node_id": "NODE_01", "minutes_back": 15})
    assert isinstance(res1, dict)
    assert res1.get("status") == "failed"
    assert "validation" in res1.get("error", "").lower()

    # Unknown tool name
    res2 = dispatcher.dispatch("non_existent_tool", {})
    assert isinstance(res2, dict)
    assert res2.get("status") == "failed"
    assert "unknown tool" in res2.get("error", "").lower()

