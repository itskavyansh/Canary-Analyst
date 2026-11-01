# Real-data replay notes (2-node prototype)

Staged bench sessions, **not mine data**. Nothing here is an accuracy claim. Frozen detectors, B2.1 config, agent prompt, guard and thresholds are unchanged.

## Pipeline
`realdata/adapter.py` (UTC, 1-minute bins, max for vibration/piezo_peak/piezo_peak_to_peak, median for the rest, fault if any raw fault in the bin, forward-fill at most 2 minutes, longer gaps left missing and reported) -> `realdata/scenario.py` (readings, layout, empty blast schedule, no ground truth) -> `realdata/run_real.py` (existing `stream_scenario` harness) -> `realdata/report.py` (reads the events file only after the run).

The events file is read by the adapter only for its timezone column and for one console warning about the length of the quiet start. Neither reaches a detector or the agent (tested with a spy).

## What becomes inert with 2 nodes (no crashes found)
Probed with `python -m realdata.probe_two_nodes` (scripted fake client, no API).

| Component | Effect with 2 nodes |
|---|---|
| B2.1 common-mode rejection (`baseline_b2.py`, needs >= 3 nodes) | Never active. Rain-like common tilt is not suppressed. |
| `compare_neighbor_nodes` distance-decay flag (`tools.py`, needs >= 3 nodes) | Always `False`. Correlation and first-moved node still work with 2 nodes. |
| Guard gate for `blast` (needs >= 3 nodes in synchrony, or a scheduled blast) | Blast schedule is empty, so a blast downgrade can never be approved. Guard keeps the alert. |
| Guard gate for `environmental_tilt` (needs >= 3 nodes common-mode) | Can never be approved. Guard keeps the alert. |
| Guard gates for `machinery_impact`, `sensor_fault`, `sensor_stuck` | Work. Caution: "only one node moved" is easier to satisfy with one neighbour. |

Other observations:
- The agent's first message says "Square 4-node network" and the tool descriptions mention a 4-node array and a quarry log. The prompt and tools are frozen, so this is left as is.
- `compare_neighbor_nodes` is not given the layout file (the dispatcher does not pass it) and falls back to the built-in 4-node square, so the layout is only shown to the model as text.
- Baselines use the first 30 one-minute readings, so the quiet period at the start should be at least 30 minutes.
- Missing channels are filled with 0.0 and flagged loudly. The old `data/real_readings.csv` has empty piezo columns.

## Dry run on `data/real_readings.csv`
See the project report for the result (longest 2-node stretch: NODE_01 + NODE_02, 2026-09-11 14:00-17:00 UTC, only 36 and 18 real minutes). The layout gap of 1 m there is an assumption. Re-run with `python -m realdata.dry_run_existing`.
