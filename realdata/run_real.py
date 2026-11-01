"""Run frozen detectors (and optionally the agent) on a real prototype session.

    python -m realdata.run_real --session data/real/session_<name>.csv --detectors B0,B1,B2.1 [--agent]

The events file is not given to any detector or the agent. It is read by
realdata.report only AFTER the run finishes.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from eval.run_eval import DETECTOR_REGISTRY, stream_scenario
from realdata.adapter import load_session, session_name_from_path, sibling
from realdata.scenario import write_scenario

DETECTOR_ALIASES = {"B2.1": "B2", "B2": "B2"}


def make_detector(label: str, out_dir: Path, model=None):
    key = DETECTOR_ALIASES.get(label, label)
    if key == "AGENT":
        from agent.analyst import Analyst
        analyst = Analyst(
            model=model or os.getenv("AGENT_MODEL", "muse-spark-1.3"),
            cache_dir=str(out_dir / "agent_cache"),
            runs_dir=str(out_dir),
        )
        return DETECTOR_REGISTRY["AGENT"](analyst=analyst)
    if key not in DETECTOR_REGISTRY:
        raise ValueError(f"Unknown detector '{label}'")
    return DETECTOR_REGISTRY[key]()


def run_detectors(scen: Dict[str, str], labels: List[str], out_dir: Path, model=None) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    for label in labels:
        det = make_detector(label, out_dir, model)
        alerts = stream_scenario(det, Path(scen["readings_file"]), Path(scen["meta_file"]))
        with open(out_dir / f"alerts_{label}.jsonl", "w", encoding="utf-8") as f:
            for a in alerts:
                f.write(json.dumps(dataclasses.asdict(a)) + "\n")
        info[label] = {"alerts": len(alerts)}
        print(f"[run_real] {label}: {len(alerts)} alert rows")
        if label == "AGENT":
            _dump_agent(det, out_dir)
            info[label]["candidates"] = len(det.candidate_history)
            info[label]["cost_usd"] = round(det.analyst.total_cost_spent, 5)
            info[label]["model_id"] = det.analyst.model
    return info


def _dump_agent(det, out_dir: Path) -> None:
    with open(out_dir / "agent_decisions.jsonl", "w", encoding="utf-8") as f:
        for d in det.decisions_log:
            ar, gd = d["analyst_result"], d["guard_decision"]
            parsed = (ar.parsed if ar is not None else None) or {}
            f.write(json.dumps({
                "episode_id": d["episode_id"],
                "timestamp": d["timestamp"],
                "hypothesis": parsed.get("hypothesis"),
                "recommendation": parsed.get("recommendation"),
                "confidence": parsed.get("confidence"),
                "brief": parsed.get("brief"),
                "tool_calls": len(ar.tool_calls) if ar is not None else 0,
                "parsed_ok": bool(parsed),
                "guard_action": gd.action,
                "guard_reason": gd.reason,
            }) + "\n")
    with open(out_dir / "hold_resolutions.jsonl", "w", encoding="utf-8") as f:
        for h in det.hold_manager.hold_resolutions_log:
            f.write(json.dumps(dataclasses.asdict(h)) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description="Replay a real prototype session through the frozen detectors.")
    p.add_argument("--session", required=True, help="path to data/real/session_<name>.csv")
    p.add_argument("--detectors", default="B0,B1,B2.1")
    p.add_argument("--agent", action="store_true", help="also run the AGENT (makes API calls)")
    p.add_argument("--model", default=None)
    p.add_argument("--out", default=None, help="default results/real/<name>")
    args = p.parse_args(argv)

    csv_path = Path(args.session)
    name = session_name_from_path(csv_path)
    out_dir = Path(args.out) if args.out else Path("results/real") / name
    out_dir.mkdir(parents=True, exist_ok=True)

    labels = [d.strip() for d in args.detectors.split(",") if d.strip() and d.strip() != "AGENT"]
    if args.agent:
        labels.append("AGENT")

    session = load_session(csv_path)
    scen = write_scenario(session, out_dir / "scenario")
    info = run_detectors(scen, labels, out_dir, args.model)
    info.update({"session": name, "nodes": session.nodes, "start": session.start, "end": session.end,
                 "agent_run": bool(args.agent)})
    with open(out_dir / "run_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

    events = sibling(csv_path, "_events.csv")
    if events.exists():
        from realdata.report import build_report
        text = build_report(out_dir, events, session)
        (out_dir / "report.md").write_text(text, encoding="utf-8")
        print(text)
    else:
        print("[run_real] no events file found, report skipped")


if __name__ == "__main__":
    main()
