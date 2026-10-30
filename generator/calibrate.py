import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

REAL_DATA_PATH = Path("data/real_readings.csv")
OUTPUT_PATH = Path("generator/noise_profile.json")

NUMERIC_FIELDS = ["tilt_x", "tilt_y", "vibration", "distance", "piezo_peak", "piezo_rms", "piezo_peak_to_peak"]
FAULT_FIELDS = ["mpu6050_status", "hc_sr04_status", "ads1115_status"]

DEFAULT_NOISE_PROFILE = {
    "source": "defaults",
    "sampling_interval_sec": 60.0,
    "nodes": {
        f"NODE_0{i}": {
            "tilt_x": {"mean": 0.0, "std": 0.15, "p1": -0.35, "p99": 0.35, "autocorr_lag1": 0.65},
            "tilt_y": {"mean": 0.0, "std": 0.15, "p1": -0.35, "p99": 0.35, "autocorr_lag1": 0.65},
            "vibration": {"mean": 0.035, "std": 0.010, "p1": 0.015, "p99": 0.065, "autocorr_lag1": 0.10},
            "distance": {"mean": 120.0, "std": 0.30, "p1": 119.3, "p99": 120.7, "autocorr_lag1": 0.40},
            "piezo_peak": {"mean": 0.02, "std": 0.008, "p1": 0.005, "p99": 0.045, "autocorr_lag1": 0.05},
            "piezo_rms": {"mean": 0.008, "std": 0.003, "p1": 0.002, "p99": 0.018, "autocorr_lag1": 0.05},
            "piezo_peak_to_peak": {"mean": 0.04, "std": 0.015, "p1": 0.010, "p99": 0.090, "autocorr_lag1": 0.05},
            "fault_fraction": {
                "mpu6050_status": 0.0,
                "hc_sr04_status": 0.0,
                "ads1115_status": 0.0
            }
        }
        for i in range(1, 5)
    },
    "overall": {
        "tilt_x": {"mean": 0.0, "std": 0.15, "p1": -0.35, "p99": 0.35, "autocorr_lag1": 0.65},
        "tilt_y": {"mean": 0.0, "std": 0.15, "p1": -0.35, "p99": 0.35, "autocorr_lag1": 0.65},
        "vibration": {"mean": 0.035, "std": 0.010, "p1": 0.015, "p99": 0.065, "autocorr_lag1": 0.10},
        "distance": {"mean": 120.0, "std": 0.30, "p1": 119.3, "p99": 120.7, "autocorr_lag1": 0.40},
        "piezo_peak": {"mean": 0.02, "std": 0.008, "p1": 0.005, "p99": 0.045, "autocorr_lag1": 0.05},
        "piezo_rms": {"mean": 0.008, "std": 0.003, "p1": 0.002, "p99": 0.018, "autocorr_lag1": 0.05},
        "piezo_peak_to_peak": {"mean": 0.04, "std": 0.015, "p1": 0.010, "p99": 0.090, "autocorr_lag1": 0.05},
        "fault_fraction": {
            "mpu6050_status": 0.0,
            "hc_sr04_status": 0.0,
            "ads1115_status": 0.0
        }
    }
}


def calc_autocorr(series: np.ndarray) -> float:
    if len(series) < 3:
        return 0.0
    s = series - np.mean(series)
    denom = np.sum(s**2)
    if denom == 0:
        return 0.0
    return float(np.sum(s[:-1] * s[1:]) / denom)


def compute_robust_stats(series: np.ndarray) -> Dict[str, Any]:
    """Compute median, MAD-based std (1.4826*MAD), and 6*MAD outlier bounds."""
    if len(series) == 0:
        return {"median": 0.0, "mad_std": 0.0, "inliers": np.array([], dtype=float), "outliers_count": 0}
    med = float(np.median(series))
    mad = float(np.median(np.abs(series - med)))
    mad_std = float(mad * 1.4826)
    lower = med - 6 * mad_std
    upper = med + 6 * mad_std
    inlier_mask = (series >= lower) & (series <= upper)
    inliers = series[inlier_mask]
    outliers_count = int(np.sum(~inlier_mask))
    return {
        "median": med,
        "mad_std": mad_std,
        "lower_6mad": lower,
        "upper_6mad": upper,
        "inliers": inliers,
        "outliers_count": outliers_count
    }


def calibrate() -> Dict[str, Any]:
    if not REAL_DATA_PATH.exists():
        print(f"[Calibrate] Real readings file not found at {REAL_DATA_PATH}.")
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(DEFAULT_NOISE_PROFILE, f, indent=2)
        return DEFAULT_NOISE_PROFILE

    # 1. Read CSV
    df = pd.read_csv(REAL_DATA_PATH)
    total_raw_rows = len(df)
    print(f"[Calibrate] Read {total_raw_rows} rows from {REAL_DATA_PATH}.")

    # Parse timestamps
    df["dt"] = pd.to_datetime(df["timestamp"], format="mixed")
    df = df.sort_values("dt")

    time_span_str = f"{df['dt'].min()} to {df['dt'].max()}"
    print(f"[Calibrate] Time span: {time_span_str}")

    # Sampling interval
    diffs = df["dt"].diff().dt.total_seconds().dropna()
    median_interval = float(diffs[diffs > 0].median())
    print(f"[Calibrate] Median sampling interval: {median_interval:.2f} s")
    gaps_gt_5m = int((diffs > 300).sum())
    print(f"[Calibrate] Number of large time gaps (>5 min): {gaps_gt_5m}")

    # 2. Exclude rows where any status flag is 'fault' from baseline
    fault_mask = (df["mpu6050_status"] == "fault") | (df["hc_sr04_status"] == "fault") | (df["ads1115_status"] == "fault")
    rows_fault = int(fault_mask.sum())
    print(f"[Calibrate] Rows with any fault flag: {rows_fault} ({(rows_fault / total_raw_rows) * 100:.2f}%)")

    fault_free_df = df[~fault_mask].copy()

    # Calculate fault fractions per status field
    overall_fault_fraction = {
        f: float((df[f] == "fault").sum() / total_raw_rows) for f in FAULT_FIELDS
    }

    # 3. Robust outlier exclusion per field on fault-free data
    field_exclusion_counts: Dict[str, int] = {}
    field_exclusion_reasons: Dict[str, str] = {
        "tilt_x": "Extreme physical handling, bench rotations, and setup orientations ([-71.9 deg, +65.6 deg])",
        "tilt_y": "Manual placement reorientation and tilt testing ([-38.7 deg, +83.4 deg])",
        "vibration": "Manual vibration tapping, shaker testing, and bench impact shocks up to 2.5 g",
        "distance": "Out-of-range ultrasonic echoes, acoustic dropouts, and rail limits ([-1.0 cm, 403.5 cm])",
        "piezo_peak": "Mechanical stress testing and impact impulse strikes up to 2.02 V",
        "piezo_rms": "Extended acoustic testing excitation shocks up to 1.62 V",
        "piezo_peak_to_peak": "Piezo full-scale impulse clipping up to 2.30 V",
    }
    cleaned_fields_overall: Dict[str, np.ndarray] = {}

    for f in NUMERIC_FIELDS:
        vals = fault_free_df[f].dropna().to_numpy(dtype=float)
        rob = compute_robust_stats(vals)
        field_exclusion_counts[f] = rob["outliers_count"]
        cleaned_fields_overall[f] = rob["inliers"]

    print("\n[Calibrate] Outliers excluded beyond 6 MAD on fault-free rows:")
    for f, count in field_exclusion_counts.items():
        total_valid = len(fault_free_df[f].dropna())
        print(f"  - {f:<20}: {count:>4} / {total_valid} excluded ({count/total_valid*100:.2f}%) -> Reason: {field_exclusion_reasons.get(f)}")

    # 4. Resample onto median interval for autocorrelation
    resampled_interval_str = f"{max(1, int(round(median_interval)))}s"
    resampled_df = fault_free_df.set_index("dt")[NUMERIC_FIELDS].resample(resampled_interval_str).median().dropna()

    # 5. Build overall profile
    overall_profile: Dict[str, Any] = {}
    for f in NUMERIC_FIELDS:
        arr = cleaned_fields_overall[f]
        rob = compute_robust_stats(arr)
        autocorr = calc_autocorr(resampled_df[f].to_numpy()) if f in resampled_df else 0.5
        overall_profile[f] = {
            "mean": float(np.mean(arr)),
            "std": float(rob["mad_std"]),  # Robust std estimate: 1.4826 * MAD
            "p1": float(np.percentile(arr, 1)),
            "p99": float(np.percentile(arr, 99)),
            "autocorr_lag1": float(round(autocorr, 4)),
            "median": float(np.median(arr))
        }
    overall_profile["fault_fraction"] = overall_fault_fraction

    # 6. Build per-node profiles
    node_profiles: Dict[str, Any] = {}
    canonical_nodes = ["NODE_01", "NODE_02", "NODE_03", "NODE_04"]

    for nid in canonical_nodes:
        node_df = fault_free_df[fault_free_df["node_id"] == nid]
        raw_node_df = df[df["node_id"] == nid]
        node_profiles[nid] = {}

        if len(node_df) > 10:
            for f in NUMERIC_FIELDS:
                vals = node_df[f].dropna().to_numpy(dtype=float)
                if len(vals) > 5:
                    rob = compute_robust_stats(vals)
                    inliers = rob["inliers"]
                    node_profiles[nid][f] = {
                        "mean": float(np.mean(inliers)),
                        "std": float(rob["mad_std"]),
                        "p1": float(np.percentile(inliers, 1)),
                        "p99": float(np.percentile(inliers, 99)),
                        "autocorr_lag1": overall_profile[f]["autocorr_lag1"],
                        "median": float(np.median(inliers))
                    }
                else:
                    node_profiles[nid][f] = overall_profile[f].copy()
            node_profiles[nid]["fault_fraction"] = {
                f: float((raw_node_df[f] == "fault").sum() / len(raw_node_df)) if len(raw_node_df) > 0 else 0.0
                for f in FAULT_FIELDS
            }
        else:
            # Fall back to overall calibrated stats
            for f in NUMERIC_FIELDS:
                node_profiles[nid][f] = overall_profile[f].copy()
            node_profiles[nid]["fault_fraction"] = overall_fault_fraction.copy()

    # Step noise calculation for stationary AR(1) within-session process
    session_noise: Dict[str, Dict[str, float]] = {}
    for nid in ["NODE_01", "NODE_02", "NODE_03"]:
        ndf = df[df["node_id"] == nid].copy()
        ndf["dt"] = pd.to_datetime(ndf["timestamp"], format="mixed")
        ndf = ndf.sort_values("dt")
        dts = ndf["dt"].diff().dt.total_seconds().dropna()
        session_noise[nid] = {}
        for f in NUMERIC_FIELDS:
            diffs = ndf[f].diff().dropna()
            valid_diffs = diffs[dts < 10.0].dropna()
            if len(valid_diffs) > 10:
                step_mad = float(np.median(np.abs(valid_diffs - np.median(valid_diffs))) * 1.4826)
                session_noise[nid][f] = step_mad
            else:
                session_noise[nid][f] = node_profiles[nid][f]["std"]

    profile = {
        "source": "calibrated_on_prototype_readings",
        "rows_raw_total": total_raw_rows,
        "rows_fault_excluded": rows_fault,
        "rows_used_baseline": len(fault_free_df),
        "field_outliers_excluded_6mad": field_exclusion_counts,
        "sampling_interval_sec": float(median_interval),
        "large_time_gaps_gt_5m": gaps_gt_5m,
        "overall": overall_profile,
        "nodes": node_profiles,
        "continuous_step_noise": session_noise
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(profile, f, indent=2)

    # 7. Print side-by-side comparison table
    print("\n" + "=" * 105)
    print("SIDE-BY-SIDE: Old Defaults vs. New Robust Calibrated Profile")
    print("=" * 105)
    print(f"{'Field':<20} | {'Old Mean':<10} | {'New Mean':<10} | {'Old Std':<10} | {'New Std (MAD)':<14} | {'Std Ratio':<10} | {'Flag >2x Diff'}")
    print("-" * 105)

    for f in NUMERIC_FIELDS:
        old_m = DEFAULT_NOISE_PROFILE["overall"][f]["mean"]
        new_m = profile["overall"][f]["mean"]
        old_s = DEFAULT_NOISE_PROFILE["overall"][f]["std"]
        new_s = profile["overall"][f]["std"]
        ratio = new_s / old_s if old_s > 0 else 1.0
        flag = "!!! > 2x DIFFERENCE" if (ratio > 2.0 or ratio < 0.5) else "OK"
        print(f"{f:<20} | {old_m:<10.4f} | {new_m:<10.4f} | {old_s:<10.4f} | {new_s:<14.4f} | {ratio:<10.2f} | {flag}")

    print("=" * 105)
    return profile


if __name__ == "__main__":
    calibrate()
