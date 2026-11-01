"""Dry run on the existing data/real_readings.csv (no agent, no API calls).

Finds the longest stretch where two chosen nodes both have data in the same
hours, writes it as a temporary session under data/real/ (git-ignored) with an
ASSUMED layout, and runs B0, B1 and B2.1 on it through the real-data pipeline.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from realdata.run_real import main as run_main

SRC = Path("data/real_readings.csv")
GOOD = ("NODE_01", "NODE_02", "NODE_03")


def find_best_stretch():
    d = pd.read_csv(SRC, dtype=str, keep_default_na=False)
    d = d[d["node_id"].isin(GOOD)].copy()
    d["ts"] = pd.to_datetime(d["timestamp"], format="mixed", utc=True)
    d["h"] = d["ts"].dt.floor("h")
    counts = d.groupby(["h", "node_id"]).size().unstack(fill_value=0)
    best = None
    for a, b in itertools.combinations(GOOD, 2):
        ok = ((counts[a] > 0) & (counts[b] > 0)).sort_index()
        run = []
        for h, flag in ok.items():
            if flag and run and h - run[-1] == pd.Timedelta(hours=1):
                run.append(h)
            elif flag:
                run = [h]
            else:
                run = []
            if run and (best is None or len(run) > len(best[2])):
                best = (a, b, list(run))
    return d, best


def main():
    d, best = find_best_stretch()
    a, b, hours = best
    t0, t1 = hours[0], hours[-1] + pd.Timedelta(hours=1)
    print(f"[dry-run] longest same-hour stretch: {a} + {b}, {t0} -> {t1} ({len(hours)} h)")
    sub = d[d["node_id"].isin([a, b]) & (d["ts"] >= t0) & (d["ts"] < t1)]
    raw = pd.read_csv(SRC, dtype=str, keep_default_na=False).loc[sub.index]
    out = Path("data/real")
    out.mkdir(parents=True, exist_ok=True)
    raw.to_csv(out / "session_dryrun.csv", index=False)
    # The real gap is unknown for this old data: 1.0 m is an ASSUMPTION.
    with open(out / "session_dryrun_layout.json", "w") as f:
        json.dump({a: {"x": 0.0, "y": 0.0}, b: {"x": 1.0, "y": 0.0}}, f)
    run_main(["--session", str(out / "session_dryrun.csv"), "--detectors", "B0,B1,B2.1"])


if __name__ == "__main__":
    main()
