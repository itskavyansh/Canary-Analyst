"""Report on a real-session run. Reads the events file ONLY here, after the run.

Counts only: no accuracy percentages. Alerts outside labelled events are
'unlabelled disturbance'; alerts inside 'unplanned' events are reported
separately. Neither is called a false alarm.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from realdata.adapter import parse_timezone, to_utc

HEADER = "STAGED BENCH EVENTS ON A 2-NODE PROTOTYPE, NOT MINE DATA"
TOLERANCE_MIN = 2      # an alert up to 2 min after an event's end still counts for it
MERGE_GAP_MIN = 15     # alert rows closer than this form one episode (as in the benchmark)
DETECTOR_ORDER = ["B0", "B1", "B2.1", "AGENT"]


def load_events(path: Path) -> List[dict]:
    events = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tz = parse_timezone((row.get("timezone") or "").strip())
            s, e = to_utc(row.get("start"), tz), to_utc(row.get("end"), tz)
            if s is None or e is None:
                continue
            events.append({"start": s, "end": e, "type": (row.get("type") or "").strip(),
                           "nodes": (row.get("nodes") or "").strip(),
                           "notes": (row.get("notes") or "").strip()})
    events.sort(key=lambda x: x["start"])
    return events


def load_alerts(out_dir: Path) -> Dict[str, List[dict]]:
    res: Dict[str, List[dict]] = {}
    for det in DETECTOR_ORDER:
        p = out_dir / f"alerts_{det}.jsonl"
        if p.exists():
            rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
            for r in rows:
                r["t"] = pd.Timestamp(r["time"])
            res[det] = rows
    return res


def episodes(rows: List[dict]) -> List[dict]:
    """Merge alert rows (any level incl. REVIEW) into episodes by time gap."""
    eps: List[dict] = []
    for r in sorted(rows, key=lambda x: x["t"]):
        if eps and (r["t"] - eps[-1]["last"]) <= pd.Timedelta(minutes=MERGE_GAP_MIN):
            eps[-1]["last"] = r["t"]
            eps[-1]["rows"].append(r)
        else:
            eps.append({"first": r["t"], "last": r["t"], "rows": [r]})
    return eps


def _in_window(t, ev) -> bool:
    return ev["start"] <= t <= ev["end"] + pd.Timedelta(minutes=TOLERANCE_MIN)


def _fmt(t) -> str:
    return t.strftime("%H:%M:%S")


def build_report(out_dir, events_path, session=None) -> str:
    out_dir = Path(out_dir)
    events = load_events(Path(events_path))
    alerts = load_alerts(out_dir)
    decisions = []
    dp = out_dir / "agent_decisions.jsonl"
    if dp.exists():
        decisions = [json.loads(l) for l in open(dp, encoding="utf-8") if l.strip()]
    resolutions = {}
    rp = out_dir / "hold_resolutions.jsonl"
    if rp.exists():
        for l in open(rp, encoding="utf-8"):
            if l.strip():
                h = json.loads(l)
                resolutions[h["episode_id"]] = h["outcome"]

    L: List[str] = []
    L.append("=" * 78)
    L.append(HEADER)
    L.append("=" * 78)
    L.append(f"detectors in this run: {', '.join(alerts) or 'none'}")
    L.append(f"events counted if an alert falls inside [start, end + {TOLERANCE_MIN} min]; "
             f"episodes merge alert rows closer than {MERGE_GAP_MIN} min.")
    L.append("")

    labelled = [e for e in events if e["type"] != "quiet"]
    for ev in labelled:
        L.append(f"EVENT {ev['type']} | nodes: {ev['nodes'] or '-'} | {_fmt(ev['start'])} -> {_fmt(ev['end'])} UTC"
                 + (f" | {ev['notes']}" if ev['notes'] else ""))
        for det in DETECTOR_ORDER:
            if det == "AGENT" or det not in alerts:
                continue
            hits = sorted([a for a in alerts[det] if _in_window(a["t"], ev)], key=lambda a: a["t"])
            if hits:
                a0 = hits[0]
                delay = (a0["t"] - ev["start"]).total_seconds() / 60.0
                L.append(f"  {det}: alerted, first {_fmt(a0['t'])}, delay {delay:.0f} min, level {a0['level']} "
                         f"({len(hits)} alert rows)")
            else:
                L.append(f"  {det}: no alert")
        if "AGENT" in alerts or decisions:
            cands = [d for d in decisions if _in_window(pd.Timestamp(d["timestamp"]), ev)]
            if not cands:
                L.append("  AGENT: no candidate investigated in this window")
            for d in cands:
                outcome = resolutions.get(d["episode_id"], "n/a (not held)" if d["guard_action"] != "DOWNGRADE"
                                          else "no resolution recorded")
                L.append(f"  AGENT: investigated {d['episode_id']} at {_fmt(pd.Timestamp(d['timestamp']))}: "
                         f"hypothesis={d['hypothesis']}, recommendation={d['recommendation']}, "
                         f"guard={d['guard_action']} ({d['guard_reason']}), hold={outcome}")
                if d.get("brief"):
                    L.append(f"    brief: {d['brief']}")
        L.append("")

    # quiet periods
    quiet = [e for e in events if e["type"] == "quiet"]
    L.append(f"QUIET PERIODS ({len(quiet)} labelled): alert episodes per detector")
    for det in alerts:
        n = 0
        for q in quiet:
            n += len(episodes([a for a in alerts[det] if _in_window(a["t"], q)]))
        L.append(f"  {det}: {n} alert episode(s) inside quiet periods")
    L.append("")

    # unplanned events: reported separately
    unplanned = [e for e in events if e["type"] == "unplanned"]
    L.append(f"UNPLANNED EVENTS ({len(unplanned)} labelled), reported separately, not called false alarms:")
    for det in alerts:
        n = sum(len(episodes([a for a in alerts[det] if _in_window(a["t"], u)])) for u in unplanned)
        L.append(f"  {det}: {n} alert episode(s) inside unplanned events")
    L.append("")

    # unlabelled disturbance: alerts inside no labelled window at all
    L.append("UNLABELLED DISTURBANCE (alerts outside every labelled event window):")
    for det in alerts:
        rows = [a for a in alerts[det] if not any(_in_window(a["t"], e) for e in events)]
        eps = episodes(rows)
        L.append(f"  {det}: {len(eps)} episode(s)" + (
            " at " + ", ".join(_fmt(e["first"]) for e in eps[:10]) if eps else ""))
    L.append("")
    L.append("Counts only. Staged bench sessions are not mine data; no accuracy is claimed.")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True, help="results/real/<name>")
    p.add_argument("--events", required=True, help="data/real/session_<name>_events.csv")
    args = p.parse_args(argv)
    text = build_report(Path(args.results), Path(args.events))
    (Path(args.results) / "report.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
