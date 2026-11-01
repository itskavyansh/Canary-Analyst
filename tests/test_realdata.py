import builtins
import json
from pathlib import Path

import pandas as pd
import pytest

from engine.common import Detector
from eval.run_eval import DETECTOR_REGISTRY
from realdata import adapter
from realdata.adapter import load_session
from realdata.run_real import run_detectors
from realdata.scenario import write_scenario

COLS = ("id,node_id,timestamp,tilt_x,tilt_y,vibration,distance,created_at,mpu6050_status,"
        "hc_sr04_status,displacement,ads1115_status,piezo_peak,piezo_rms,piezo_peak_to_peak")


def row(node, ts, tx=1.0, ty=2.0, vib=0.1, dist=10.0, mpu="", hc="", pp=0.0, rms=0.0, p2p=0.0):
    return f"1,{node},{ts},{tx},{ty},{vib},{dist},,{mpu},{hc},,,{pp},{rms},{p2p}"


def make_session(tmp_path, rows, nodes=("NODE_A", "NODE_B"), tz="UTC", events_notes="x", name="t"):
    d = tmp_path / "real"
    d.mkdir(exist_ok=True)
    csv = d / f"session_{name}.csv"
    csv.write_text(COLS + "\n" + "\n".join(rows) + "\n")
    (d / f"session_{name}_layout.json").write_text(
        json.dumps({n: {"x": float(i), "y": 0.0} for i, n in enumerate(nodes)}))
    (d / f"session_{name}_events.csv").write_text(
        "start,end,timezone,type,nodes,notes\n"
        f"2026-10-27 10:00:00,2026-10-27 10:30:00,{tz},quiet,,{events_notes}\n"
        f"2026-10-27 10:30:00,2026-10-27 10:40:00,{tz},tap_one_node,NODE_A,{events_notes}\n")
    return csv


def test_max_median_rule_and_fault_status(tmp_path):
    rows = [
        row("NODE_A", "2026-10-27T10:00:05Z", tx=1, vib=0.1, pp=0.3, mpu=""),
        row("NODE_A", "2026-10-27T10:00:20Z", tx=5, vib=0.9, pp=0.1, mpu="fault"),
        row("NODE_A", "2026-10-27T10:00:40Z", tx=2, vib=0.2, pp=0.2, mpu=""),
        row("NODE_B", "2026-10-27T10:00:10Z"),
    ]
    s = load_session(make_session(tmp_path, rows), verbose=False)
    a = [r for r in s.readings if r.node_id == "NODE_A"][0]
    assert a.vibration == 0.9          # MAX
    assert a.piezo_peak == 0.3         # MAX
    assert a.tilt_x == 2.0             # MEDIAN of 1,5,2
    assert a.mpu6050_status == "fault"  # any fault in the bin
    assert a.hc_sr04_status == "ok"


def test_timezone_from_events_file_and_mixed_formats(tmp_path):
    rows = [
        row("NODE_A", "2026-10-27 10:00:00"),               # naive: Asia/Kolkata -> 04:30Z
        row("NODE_B", "2026-10-27T05:00:00+00:00"),         # explicit offset wins
        row("NODE_A", "2026-10-27 10:01:00.5"),
    ]
    s = load_session(make_session(tmp_path, rows, tz="Asia/Kolkata"), verbose=False)
    ts = {(r.node_id, r.timestamp) for r in s.readings}
    assert ("NODE_A", "2026-10-27T04:30:00Z") in ts
    assert ("NODE_B", "2026-10-27T05:00:00Z") in ts
    assert s.start == "2026-10-27T04:30:00Z"


def test_ignores_test_node_names(tmp_path):
    rows = [row("NODE_A", "2026-10-27T10:00:00Z"), row("NODE_B", "2026-10-27T10:00:00Z"),
            row("NODE_TEST_ALERT", "2026-10-27T10:00:00Z")]
    s = load_session(make_session(tmp_path, rows), verbose=False)
    assert s.nodes == ["NODE_A", "NODE_B"]
    assert s.ignored_nodes == {"NODE_TEST_ALERT": 1}


def test_no_lookahead_ffill_and_prefix_invariance(tmp_path):
    # NODE_B reports at minute 0 and minute 6 only
    rows = []
    for m in range(0, 8):
        rows.append(row("NODE_A", f"2026-10-27T10:{m:02d}:00Z", tx=float(m)))
    rows.append(row("NODE_B", "2026-10-27T10:00:00Z", tx=7.0))
    rows.append(row("NODE_B", "2026-10-27T10:06:00Z", tx=99.0))
    s = load_session(make_session(tmp_path, rows), verbose=False)
    b = {r.timestamp[11:16]: r.tilt_x for r in s.readings if r.node_id == "NODE_B"}
    assert b["10:00"] == 7.0 and b["10:01"] == 7.0 and b["10:02"] == 7.0   # filled from the PAST
    assert "10:03" not in b and "10:04" not in b and "10:05" not in b       # >2 min: missing
    assert b["10:06"] == 99.0
    assert any(g["node"] == "NODE_B" and g["minutes"] == 5 for g in s.gaps)

    # prefix invariance: cutting the recording at minute 4 must not change earlier output
    short = [r for r in rows if not (r.split(",")[2] >= "2026-10-27T10:05:00Z")]
    s2 = load_session(make_session(tmp_path, short, name="short"), verbose=False)
    full_prefix = [r.model_dump() for r in s.readings if r.timestamp <= "2026-10-27T10:04:00Z"]
    short_all = [r.model_dump() for r in s2.readings if r.timestamp <= "2026-10-27T10:04:00Z"]
    assert full_prefix == short_all


def test_missing_node_pipeline_runs(tmp_path):
    # layout names two nodes but only NODE_A has data
    rows = [row("NODE_A", f"2026-10-27T10:{m:02d}:00Z", tx=float(m % 3)) for m in range(0, 45)]
    s = load_session(make_session(tmp_path, rows), verbose=False)
    assert s.nodes == ["NODE_A"]
    scen = write_scenario(s, tmp_path / "out")
    info = run_detectors(scen, ["B0", "B1", "B2.1"], tmp_path / "out")
    assert set(info) == {"B0", "B1", "B2.1"}


def test_events_file_never_reaches_detector(tmp_path, monkeypatch):
    marker = "SECRET_EVENT_MARKER"
    rows = [row(n, f"2026-10-27T10:{m:02d}:00Z") for m in range(0, 40) for n in ("NODE_A", "NODE_B")]
    csv = make_session(tmp_path, rows, events_notes=marker)
    events_path = csv.with_name(csv.stem + "_events.csv")
    s = load_session(csv, verbose=False)
    assert marker not in repr(s)            # nothing from the events file stored in the session
    scen = write_scenario(s, tmp_path / "out")
    assert marker not in Path(scen["meta_file"]).read_text()
    assert marker not in Path(scen["readings_file"]).read_text()

    seen = {"meta": None, "updates": []}

    class Spy(Detector):
        def reset(self, scenario_meta):
            seen["meta"] = dict(scenario_meta)

        def update(self, timestamp, readings_by_node):
            seen["updates"].append((timestamp, json.dumps(readings_by_node, default=str)))
            return []

    monkeypatch.setitem(DETECTOR_REGISTRY, "SPY", Spy)

    opened = []
    real_open = builtins.open

    def spy_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    run_detectors(scen, ["SPY"], tmp_path / "out")
    monkeypatch.undo()

    assert set(seen["meta"]) == {"scenario_id", "node_coordinates_m", "blast_schedule"}
    assert seen["meta"]["blast_schedule"] == []
    assert marker not in json.dumps(seen["meta"], default=str)
    assert all(marker not in u[1] for u in seen["updates"])
    assert len(seen["updates"]) == 40
    assert not any(str(events_path) in o for o in opened)   # events file not even opened during the run
