"""Two-node probe: exercise every component on an adapter-built 2-node scenario.

NO network and NO API calls: the analyst talks to a scripted fake HTTP client.
It reports crashes (with file and line) and components that become inert.

    python -m realdata.probe_two_nodes [--session data/real/session_dryrun.csv]
"""
from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

from agent.analyst import Analyst
from agent.detector_agent import AgentDetector
from agent.tools import (check_blast_schedule, compare_neighbor_nodes, get_node_history,
                         get_sensor_health, project_time_to_threshold)
from eval.run_eval import stream_scenario
from realdata.adapter import load_session
from realdata.scenario import write_scenario

HYPOTHESES = ["blast", "machinery_impact", "environmental_tilt", "sensor_fault", "sensor_stuck",
              "ground_movement"]


class _Resp:
    def __init__(self, body):
        self.status_code = 200
        self._b = body
        self.text = json.dumps(body)

    def json(self):
        return self._b


class ScriptedClient:
    """Fake HTTP client that plays a fixed investigation. Never touches the network."""

    def __init__(self, hypothesis: str, nodes):
        self.h, self.nodes, self.calls = hypothesis, nodes, 0

    def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002
        import json as _j
        self.calls += 1
        msgs = json["messages"]
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        if "response_format" in json:
            ev = []
            for m in msgs:
                if m.get("role") == "tool":
                    e = _j.loads(m["content"]).get("evidence_id")
                    if e:
                        ev.append(e)
            body = {"hypothesis": self.h, "recommendation": "DOWNGRADE", "confidence": 0.95,
                    "cited_evidence_ids": ev, "findings": ["scripted"], "brief": "scripted probe"}
            return _Resp({"choices": [{"message": {"role": "assistant", "content": _j.dumps(body)}}],
                          "usage": usage})
        if not any(m.get("role") == "tool" for m in msgs):
            n0 = self.nodes[0]
            calls = [("get_sensor_health", {"node_id": n0}),
                     ("compare_neighbor_nodes", {"channel": "tilt", "window_minutes": 30}),
                     ("get_node_history", {"node_id": n0, "channel": "vibration", "minutes_back": 60}),
                     ("check_blast_schedule", {}),
                     ("project_time_to_threshold", {"node_id": n0, "channel": "tilt", "fit_minutes": 30})]
            tcs = [{"id": f"c{i}", "type": "function",
                    "function": {"name": n, "arguments": _j.dumps(a)}} for i, (n, a) in enumerate(calls)]
            return _Resp({"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": tcs}}],
                          "usage": usage})
        return _Resp({"choices": [{"message": {"role": "assistant", "content": "done"}}], "usage": usage})


def where(exc: BaseException) -> str:
    tb = traceback.extract_tb(exc.__traceback__)[-1]
    return f"{tb.filename}:{tb.lineno} in {tb.name}: {type(exc).__name__}: {exc}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="data/real/session_dryrun.csv")
    args = ap.parse_args(argv)

    sess = load_session(args.session, verbose=False)
    print(f"[probe] nodes={sess.nodes} readings={len(sess.readings)}")
    rows = [r.model_dump() for r in sess.readings]
    as_of = sess.end
    n0 = sess.nodes[0]
    crashes = []

    def attempt(label, fn):
        try:
            out = fn()
            print(f"[probe] OK    {label}")
            return out
        except Exception as e:  # noqa: BLE001
            crashes.append((label, where(e)))
            print(f"[probe] CRASH {label}: {where(e)}")
            return None

    print("\n-- agent tools on 2 nodes --")
    cmp_ = attempt("compare_neighbor_nodes", lambda: compare_neighbor_nodes(rows, as_of, "tilt", 30))
    if cmp_:
        print(f"   amplitude_decays_with_distance={cmp_['amplitude_decays_with_distance']} "
              f"(needs >=3 nodes, so always False here); nodes seen={sorted(cmp_['per_node_change'])}")
    attempt("get_node_history", lambda: get_node_history(rows, as_of, n0, "vibration", 60))
    attempt("get_sensor_health", lambda: get_sensor_health(rows, as_of, n0))
    attempt("check_blast_schedule", lambda: check_blast_schedule([], as_of))
    attempt("project_time_to_threshold", lambda: project_time_to_threshold(rows, as_of, n0, "tilt", 30))

    print("\n-- full AgentDetector with scripted analyst, every guard hypothesis (DOWNGRADE, conf 0.95) --")
    out_root = Path("results/real/probe")
    scen = write_scenario(sess, out_root / "scenario")
    for h in HYPOTHESES:
        client = ScriptedClient(h, sess.nodes)
        an = Analyst(model="scripted-fake", cache_dir=str(out_root / f"cache_{h}"),
                     runs_dir=str(out_root / f"runs_{h}"), client=client)
        det = AgentDetector(analyst=an)

        def run():
            return stream_scenario(det, Path(scen["readings_file"]), Path(scen["meta_file"]))
        alerts = attempt(f"AgentDetector hypothesis={h}", run)
        if alerts is None:
            continue
        for d in det.decisions_log:
            print(f"   cand {d['episode_id']}: guard={d['guard_decision'].action} :: {d['guard_decision'].reason}")
        print(f"   fake-client calls={client.calls}, hold outcomes="
              f"{[x.outcome for x in det.hold_manager.hold_resolutions_log]}")

    print("\n-- summary --")
    if crashes:
        print("CRASHES:")
        for label, w in crashes:
            print(f"  {label}: {w}")
    else:
        print("no crashes")


if __name__ == "__main__":
    main()
