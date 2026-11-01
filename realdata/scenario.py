"""Build a harness-compatible scenario from a real session. No ground truth, ever."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from realdata.adapter import Session


def write_scenario(session: Session, out_dir) -> Dict[str, str]:
    """Write readings (jsonl) and a SANITIZED meta file shaped like the truth file's
    safe subset (scenario_id, node_coordinates_m, blast_schedule) so that
    eval.run_eval.stream_scenario can be reused unchanged.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = f"REAL_{session.name}"
    readings_file = out_dir / f"{sid}.jsonl"
    meta_file = out_dir / f"{sid}_meta.json"
    with open(readings_file, "w", encoding="utf-8") as f:
        for r in session.readings:
            f.write(json.dumps(r.model_dump()) + "\n")
    meta = {
        "scenario_id": sid,
        "node_coordinates_m": session.layout,
        "blast_schedule": [],
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return {"scenario_id": sid, "readings_file": str(readings_file), "meta_file": str(meta_file)}
