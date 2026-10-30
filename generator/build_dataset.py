import argparse
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np

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


def build_dataset(n: int, seed: int, out_dir: str):
    rng = np.random.Generator(np.random.PCG64(seed))
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Balanced mix: ~14% each, with creep types getting slightly more
    # Base count per type
    base_count = n // len(SCENARIO_TYPES)
    counts = {st: base_count for st in SCENARIO_TYPES}
    remainder = n - sum(counts.values())
    # Distribute remainder prioritizing creep scenarios
    priority_order = ["slow_creep", "accelerating_creep", "blast", "machinery_impact", "rain_tilt", "sensor_fault", "stuck_sensor"]
    for i in range(remainder):
        counts[priority_order[i % len(priority_order)]] += 1

    # Generate sequence of scenarios
    scenario_plan = []
    for st, c in counts.items():
        scenario_plan.extend([st] * c)
    rng.shuffle(scenario_plan)

    index_entries: List[Dict[str, Any]] = []

    print(f"Building dataset of {n} scenarios into {out_path} (seed={seed})...")
    print(f"Distribution: {counts}")

    for idx, st in enumerate(scenario_plan):
        scenario_id = f"SCENARIO_{idx:04d}_{st}"
        sub_seed = int(rng.integers(0, 2**31 - 1))

        # 20% of creep scenarios get combo scheduled blast
        overlay_blast = False
        if st in ("slow_creep", "accelerating_creep") and rng.random() < 0.20:
            overlay_blast = True

        readings, ground_truth = generate_scenario(
            scenario_type=st,
            scenario_id=scenario_id,
            seed=sub_seed,
            overlay_blast=overlay_blast
        )

        # Write readings to JSONL
        readings_file = out_path / f"{scenario_id}.jsonl"
        with open(readings_file, "w", encoding="utf-8") as f:
            for r in readings:
                f.write(r.model_dump_json() + "\n")

        # Write ground truth to JSON
        truth_file = out_path / f"{scenario_id}_truth.json"
        with open(truth_file, "w", encoding="utf-8") as f:
            json.dump(ground_truth, f, indent=2)

        index_entries.append({
            "scenario_id": scenario_id,
            "type": st,
            "is_hazard": ground_truth["is_hazard"],
            "seed": sub_seed,
            "overlay_blast": overlay_blast,
            "onset_time": ground_truth["onset_time"],
            "collapse_time": ground_truth["collapse_time"],
            "affected_nodes": ground_truth["affected_nodes"],
            "readings_file": str(readings_file.name),
            "truth_file": str(truth_file.name),
            "reading_count": len(readings)
        })

    # Write index.json
    index_file = out_path / "index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_scenarios": n,
            "seed": seed,
            "distribution": counts,
            "scenarios": index_entries
        }, f, indent=2)

    print(f"Dataset generation complete. Index written to {index_file}")


def main():
    parser = argparse.ArgumentParser(description="Build synthetic scenario dataset for Canary Analyst.")
    parser.add_argument("--n", type=int, default=300, help="Total number of scenarios to generate")
    parser.add_argument("--seed", type=int, default=42, help="Master random seed")
    parser.add_argument("--out", type=str, default="data/scenarios", help="Output directory path")

    args = parser.parse_args()
    build_dataset(n=args.n, seed=args.seed, out_dir=args.out)


if __name__ == "__main__":
    main()

