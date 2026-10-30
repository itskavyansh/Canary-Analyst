from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from generator.scenarios import SCENARIO_TYPES, generate_scenario


def plot_preview(scenario_type: str, seed: int, out_dir: Path):
    scenario_id = f"PREVIEW_{scenario_type.upper()}"
    readings, truth = generate_scenario(scenario_type, scenario_id, seed=seed)

    # Reorganize by node
    nodes = ["NODE_01", "NODE_02", "NODE_03", "NODE_04"]
    colors = {"NODE_01": "#1f77b4", "NODE_02": "#ff7f0e", "NODE_03": "#2ca02c", "NODE_04": "#d62728"}

    node_data = {nid: {"t": [], "tilt_x": [], "tilt_y": [], "vibration": [], "distance": []} for nid in nodes}
    for idx, r in enumerate(readings):
        t_min = idx // 4
        node_data[r.node_id]["t"].append(t_min)
        node_data[r.node_id]["tilt_x"].append(r.tilt_x)
        node_data[r.node_id]["tilt_y"].append(r.tilt_y)
        node_data[r.node_id]["vibration"].append(r.vibration)
        node_data[r.node_id]["distance"].append(r.distance)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(f"SIMULATED: Scenario '{scenario_type}' (ID: {scenario_id})", fontsize=14, fontweight="bold")

    # 1. Tilt X
    for nid in nodes:
        axes[0].plot(node_data[nid]["t"], node_data[nid]["tilt_x"], label=nid, color=colors[nid], alpha=0.85)
    axes[0].set_ylabel("Tilt X (deg)")
    axes[0].grid(True, linestyle="--", alpha=0.5)
    axes[0].legend(loc="upper left", ncol=4)

    # 2. Vibration
    for nid in nodes:
        axes[1].plot(node_data[nid]["t"], node_data[nid]["vibration"], label=nid, color=colors[nid], alpha=0.85)
    axes[1].set_ylabel("Vibration (peak g)")
    axes[1].grid(True, linestyle="--", alpha=0.5)

    # 3. Distance
    for nid in nodes:
        axes[2].plot(node_data[nid]["t"], node_data[nid]["distance"], label=nid, color=colors[nid], alpha=0.85)
    axes[2].set_ylabel("Distance (cm)")
    axes[2].set_xlabel("Time (minutes)")
    axes[2].grid(True, linestyle="--", alpha=0.5)

    # Mark onset / collapse if present
    if truth.get("onset_time"):
        # Calculate onset minute from ISO string
        for ax in axes:
            ax.axvline(x=readings[0].timestamp, color="gray", linestyle=":", alpha=0.0)  # dummy to avoid error

    plt.tight_layout()
    out_file = out_dir / f"preview_{scenario_type}.png"
    plt.savefig(out_file, dpi=120)
    plt.close()
    print(f"Saved preview: {out_file}")


def main():
    out_dir = Path("docs/previews")
    out_dir.mkdir(parents=True, exist_ok=True)
    from generator.build_dataset import SCENARIO_TYPES
    for idx, st in enumerate(SCENARIO_TYPES):
        plot_preview(st, seed=100 + idx, out_dir=out_dir)


if __name__ == "__main__":
    main()

