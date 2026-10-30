from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from generator.schema import NodeReading

NOISE_PROFILE_PATH = Path("generator/noise_profile.json")

# Node layouts: 4 corner nodes in meters
NODE_COORDS = {
    "NODE_01": (0.0, 0.0),
    "NODE_02": (20.0, 0.0),
    "NODE_03": (20.0, 20.0),
    "NODE_04": (0.0, 20.0),
}

SCENARIO_TYPES = [
    "blast",
    "machinery_impact",
    "rain_tilt",
    "sensor_fault",
    "stuck_sensor",
    "slow_creep",
    "accelerating_creep",
]


def load_noise_profile() -> Dict[str, Any]:
    if not NOISE_PROFILE_PATH.exists():
        from generator.calibrate import calibrate
        return calibrate()
    with open(NOISE_PROFILE_PATH, "r") as f:
        return json.load(f)


def generate_ar1_series(n_steps: int, mean: float, std: float, phi: float, rng: np.random.Generator) -> np.ndarray:
    """Generate AR(1) time series: X_t - mu = phi * (X_{t-1} - mu) + W_t."""
    # Ensure phi in (-1, 1)
    phi = max(-0.99, min(0.99, phi))
    # Innovation variance: var(W) = var(X) * (1 - phi^2)
    innov_std = std * math.sqrt(max(1e-6, 1.0 - phi**2))
    w = rng.normal(0, innov_std, size=n_steps)
    x = np.zeros(n_steps)
    x[0] = rng.normal(0, std)
    for t in range(1, n_steps):
        x[t] = phi * x[t - 1] + w[t]
    return mean + x


def generate_scenario(
    scenario_type: str,
    scenario_id: str,
    seed: int,
    overlay_blast: bool = False,
    start_time_iso: str = "2026-10-27T08:00:00Z"
) -> Tuple[List[NodeReading], Dict[str, Any]]:
    """
    Generate 6 hours of simulated data (360 steps) for 4 corner nodes.
    Returns (readings, ground_truth).
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    noise_profile = load_noise_profile()
    noise_source = noise_profile.get("source", "defaults")

    n_steps = 360  # 6 hours at 1 reading/min
    node_ids = ["NODE_01", "NODE_02", "NODE_03", "NODE_04"]

    start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    timestamps = [(start_dt + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(n_steps)]

    # Generate baseline series for each node using AR(1)
    data: Dict[str, Dict[str, np.ndarray]] = {}
    status_flags: Dict[str, Dict[str, List[str]]] = {}

    continuous_noise = noise_profile.get("continuous_step_noise", {})

    for nid in node_ids:
        node_prof = noise_profile["nodes"].get(nid, noise_profile["overall"])
        data[nid] = {}
        for metric in ["tilt_x", "tilt_y", "vibration", "distance", "piezo_peak", "piezo_rms", "piezo_peak_to_peak"]:
            p = node_prof[metric]
            # Use measured baseline mean per node for distance and piezo;
            # For tilt and baseline vibration, keep reference nominal orientation (near 0 deg, ~0.035-0.06 g)
            # so scenarios represent healthy ground installations before subsidence
            if metric == "distance":
                baseline_mean = p.get("mean", 18.0)
            elif metric in ("tilt_x", "tilt_y"):
                baseline_mean = 0.0
            elif metric == "vibration":
                baseline_mean = min(p.get("mean", 0.04), 0.065)
            else:
                baseline_mean = p.get("mean", 0.02)

            # Use step noise standard deviation to model stationary AR(1) fluctuations
            phi = p.get("autocorr_lag1", 0.5)
            if nid in continuous_noise and metric in continuous_noise[nid]:
                step_noise = continuous_noise[nid][metric]
                # stationary std = step_noise / sqrt(1 - phi^2)
                sim_std = step_noise / math.sqrt(max(0.1, 1.0 - phi**2))
            else:
                sim_std = p.get("std", 0.15)
                # Cap excessive distance standard deviation from multi-session bench moves
                if metric == "distance":
                    sim_std = min(sim_std, 0.35)
                elif metric == "vibration":
                    sim_std = min(sim_std, 0.015)

            # Keep stationary baseline noise tight for stable monitoring
            if metric == "distance":
                sim_std = min(sim_std, 0.35)
            elif metric in ("tilt_x", "tilt_y"):
                sim_std = min(sim_std, 0.20)
            elif metric == "vibration":
                sim_std = min(sim_std, 0.015)

            series = generate_ar1_series(n_steps, baseline_mean, sim_std, phi, rng)
            # Physical bounds
            if metric == "vibration":
                series = np.clip(series, 0.005, 10.0)
            elif metric.startswith("piezo"):
                series = np.clip(series, 0.001, 10.0)
            elif metric == "distance":
                series = np.clip(series, 2.0, 500.0)
            data[nid][metric] = series

        status_flags[nid] = {
            "mpu6050_status": ["ok"] * n_steps,
            "hc_sr04_status": ["ok"] * n_steps,
            "ads1115_status": ["ok"] * n_steps,
        }

    # Initialize ground truth metadata
    ground_truth: Dict[str, Any] = {
        "scenario_id": scenario_id,
        "type": scenario_type,
        "seed": seed,
        "is_hazard": False,
        "onset_time": None,
        "collapse_time": None,
        "affected_nodes": [],
        "events": [],
        "blast_schedule": [],
        "node_coordinates_m": NODE_COORDS,
        "noise_profile_source": noise_source,
        "simulated": True,
        "overlay_blast": overlay_blast
    }

    # Helper to schedule a blast event
    def add_blast_event(step_idx: int, is_scheduled: bool) -> Dict[str, Any]:
        blast_time = timestamps[step_idx]
        blast_event = {
            "type": "blast",
            "time": blast_time,
            "scheduled": is_scheduled
        }
        ground_truth["events"].append(blast_event)

        if is_scheduled:
            # Blast schedule window is +-10 minutes around scheduled time
            ground_truth["blast_schedule"].append({
                "scheduled_time": blast_time,
                "window_start": (start_dt + timedelta(minutes=max(0, step_idx - 10))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "window_end": (start_dt + timedelta(minutes=min(n_steps - 1, step_idx + 10))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "location": "North Quarry Face"
            })

        # Blast spatial mechanics: blast center near or outside node grid
        bx = float(rng.uniform(-10.0, 30.0))
        by = float(rng.uniform(-10.0, 30.0))
        base_blast_g = float(rng.uniform(1.5, 3.5))

        for nid, (nx, ny) in NODE_COORDS.items():
            dist = math.hypot(nx - bx, ny - by)
            # Amplitude decays with distance: A / (1 + 0.1 * dist)
            node_amp = base_blast_g / (1.0 + 0.08 * dist)
            # Hit node within 0-2 minutes (sharp peak, 1-2 min decay)
            t_hit = step_idx
            if t_hit < n_steps:
                data[nid]["vibration"][t_hit] += node_amp
                data[nid]["piezo_peak"][t_hit] += node_amp * 0.8
                data[nid]["piezo_rms"][t_hit] += node_amp * 0.3
                data[nid]["piezo_peak_to_peak"][t_hit] += node_amp * 1.6
            if t_hit + 1 < n_steps:
                data[nid]["vibration"][t_hit + 1] += node_amp * 0.3
                data[nid]["piezo_peak"][t_hit + 1] += node_amp * 0.2
                data[nid]["piezo_peak_to_peak"][t_hit + 1] += node_amp * 0.4

        return blast_event

    # Scenario Implementations
    if scenario_type == "blast":
        ground_truth["is_hazard"] = False
        t_event = int(rng.integers(60, 300))
        is_scheduled = bool(rng.random() < 0.70)
        ground_truth["onset_time"] = timestamps[t_event]
        ground_truth["affected_nodes"] = list(node_ids)  # Hits all 4 nodes
        add_blast_event(t_event, is_scheduled)

    elif scenario_type == "machinery_impact":
        ground_truth["is_hazard"] = False
        t_event = int(rng.integers(60, 300))
        chosen_node = str(rng.choice(node_ids))
        ground_truth["onset_time"] = timestamps[t_event]
        ground_truth["affected_nodes"] = [chosen_node]  # Hits ONE node only
        ground_truth["events"].append({
            "type": "machinery_impact",
            "time": timestamps[t_event],
            "node_id": chosen_node
        })
        impact_amp = float(rng.uniform(0.5, 2.0))
        data[chosen_node]["vibration"][t_event] += impact_amp
        data[chosen_node]["piezo_peak"][t_event] += impact_amp * 0.6
        data[chosen_node]["piezo_peak_to_peak"][t_event] += impact_amp * 1.2
        # No lasting tilt or distance change, other nodes unaffected

    elif scenario_type == "rain_tilt":
        ground_truth["is_hazard"] = False
        t_start = int(rng.integers(30, 90))
        t_duration = int(rng.integers(60, 180))
        ground_truth["onset_time"] = timestamps[t_start]
        ground_truth["affected_nodes"] = list(node_ids)  # Common mode across all nodes
        ground_truth["events"].append({
            "type": "rain_tilt",
            "time": timestamps[t_start],
            "duration_min": t_duration
        })
        drift_mag_x = float(rng.uniform(2.0, 10.0)) * rng.choice([-1, 1])
        drift_mag_y = float(rng.uniform(2.0, 10.0)) * rng.choice([-1, 1])

        for t in range(t_start, min(n_steps, t_start + t_duration)):
            prog = (t - t_start) / t_duration
            factor = math.sin(math.pi * prog)  # Rises and partially reverts
            for nid in node_ids:
                node_var = float(rng.uniform(0.85, 1.15))
                data[nid]["tilt_x"][t] += drift_mag_x * factor * node_var
                data[nid]["tilt_y"][t] += drift_mag_y * factor * node_var
        # No vibration anomaly

    elif scenario_type == "sensor_fault":
        ground_truth["is_hazard"] = False
        t_start = int(rng.integers(60, 240))
        chosen_node = str(rng.choice(node_ids))
        flag_fault = bool(rng.random() < 0.50)  # 50% with fault flag, 50% without (silent)
        ground_truth["onset_time"] = timestamps[t_start]
        ground_truth["affected_nodes"] = [chosen_node]
        ground_truth["events"].append({
            "type": "sensor_fault",
            "time": timestamps[t_start],
            "node_id": chosen_node,
            "has_fault_flag": flag_fault
        })
        fault_type = rng.choice(["rail_distance", "rail_tilt", "spikes"])
        for t in range(t_start, n_steps):
            if flag_fault:
                if fault_type == "rail_distance":
                    status_flags[chosen_node]["hc_sr04_status"][t] = "fault"
                else:
                    status_flags[chosen_node]["mpu6050_status"][t] = "fault"

            if fault_type == "rail_distance":
                data[chosen_node]["distance"][t] = 0.0 if rng.random() < 0.5 else 450.0
            elif fault_type == "rail_tilt":
                data[chosen_node]["tilt_x"][t] = 85.0
                data[chosen_node]["tilt_y"][t] = -85.0
            else:
                data[chosen_node]["tilt_x"][t] += float(rng.uniform(-30.0, 30.0))
                data[chosen_node]["distance"][t] += float(rng.uniform(-50.0, 50.0))

    elif scenario_type == "stuck_sensor":
        ground_truth["is_hazard"] = False
        t_start = int(rng.integers(60, 180))  # At least 2+ hours frozen
        chosen_node = str(rng.choice(node_ids))
        ground_truth["onset_time"] = timestamps[t_start]
        ground_truth["affected_nodes"] = [chosen_node]
        ground_truth["events"].append({
            "type": "stuck_sensor",
            "time": timestamps[t_start],
            "node_id": chosen_node,
            "has_fault_flag": False
        })
        freeze_vals = {
            m: data[chosen_node][m][t_start] for m in ["tilt_x", "tilt_y", "vibration", "distance", "piezo_peak", "piezo_rms", "piezo_peak_to_peak"]
        }
        for t in range(t_start, n_steps):
            for m in freeze_vals:
                data[chosen_node][m][t] = freeze_vals[m]
            # Silent failure: status remains 'ok'

    elif scenario_type == "slow_creep":
        ground_truth["is_hazard"] = True
        ground_truth["collapse_time"] = None
        t_onset = int(rng.integers(40, 100))
        ground_truth["onset_time"] = timestamps[t_onset]

        # 1-2 adjacent nodes
        pair_candidates = [["NODE_01", "NODE_02"], ["NODE_02", "NODE_03"], ["NODE_03", "NODE_04"], ["NODE_04", "NODE_01"], ["NODE_01"]]
        chosen_idx = int(rng.integers(0, len(pair_candidates)))
        affected = list(pair_candidates[chosen_idx])
        ground_truth["affected_nodes"] = affected
        ground_truth["events"].append({
            "type": "slow_creep",
            "time": timestamps[t_onset],
            "affected_nodes": affected
        })

        hazard_window_len = n_steps - t_onset
        # Fixed thresholds for demo: tilt 15 deg, vibration 1.0 g, distance change 2.0 cm
        # Must stay below thresholds for at least first half of hazard window
        # In the first half (prog <= 0.5), delta tilt <= max_tilt * 0.5; delta dist <= max_dist_delta * 0.5
        max_tilt = float(rng.uniform(16.0, 18.0))
        max_dist_delta = float(rng.uniform(1.5, 1.8))

        for nid in affected:
            for t in range(t_onset, n_steps):
                prog = (t - t_onset) / hazard_window_len
                # Linear creep
                data[nid]["tilt_x"][t] += max_tilt * prog
                data[nid]["tilt_y"][t] += (max_tilt * 0.7) * prog
                data[nid]["distance"][t] += max_dist_delta * prog
                # Rising piezo micro-crack activity
                piezo_inc = 0.05 * prog + float(rng.uniform(0.0, 0.02 * prog))
                data[nid]["piezo_peak"][t] += piezo_inc
                data[nid]["piezo_peak_to_peak"][t] += piezo_inc * 2.0
                data[nid]["vibration"][t] += 0.03 * prog

    elif scenario_type == "accelerating_creep":
        ground_truth["is_hazard"] = True
        t_onset = int(rng.integers(40, 90))
        t_collapse = int(rng.integers(t_onset + 120, n_steps - 20))
        ground_truth["onset_time"] = timestamps[t_onset]
        ground_truth["collapse_time"] = timestamps[t_collapse]

        pair_candidates = [["NODE_01", "NODE_02"], ["NODE_02", "NODE_03"], ["NODE_03", "NODE_04"], ["NODE_04", "NODE_01"]]
        chosen_idx = int(rng.integers(0, len(pair_candidates)))
        affected = list(pair_candidates[chosen_idx])
        ground_truth["affected_nodes"] = affected
        ground_truth["events"].append({
            "type": "accelerating_creep",
            "time": timestamps[t_onset],
            "collapse_time": timestamps[t_collapse],
            "affected_nodes": affected
        })

        creep_len = t_collapse - t_onset
        exponent = float(rng.uniform(2.5, 3.5))

        for nid in affected:
            for t in range(t_onset, t_collapse):
                prog = (t - t_onset) / creep_len
                accel = prog ** exponent
                data[nid]["tilt_x"][t] += 12.0 * accel
                data[nid]["tilt_y"][t] += 8.0 * accel
                data[nid]["distance"][t] += 1.8 * accel
                piezo_inc = 0.15 * accel + float(rng.uniform(0.0, 0.05 * accel))
                data[nid]["piezo_peak"][t] += piezo_inc
                data[nid]["piezo_peak_to_peak"][t] += piezo_inc * 2.0
                data[nid]["vibration"][t] += 0.08 * accel

            # At and after collapse: sudden catastrophic jump
            for t in range(t_collapse, n_steps):
                data[nid]["tilt_x"][t] += float(rng.uniform(35.0, 50.0))
                data[nid]["tilt_y"][t] += float(rng.uniform(25.0, 40.0))
                data[nid]["distance"][t] += float(rng.uniform(15.0, 30.0))
                data[nid]["vibration"][t] += float(rng.uniform(1.2, 3.0))
                data[nid]["piezo_peak"][t] += float(rng.uniform(0.5, 1.5))
                data[nid]["piezo_peak_to_peak"][t] += float(rng.uniform(1.0, 3.0))

    # Handle combo overlay blast on top of creep (scheduled blast during real creep)
    if overlay_blast and scenario_type in ("slow_creep", "accelerating_creep"):
        t_blast = int(rng.integers(120, 240))
        add_blast_event(t_blast, is_scheduled=True)

    # Build typed NodeReading list
    readings: List[NodeReading] = []
    for t in range(n_steps):
        ts = timestamps[t]
        for nid in node_ids:
            r = NodeReading(
                node_id=nid,
                timestamp=ts,
                tilt_x=float(round(data[nid]["tilt_x"][t], 4)),
                tilt_y=float(round(data[nid]["tilt_y"][t], 4)),
                vibration=float(round(data[nid]["vibration"][t], 4)),
                distance=float(round(data[nid]["distance"][t], 4)),
                mpu6050_status=status_flags[nid]["mpu6050_status"][t],
                hc_sr04_status=status_flags[nid]["hc_sr04_status"][t],
                ads1115_status=status_flags[nid]["ads1115_status"][t],
                piezo_peak=float(round(data[nid]["piezo_peak"][t], 4)),
                piezo_rms=float(round(data[nid]["piezo_rms"][t], 4)),
                piezo_peak_to_peak=float(round(data[nid]["piezo_peak_to_peak"][t], 4)),
            )
            readings.append(r)

    return readings, ground_truth
