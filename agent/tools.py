from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _format_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_evidence_id(tool_name: str, payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True)
    h = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:8]
    return f"ev_{tool_name}_{h}"


def _filter_readings(readings: List[Dict[str, Any]], as_of: str) -> List[Dict[str, Any]]:
    """Strictly filter readings to rows with timestamp <= as_of (no lookahead)."""
    as_of_dt = _parse_ts(as_of)
    return [r for r in readings if _parse_ts(r["timestamp"]) <= as_of_dt]


def _ols_linear_regression(series: List[float]) -> Tuple[float, float, float, float]:
    """Return slope, raw t_stat, t_adj, r_squared."""
    n = len(series)
    if n < 3:
        return 0.0, 0.0, 0.0, 0.0
    x = np.arange(n, dtype=float)
    y = np.array(series, dtype=float)
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    ss_xx = float(np.sum((x - x_mean)**2))
    ss_yy = float(np.sum((y - y_mean)**2))
    if ss_xx == 0.0:
        return 0.0, 0.0, 0.0, 0.0
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / ss_xx)
    residuals = y - (y_mean + slope * (x - x_mean))
    ss_res = float(np.sum(residuals**2))
    r2 = 1.0 - (ss_res / ss_yy) if ss_yy > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))

    s_err2 = ss_res / (n - 2) if n > 2 else 0.0
    se_slope = math.sqrt(s_err2 / ss_xx) if s_err2 > 0 and ss_xx > 0 else 1e-9
    t_stat = slope / se_slope if se_slope > 0 else 0.0

    # Autocorrelation adjustment: lag-1 autocorrelation r of residuals
    # t_adj = t * sqrt((1 - r) / (1 + r)) with r clipped to [0, 0.95]
    res_0 = residuals[:-1]
    res_1 = residuals[1:]
    denom = float(np.sum(res_0**2))
    r = float(np.sum(res_0 * res_1) / denom) if denom > 0 else 0.0
    r_clipped = max(0.0, min(0.95, r))
    adj_factor = math.sqrt((1.0 - r_clipped) / (1.0 + r_clipped))
    t_adj = t_stat * adj_factor

    return float(round(slope, 6)), float(round(t_stat, 4)), float(round(t_adj, 4)), float(round(r2, 4))


def _extract_channel_value(r: Dict[str, Any], channel: str, baseline: Optional[Dict[str, float]] = None) -> float:
    c = channel.lower()
    if c == "tilt_x":
        return float(r.get("tilt_x", 0.0))
    elif c == "tilt_y":
        return float(r.get("tilt_y", 0.0))
    elif c in ("tilt", "tilt_magnitude"):
        if baseline:
            dx = r.get("tilt_x", 0.0) - baseline.get("tilt_x", 0.0)
            dy = r.get("tilt_y", 0.0) - baseline.get("tilt_y", 0.0)
            return float(math.hypot(dx, dy))
        return float(math.hypot(r.get("tilt_x", 0.0), r.get("tilt_y", 0.0)))
    elif c == "vibration":
        return float(r.get("vibration", 0.0))
    elif c == "distance":
        if baseline:
            return float(abs(r.get("distance", 0.0) - baseline.get("distance", 0.0)))
        return float(r.get("distance", 0.0))
    elif c == "piezo_peak":
        return float(r.get("piezo_peak", 0.0))
    elif c == "piezo_rms":
        return float(r.get("piezo_rms", 0.0))
    elif c == "piezo_peak_to_peak":
        return float(r.get("piezo_peak_to_peak", 0.0))
    else:
        raise ValueError(f"Unknown channel '{channel}'")


def get_node_history(
    readings: List[Dict[str, Any]],
    as_of: str,
    node_id: str,
    channel: str,
    minutes_back: int
) -> Dict[str, Any]:
    """Retrieve historical summary statistics and downsampled series for a node."""
    valid_readings = _filter_readings(readings, as_of)
    node_readings = [r for r in valid_readings if r.get("node_id") == node_id]
    node_readings.sort(key=lambda r: _parse_ts(r["timestamp"]))

    if not node_readings:
        res: Dict[str, Any] = {
            "node_id": node_id,
            "channel": channel,
            "count": 0,
            "error": "No readings found for node prior to as_of"
        }
        res["evidence_id"] = _make_evidence_id("get_node_history", res)
        return res

    # Establish node baseline from first 30 readings
    first30 = node_readings[:30]
    baseline = {
        "tilt_x": float(np.median([r["tilt_x"] for r in first30])),
        "tilt_y": float(np.median([r["tilt_y"] for r in first30])),
        "distance": float(np.median([r["distance"] for r in first30])),
        "vibration": float(np.median([r["vibration"] for r in first30])),
        "piezo_peak": float(np.median([r["piezo_peak"] for r in first30])),
    }

    as_of_dt = _parse_ts(as_of)
    window_start = as_of_dt - timedelta(minutes=minutes_back)
    window_readings = [r for r in node_readings if _parse_ts(r["timestamp"]) >= window_start]

    if not window_readings:
        window_readings = [node_readings[-1]]

    values = [_extract_channel_value(r, channel, baseline) for r in window_readings]
    v_arr = np.array(values, dtype=float)

    # Slope
    slope, t_stat, t_adj, r2 = _ols_linear_regression(values)

    # Baseline noise std
    first30_vals = [_extract_channel_value(r, channel, baseline) for r in first30]
    base_std = float(round(float(np.std(first30_vals)), 4)) if len(first30_vals) > 1 else 0.01

    # Peak value and time
    peak_idx = int(np.argmax(v_arr))
    peak_val = float(round(float(v_arr[peak_idx]), 4))
    peak_time = window_readings[peak_idx]["timestamp"]

    # Check whether it returned to baseline within 3*base_std
    nominal_baseline_val = float(np.median(first30_vals))
    tolerance = max(0.02, 3.0 * base_std)
    returned_to_baseline = False
    return_time = None

    if peak_idx < len(values) - 1:
        for r_idx in range(peak_idx + 1, len(values)):
            if abs(values[r_idx] - nominal_baseline_val) <= tolerance:
                returned_to_baseline = True
                return_time = window_readings[r_idx]["timestamp"]
                break

    # Last 10 values downsampled
    n_sample = min(10, len(values))
    indices = np.linspace(0, len(values) - 1, n_sample, dtype=int)
    downsampled = [
        {"time": window_readings[i]["timestamp"], "value": float(round(values[i], 4))}
        for i in indices
    ]

    res = {
        "node_id": node_id,
        "channel": channel,
        "as_of": as_of,
        "window_minutes": minutes_back,
        "count": len(values),
        "min": float(round(float(np.min(v_arr)), 4)),
        "max": float(round(float(np.max(v_arr)), 4)),
        "mean": float(round(float(np.mean(v_arr)), 4)),
        "slope_per_min": slope,
        "baseline_noise_std": base_std,
        "peak_value": peak_val,
        "peak_time": peak_time,
        "returned_to_baseline": returned_to_baseline,
        "return_time": return_time,
        "last_10_downsampled": downsampled,
    }
    res["evidence_id"] = _make_evidence_id("get_node_history", res)
    return res


def compare_neighbor_nodes(
    readings: List[Dict[str, Any]],
    as_of: str,
    channel: str,
    window_minutes: int,
    node_coordinates: Optional[Dict[str, Tuple[float, float]]] = None
) -> Dict[str, Any]:
    """Compare cross-node spatial dynamics, correlation, timing, and amplitude decay."""
    valid_readings = _filter_readings(readings, as_of)
    as_of_dt = _parse_ts(as_of)
    window_start = as_of_dt - timedelta(minutes=window_minutes)

    # Group readings by node
    node_data: Dict[str, List[Dict[str, Any]]] = {}
    for r in valid_readings:
        nid = r.get("node_id", "")
        if nid not in node_data:
            node_data[nid] = []
        node_data[nid].append(r)

    # Baseline and window series per node
    node_changes: Dict[str, float] = {}
    node_peaks: Dict[str, Dict[str, Any]] = {}
    node_series: Dict[str, List[float]] = {}

    for nid, rlist in node_data.items():
        rlist.sort(key=lambda r: _parse_ts(r["timestamp"]))
        first30 = rlist[:30]
        baseline = {
            "tilt_x": float(np.median([r["tilt_x"] for r in first30])),
            "tilt_y": float(np.median([r["tilt_y"] for r in first30])),
            "distance": float(np.median([r["distance"] for r in first30])),
            "vibration": float(np.median([r["vibration"] for r in first30])),
            "piezo_peak": float(np.median([r["piezo_peak"] for r in first30])),
        }
        win_r = [r for r in rlist if _parse_ts(r["timestamp"]) >= window_start]
        if not win_r:
            win_r = [rlist[-1]]

        vals = [_extract_channel_value(r, channel, baseline) for r in win_r]
        node_series[nid] = vals
        base_val = float(np.median([_extract_channel_value(r, channel, baseline) for r in first30]))
        curr_val = vals[-1]
        node_changes[nid] = float(round(abs(curr_val - base_val), 4))

        p_idx = int(np.argmax(vals))
        node_peaks[nid] = {
            "peak_val": float(round(vals[p_idx], 4)),
            "peak_time": win_r[p_idx]["timestamp"],
            "peak_step": p_idx
        }

    # Cross-node correlation matrix
    common_len = min((len(s) for s in node_series.values()), default=0)
    corr_matrix: Dict[str, Dict[str, float]] = {}
    nodes = sorted(list(node_series.keys()))

    for n1 in nodes:
        corr_matrix[n1] = {}
        s1 = np.array(node_series[n1][-common_len:], dtype=float) if common_len > 1 else np.array([])
        for n2 in nodes:
            if n1 == n2:
                corr_matrix[n1][n2] = 1.0
            elif common_len > 1:
                s2 = np.array(node_series[n2][-common_len:], dtype=float)
                std1, std2 = np.std(s1), np.std(s2)
                if std1 > 1e-6 and std2 > 1e-6:
                    c = float(np.corrcoef(s1, s2)[0, 1])
                    corr_matrix[n1][n2] = float(round(c, 4))
                else:
                    corr_matrix[n1][n2] = 0.0
            else:
                corr_matrix[n1][n2] = 0.0

    # Determine which node moved first (earliest peak or first significant rise)
    earliest_node = min(node_peaks.keys(), key=lambda n: node_peaks[n]["peak_time"]) if node_peaks else "none"
    peak_times = {n: node_peaks[n]["peak_time"] for n in node_peaks}

    # Amplitude fall with distance from strongest node
    coords = node_coordinates or {
        "NODE_01": (0.0, 0.0),
        "NODE_02": (20.0, 0.0),
        "NODE_03": (20.0, 20.0),
        "NODE_04": (0.0, 20.0),
    }

    strongest_node = max(node_changes.keys(), key=lambda n: node_changes[n]) if node_changes else "none"
    decays_with_distance = False
    if strongest_node in coords and len(node_changes) >= 3:
        sx, sy = coords[strongest_node]
        dist_and_amp = []
        for n, change in node_changes.items():
            if n in coords:
                d = math.hypot(coords[n][0] - sx, coords[n][1] - sy)
                dist_and_amp.append((d, change))
        # Check negative correlation between distance from epicenter and amplitude
        dist_and_amp.sort(key=lambda x: x[0])
        distances = [x[0] for x in dist_and_amp]
        amps = [x[1] for x in dist_and_amp]
        if np.std(distances) > 0 and np.std(amps) > 0:
            c = np.corrcoef(distances, amps)[0, 1]
            decays_with_distance = bool(c < -0.5)

    res = {
        "channel": channel,
        "as_of": as_of,
        "window_minutes": window_minutes,
        "per_node_change": node_changes,
        "cross_node_correlation": corr_matrix,
        "strongest_node": strongest_node,
        "first_moved_node": earliest_node,
        "peak_times": peak_times,
        "amplitude_decays_with_distance": decays_with_distance,
    }
    res["evidence_id"] = _make_evidence_id("compare_neighbor_nodes", res)
    return res


def get_sensor_health(
    readings: List[Dict[str, Any]],
    as_of: str,
    node_id: str,
    noise_profile_path: Optional[str] = "generator/noise_profile.json"
) -> Dict[str, Any]:
    """Diagnose sensor health, stuck counts, rail limits, and noise ratio."""
    valid_readings = _filter_readings(readings, as_of)
    node_readings = [r for r in valid_readings if r.get("node_id") == node_id]
    node_readings.sort(key=lambda r: _parse_ts(r["timestamp"]))

    if not node_readings:
        res: Dict[str, Any] = {
            "node_id": node_id,
            "error": "No readings found prior to as_of"
        }
        res["evidence_id"] = _make_evidence_id("get_sensor_health", res)
        return res

    latest = node_readings[-1]
    status_flags = {
        "mpu6050_status": latest.get("mpu6050_status", "ok"),
        "hc_sr04_status": latest.get("hc_sr04_status", "ok"),
        "ads1115_status": latest.get("ads1115_status", "ok"),
    }

    # Count consecutive constant readings at tail
    constant_count = 1
    tail_r = node_readings[-1]
    for r in reversed(node_readings[:-1]):
        if (r.get("tilt_x") == tail_r.get("tilt_x") and
            r.get("tilt_y") == tail_r.get("tilt_y") and
            r.get("vibration") == tail_r.get("vibration") and
            r.get("distance") == tail_r.get("distance")):
            constant_count += 1
        else:
            break

    # Fraction of rail values in last 60 readings
    last60 = node_readings[-60:]
    rail_count = 0
    for r in last60:
        d = r.get("distance", 0.0)
        if d <= 0.0 or d >= 400.0 or abs(r.get("tilt_x", 0.0)) >= 85.0:
            rail_count += 1
    rail_fraction = float(round(rail_count / len(last60), 4))

    # Max step change in distance and tilt over last 60 readings
    max_step_dist = 0.0
    max_step_tilt = 0.0
    for i in range(1, len(last60)):
        d_step = abs(last60[i].get("distance", 0.0) - last60[i - 1].get("distance", 0.0))
        t_step = math.hypot(
            last60[i].get("tilt_x", 0.0) - last60[i - 1].get("tilt_x", 0.0),
            last60[i].get("tilt_y", 0.0) - last60[i - 1].get("tilt_y", 0.0)
        )
        max_step_dist = max(max_step_dist, d_step)
        max_step_tilt = max(max_step_tilt, t_step)

    # Noise ratio versus calibrated noise profile
    calib_std = 0.20
    p = Path(noise_profile_path) if noise_profile_path else None
    if p and p.exists():
        try:
            with open(p) as f:
                np_data = json.load(f)
            node_prof = np_data.get("nodes", {}).get(node_id, np_data.get("overall", {}))
            calib_std = node_prof.get("tilt_x", {}).get("std", 0.20)
        except Exception:
            pass

    obs_std = float(np.std([r.get("tilt_x", 0.0) for r in last60])) if len(last60) > 1 else 0.0
    noise_ratio = float(round(obs_std / calib_std, 4)) if calib_std > 0 else 1.0

    res = {
        "node_id": node_id,
        "as_of": as_of,
        "status_flags": status_flags,
        "consecutive_constant_readings": constant_count,
        "rail_value_fraction": rail_fraction,
        "max_step_change_distance_cm": float(round(max_step_dist, 4)),
        "max_step_change_tilt_deg": float(round(max_step_tilt, 4)),
        "noise_ratio_versus_profile": noise_ratio,
        "is_healthy": (
            all(v == "ok" for v in status_flags.values()) and
            constant_count < 30 and
            rail_fraction < 0.10 and
            max_step_dist < 10.0
        )
    }
    res["evidence_id"] = _make_evidence_id("get_sensor_health", res)
    return res


def check_blast_schedule(
    blast_schedule: List[Dict[str, Any]],
    as_of: str
) -> Dict[str, Any]:
    """Check whether a planned quarry blast is scheduled within +-30 minutes of as_of."""
    as_of_dt = _parse_ts(as_of)
    within_30m: List[Dict[str, Any]] = []
    past_blasts: List[datetime] = []

    for item in blast_schedule:
        s_time_dt = _parse_ts(item.get("scheduled_time", item.get("time", as_of)))
        diff_sec = (s_time_dt - as_of_dt).total_seconds()
        diff_min = diff_sec / 60.0

        if abs(diff_min) <= 30.0:
            within_30m.append({
                "scheduled_time": item.get("scheduled_time", item.get("time")),
                "delta_minutes": float(round(diff_min, 1)),
                "location": item.get("location", "Quarry Face")
            })

        if diff_sec <= 0:
            past_blasts.append(s_time_dt)

    time_since_last_min = None
    if past_blasts:
        latest_past = max(past_blasts)
        time_since_last_min = float(round((as_of_dt - latest_past).total_seconds() / 60.0, 1))

    res = {
        "as_of": as_of,
        "blast_scheduled_within_30min": len(within_30m) > 0,
        "nearby_blasts": within_30m,
        "time_since_last_scheduled_blast_min": time_since_last_min,
    }
    res["evidence_id"] = _make_evidence_id("check_blast_schedule", res)
    return res


def project_time_to_threshold(
    readings: List[Dict[str, Any]],
    as_of: str,
    node_id: str,
    channel: str,
    fit_minutes: int,
    threshold: Optional[float] = None
) -> Dict[str, Any]:
    """Fit OLS trend and project estimated minutes until crossing demonstration threshold."""
    valid_readings = _filter_readings(readings, as_of)
    node_readings = [r for r in valid_readings if r.get("node_id") == node_id]
    node_readings.sort(key=lambda r: _parse_ts(r["timestamp"]))

    if not node_readings:
        res: Dict[str, Any] = {
            "node_id": node_id,
            "channel": channel,
            "error": "No readings available"
        }
        res["evidence_id"] = _make_evidence_id("project_time_to_threshold", res)
        return res

    first30 = node_readings[:30]
    baseline = {
        "tilt_x": float(np.median([r["tilt_x"] for r in first30])),
        "tilt_y": float(np.median([r["tilt_y"] for r in first30])),
        "distance": float(np.median([r["distance"] for r in first30])),
        "vibration": float(np.median([r["vibration"] for r in first30])),
        "piezo_peak": float(np.median([r["piezo_peak"] for r in first30])),
    }

    as_of_dt = _parse_ts(as_of)
    window_start = as_of_dt - timedelta(minutes=fit_minutes)
    win_r = [r for r in node_readings if _parse_ts(r["timestamp"]) >= window_start]
    if len(win_r) < 5:
        win_r = node_readings[-max(5, len(node_readings)):]

    values = [_extract_channel_value(r, channel, baseline) for r in win_r]
    slope, t_stat, t_adj, r2 = _ols_linear_regression(values)
    curr_val = values[-1]

    # Default threshold: tilt=15 deg, distance=2.0 cm, vibration=1.0 g
    if threshold is None:
        c = channel.lower()
        if "tilt" in c:
            threshold = 15.0
        elif "dist" in c:
            threshold = 2.0
        elif "vib" in c:
            threshold = 1.0
        else:
            threshold = 1.0

    minutes_to_thresh = None
    if slope > 0:
        remaining = threshold - curr_val
        if remaining <= 0:
            minutes_to_thresh = 0.0
        else:
            minutes_to_thresh = float(round(remaining / slope, 1))

    # Reliable boolean: t_adj >= 4.0 and r2 >= 0.60
    reliable = bool(t_adj >= 4.0 and r2 >= 0.60 and slope > 0)

    res = {
        "node_id": node_id,
        "channel": channel,
        "as_of": as_of,
        "fit_minutes": fit_minutes,
        "current_value": float(round(curr_val, 4)),
        "target_threshold": threshold,
        "slope_per_minute": slope,
        "t_statistic": t_stat,
        "t_statistic_adjusted": t_adj,
        "r_squared": r2,
        "minutes_to_threshold": minutes_to_thresh,
        "reliable": reliable,
    }
    res["evidence_id"] = _make_evidence_id("project_time_to_threshold", res)
    return res
