"""Scenario simulator for the Canary Analyst sandbox.

Generates synthetic 4-node geotechnical time series under the generator's NodeReading schema.
Background noise is calibrated from generator/noise_profile.json using AR(1) series generation.
"""

from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from generator.scenarios import (
    NODE_COORDS,
    generate_ar1_series,
    load_noise_profile,
)
from generator.schema import NodeReading

ALLOWED_PRESETS = {
    "single_node_move",
    "common_mode_tilt",
    "vibration_pulse_all_nodes",
    "single_node_spike",
    "silent_sensor_fault",
    "random",
}

PRESET_CHOICES = [
    "single_node_move",
    "common_mode_tilt",
    "vibration_pulse_all_nodes",
    "single_node_spike",
    "silent_sensor_fault",
]

NODE_IDS = ["NODE_01", "NODE_02", "NODE_03", "NODE_04"]


def clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


def build_scenario(
    params: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Build a synthetic scenario returning (readings, meta).

    readings: List of dicts in NodeReading schema format.
    meta: Dict in generator scenario metadata format with empty blast_schedule.
    """
    params = dict(params or {})

    # Seed resolution
    resolved_seed = seed if seed is not None else params.get("seed")
    if resolved_seed is None:
        resolved_seed = int(np.random.randint(0, 2**31 - 1))
    else:
        resolved_seed = int(resolved_seed)

    rng = np.random.Generator(np.random.PCG64(resolved_seed))

    preset_raw = str(params.get("preset", "single_node_move")).strip().lower()
    if preset_raw not in ALLOWED_PRESETS:
        preset_raw = "single_node_move"

    if preset_raw == "random":
        preset = str(rng.choice(PRESET_CHOICES))
        node = str(rng.choice(NODE_IDS))
        onset_minute = int(rng.integers(35, 75))
        rise_minutes = int(rng.integers(0, 30))
        tilt_deg = float(rng.uniform(0.0, 45.0))
        vibration_g = float(rng.uniform(0.0, 5.0))
        distance_cm = float(rng.uniform(0.0, 20.0))
        duration_minutes = int(rng.integers(60, 121))
    else:
        preset = preset_raw

        node_raw = params.get("node", "NODE_01")
        if node_raw not in NODE_IDS:
            node = "NODE_01"
        else:
            node = str(node_raw)

        # Duration: 60 to 120 minutes (default 90)
        dur_raw = params.get("duration_minutes", 90)
        try:
            duration_minutes = int(clamp(float(dur_raw), 60, 120))
        except (ValueError, TypeError):
            duration_minutes = 90

        # Onset minute: 35 or later, clamped up to duration_minutes - 1
        onset_raw = params.get("onset_minute", 35)
        try:
            onset_minute = int(clamp(float(onset_raw), 35, max(35, duration_minutes - 1)))
        except (ValueError, TypeError):
            onset_minute = 35

        # Rise minutes: >= 0 (0 = sudden)
        rise_raw = params.get("rise_minutes", 0)
        try:
            rise_minutes = int(max(0, float(rise_raw)))
        except (ValueError, TypeError):
            rise_minutes = 0

        # Physical perturbations clamped to specification ranges
        tilt_raw = params.get("tilt_deg", 0.0)
        try:
            tilt_deg = float(clamp(float(tilt_raw), 0.0, 45.0))
        except (ValueError, TypeError):
            tilt_deg = 0.0

        vib_raw = params.get("vibration_g", 0.0)
        try:
            vibration_g = float(clamp(float(vib_raw), 0.0, 5.0))
        except (ValueError, TypeError):
            vibration_g = 0.0

        dist_raw = params.get("distance_cm", 0.0)
        try:
            distance_cm = float(clamp(float(dist_raw), 0.0, 20.0))
        except (ValueError, TypeError):
            distance_cm = 0.0

    noise_profile = load_noise_profile()
    noise_source = noise_profile.get("source", "defaults")
    continuous_noise = noise_profile.get("continuous_step_noise", {})

    n_steps = duration_minutes
    start_time_iso = params.get("start_time_iso", "2026-10-27T08:00:00Z")
    start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
    timestamps = [
        (start_dt + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(n_steps)
    ]

    # Generate AR(1) baseline for each node mirroring generator/scenarios.py
    data: Dict[str, Dict[str, np.ndarray]] = {}
    status_flags: Dict[str, Dict[str, List[str]]] = {}

    for nid in NODE_IDS:
        node_prof = noise_profile["nodes"].get(nid, noise_profile["overall"])
        data[nid] = {}
        for metric in [
            "tilt_x",
            "tilt_y",
            "vibration",
            "distance",
            "piezo_peak",
            "piezo_rms",
            "piezo_peak_to_peak",
        ]:
            p = node_prof[metric]
            if metric == "distance":
                baseline_mean = p.get("mean", 18.0)
            elif metric in ("tilt_x", "tilt_y"):
                baseline_mean = 0.0
            elif metric == "vibration":
                baseline_mean = min(p.get("mean", 0.04), 0.065)
            else:
                baseline_mean = p.get("mean", 0.02)

            phi = p.get("autocorr_lag1", 0.5)
            if nid in continuous_noise and metric in continuous_noise[nid]:
                step_noise = continuous_noise[nid][metric]
                sim_std = step_noise / math.sqrt(max(0.1, 1.0 - phi**2))
            else:
                sim_std = p.get("std", 0.15)
                if metric == "distance":
                    sim_std = min(sim_std, 0.35)
                elif metric == "vibration":
                    sim_std = min(sim_std, 0.015)

            if metric == "distance":
                sim_std = min(sim_std, 0.35)
            elif metric in ("tilt_x", "tilt_y"):
                sim_std = min(sim_std, 0.20)
            elif metric == "vibration":
                sim_std = min(sim_std, 0.015)

            series = generate_ar1_series(n_steps, baseline_mean, sim_std, phi, rng)
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

    # Inject preset mechanics
    def ramp_factor(t: int, t_start: int, rise: int) -> float:
        if t < t_start:
            return 0.0
        if rise <= 0:
            return 1.0
        return min(1.0, (t - t_start) / float(rise))

    if preset == "single_node_move":
        # Sustained movement on a single node (tilt, distance, vibration, piezo)
        # Use exact provided params: tilt_deg, distance_cm, vibration_g
        eff_tilt = tilt_deg
        eff_dist = distance_cm
        eff_vib = vibration_g
        for t in range(onset_minute, n_steps):
            rf = ramp_factor(t, onset_minute, rise_minutes)
            data[node]["tilt_x"][t] += eff_tilt * rf * 0.8
            data[node]["tilt_y"][t] += eff_tilt * rf * 0.6
            data[node]["distance"][t] += eff_dist * rf
            data[node]["vibration"][t] += eff_vib * rf
            if eff_tilt > 0 or eff_dist > 0:
                piezo_add = 0.02 * rf
                data[node]["piezo_peak"][t] += piezo_add
                data[node]["piezo_peak_to_peak"][t] += piezo_add * 2.0

    elif preset == "common_mode_tilt":
        # Environmental rain-like drift across all nodes simultaneously
        eff_tilt = tilt_deg if tilt_deg > 0.0 else 20.0
        for nid in NODE_IDS:
            node_var = float(rng.uniform(0.9, 1.1))
            for t in range(onset_minute, n_steps):
                rf = ramp_factor(t, onset_minute, rise_minutes)
                data[nid]["tilt_x"][t] += eff_tilt * rf * 0.7 * node_var
                data[nid]["tilt_y"][t] += eff_tilt * rf * 0.7 * node_var

    elif preset == "vibration_pulse_all_nodes":
        # Transient blast-like pulse hitting all nodes
        eff_vib = vibration_g if vibration_g > 0.0 else 2.5
        t_hit = onset_minute
        bx, by = 10.0, 10.0
        for nid, (nx, ny) in NODE_COORDS.items():
            dist = math.hypot(nx - bx, ny - by)
            node_amp = eff_vib / (1.0 + 0.08 * dist)
            if t_hit < n_steps:
                data[nid]["vibration"][t_hit] += node_amp
                data[nid]["piezo_peak"][t_hit] += node_amp * 0.8
                data[nid]["piezo_rms"][t_hit] += node_amp * 0.3
                data[nid]["piezo_peak_to_peak"][t_hit] += node_amp * 1.6
            if t_hit + 1 < n_steps:
                data[nid]["vibration"][t_hit + 1] += node_amp * 0.3
                data[nid]["piezo_peak"][t_hit + 1] += node_amp * 0.2
                data[nid]["piezo_peak_to_peak"][t_hit + 1] += node_amp * 0.4

    elif preset == "single_node_spike":
        # Machinery-like mechanical spike on single node, transient (1-2 min)
        eff_vib = vibration_g if vibration_g > 0.0 else 1.8
        t_hit = onset_minute
        if t_hit < n_steps:
            data[node]["vibration"][t_hit] += eff_vib
            data[node]["piezo_peak"][t_hit] += eff_vib * 0.6
            data[node]["piezo_peak_to_peak"][t_hit] += eff_vib * 1.2
        if t_hit + 1 < n_steps:
            data[node]["vibration"][t_hit + 1] += eff_vib * 0.2

    elif preset == "silent_sensor_fault":
        # Silent rail-value fault on a single node; status flags stay 'ok'
        eff_tilt = tilt_deg if tilt_deg > 0.0 else 85.0
        for t in range(onset_minute, n_steps):
            data[node]["tilt_x"][t] = eff_tilt
            data[node]["tilt_y"][t] = -eff_tilt
            data[node]["distance"][t] = 450.0

    # Build typed readings list
    readings: List[Dict[str, Any]] = []
    for t in range(n_steps):
        ts = timestamps[t]
        for nid in NODE_IDS:
            nr = NodeReading(
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
            readings.append(nr.model_dump())

    scenario_id = params.get("scenario_id", f"SANDBOX_{resolved_seed}")
    meta: Dict[str, Any] = {
        "scenario_id": scenario_id,
        "type": preset,
        "seed": resolved_seed,
        "is_hazard": preset in ("single_node_move", "accelerating_creep", "slow_creep"),
        "onset_time": timestamps[onset_minute] if onset_minute < n_steps else None,
        "collapse_time": None,
        "affected_nodes": [node] if preset != "common_mode_tilt" and preset != "vibration_pulse_all_nodes" else list(NODE_IDS),
        "events": [],
        "blast_schedule": [],  # Strictly empty blast schedule per specification
        "node_coordinates_m": NODE_COORDS,
        "noise_profile_source": noise_source,
        "simulated": True,
        "overlay_blast": False,
        "applied_params": {
            "preset": preset,
            "node": node,
            "onset_minute": onset_minute,
            "rise_minutes": rise_minutes,
            "tilt_deg": tilt_deg,
            "vibration_g": vibration_g,
            "distance_cm": distance_cm,
            "duration_minutes": duration_minutes,
            "seed": resolved_seed,
        },
    }

    return readings, meta
