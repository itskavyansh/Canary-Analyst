from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional
from typing import Tuple
import numpy as np

from engine.common import Alert, Detector

# Demonstration thresholds - NOT certified mine-safety limits.
# B2: Principled engineered baseline with statistical trend gating, common-mode rejection,
# rail/jump fault suppression, and multi-sensor spatial vibration gating.
B2_CONFIG = {
    "baseline_window": 30,
    "cooldown_minutes": 15,
    "persistence_window": 5,
    "persistence_min_exceed": 3,
    "stuck_sensor_min_readings": 30,
    "trend_window": 30,
    "trend_projection_minutes": 90.0,
    "warning": {
        "tilt_deg": 15.0,
        "vibration_g": 1.0,
        "distance_delta_cm": 2.0,
    },
    "critical": {
        "tilt_deg": 22.5,
        "vibration_g": 1.5,
        "distance_delta_cm": 3.0,
    },
    # Rule a: Significant-trend parameters
    "enable_significant_trend": True,
    "trend_min_tstat": 4.0,
    "trend_min_abs_change": {
        "tilt_deg": 5.0,
        "distance_delta_cm": 0.8,
    },
    # Rule b: Common-mode rejection
    "enable_common_mode_rejection": True,
    "common_mode_node_count": 3,  # >= 3 of 4 nodes
    "common_mode_mag_tolerance": 0.40,  # each within 40% of median magnitude
    # Rule c: Rail/jump fault suppression
    "enable_rail_jump_rejection": True,
    "rail_jump_max_step_cm": 10.0,  # one-step jump > 10 cm while others normal
    "rail_jump_suppress_readings": 10,
    # Rule d: Transient-vibration handling
    "enable_transient_vibration_gating": True,
    "piezo_trend_min_v": 0.05,
}


class BaselineB2(Detector):
    """B2: Principled engineered rules baseline.
    
    Builds upon B1 with four principled defenses:
      a) Significant-trend rule: OLS slope must achieve t-stat >= 4.0 over 30 readings
         AND have an absolute change from baseline of >= 5.0 deg (tilt) or >= 0.8 cm (distance).
      b) Common-mode rejection: If >= 3 of 4 nodes experience same-direction tilt change
         within 40% of the median magnitude, trend-CRITICAL is suppressed (environmental rain tilt).
      c) Rail/jump rejection: A distance reading at observed max rail, or jumping > 10 cm
         in one timestep while other nodes remain steady, marks the node suspect for 10 timesteps.
      d) Transient vibration gating: Vibration exceedance on a node with no tilt, distance,
         or piezo micro-crack activity change is capped at WARNING.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or B2_CONFIG
        self.scenario_id: str = ""
        self.node_history: Dict[str, List[Dict[str, Any]]] = {}
        self.baselines: Dict[str, Dict[str, float]] = {}
        self.last_alert_time: Dict[str, datetime] = {}
        self.suspect_countdown: Dict[str, int] = {}
        self.observed_max_dist: Dict[str, float] = {}

    def reset(self, scenario_meta: Dict[str, Any]) -> None:
        self.scenario_id = scenario_meta.get("scenario_id", "")
        self.node_history = {}
        self.baselines = {}
        self.last_alert_time = {}
        self.suspect_countdown = {}
        self.observed_max_dist = {}

    def _parse_ts(self, ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _is_stuck(self, history: List[Dict[str, Any]]) -> bool:
        k = self.config["stuck_sensor_min_readings"]
        if len(history) < k:
            return False
        tail = history[-k:]
        first = tail[0]
        for r in tail[1:]:
            if (r["tilt_x"] != first["tilt_x"] or
                r["tilt_y"] != first["tilt_y"] or
                r["vibration"] != first["vibration"] or
                r["distance"] != first["distance"]):
                return False
        return True

    def _has_fault_flag(self, reading: Dict[str, Any]) -> bool:
        return (reading.get("mpu6050_status") == "fault" or
                reading.get("hc_sr04_status") == "fault" or
                reading.get("ads1115_status") == "fault")

    def _ols_slope_and_tstat(self, series: List[float]) -> Tuple[float, float]:
        """Compute OLS slope and autocorrelation-adjusted t-statistic (t_adj) over series."""
        n = len(series)
        if n < 5:
            return 0.0, 0.0
        x = np.arange(n, dtype=float)
        y = np.array(series, dtype=float)
        x_mean = (n - 1) / 2.0
        y_mean = float(np.mean(y))
        ss_xx = float(np.sum((x - x_mean)**2))
        if ss_xx == 0.0:
            return 0.0, 0.0
        slope = float(np.sum((x - x_mean) * (y - y_mean)) / ss_xx)
        residuals = y - (y_mean + slope * (x - x_mean))
        s_err2 = float(np.sum(residuals**2) / (n - 2)) if n > 2 else 0.0
        se_slope = math.sqrt(s_err2 / ss_xx) if s_err2 > 0 and ss_xx > 0 else 1e-9
        t_stat = slope / se_slope if se_slope > 0 else 0.0

        # Autocorrelation adjustment: lag-1 autocorrelation r of residuals
        # t_adj = t * sqrt((1 - r) / (1 + r)) with r clipped to [0, 0.95]
        res_0 = residuals[:-1]
        res_1 = residuals[1:]
        denom = float(np.sum(res_0**2))
        if denom > 0:
            r = float(np.sum(res_0 * res_1) / denom)
        else:
            r = 0.0
        r_clipped = max(0.0, min(0.95, r))
        adj_factor = math.sqrt((1.0 - r_clipped) / (1.0 + r_clipped))
        t_adj = t_stat * adj_factor

        return slope, t_adj

    def update(self, timestamp: str, readings_by_node: Dict[str, Any]) -> List[Alert]:
        alerts: List[Alert] = []
        curr_dt = self._parse_ts(timestamp)
        cooldown = timedelta(minutes=self.config["cooldown_minutes"])
        baseline_w = self.config["baseline_window"]
        p_win = self.config["persistence_window"]
        p_min = self.config["persistence_min_exceed"]
        trend_w = self.config["trend_window"]
        proj_min = self.config["trend_projection_minutes"]

        warn = self.config["warning"]
        crit = self.config["critical"]

        # Track history & update baselines/observed max
        for nid, reading in readings_by_node.items():
            if nid not in self.node_history:
                self.node_history[nid] = []
                self.suspect_countdown[nid] = 0
                self.observed_max_dist[nid] = reading["distance"]

            prev_reading = self.node_history[nid][-1] if self.node_history[nid] else None
            self.node_history[nid].append(reading)
            self.observed_max_dist[nid] = max(self.observed_max_dist[nid], reading["distance"])

            # Establish baseline from first 30 readings
            if nid not in self.baselines and len(self.node_history[nid]) >= baseline_w:
                first30 = self.node_history[nid][:baseline_w]
                self.baselines[nid] = {
                    "tilt_x": float(np.median([r["tilt_x"] for r in first30])),
                    "tilt_y": float(np.median([r["tilt_y"] for r in first30])),
                    "distance": float(np.median([r["distance"] for r in first30])),
                    "piezo_peak": float(np.median([r["piezo_peak"] for r in first30])),
                }

            # Rule C: Rail / sudden jump rejection
            if self.config["enable_rail_jump_rejection"]:
                if self.suspect_countdown[nid] > 0:
                    self.suspect_countdown[nid] -= 1

                # Check if distance hit observed max or rail >= 400 cm
                hit_rail = (reading["distance"] >= 400.0 or (reading["distance"] >= self.observed_max_dist[nid] and reading["distance"] > 100.0))
                # Check 1-step jump > 10 cm while other nodes did not jump
                jumped = False
                if prev_reading is not None:
                    step_jump = abs(reading["distance"] - prev_reading["distance"])
                    if step_jump > self.config["rail_jump_max_step_cm"]:
                        # Check whether other nodes jumped similarly
                        other_jumps = []
                        for other_id, other_r in readings_by_node.items():
                            if other_id != nid and len(self.node_history[other_id]) >= 2:
                                o_prev = self.node_history[other_id][-2]
                                other_jumps.append(abs(other_r["distance"] - o_prev["distance"]))
                        other_max_jump = max(other_jumps) if other_jumps else 0.0
                        if other_max_jump < 2.0:  # others are normal
                            jumped = True

                if hit_rail or jumped:
                    self.suspect_countdown[nid] = self.config["rail_jump_suppress_readings"]

        # Rule B: Common-mode rejection check across all available nodes
        common_mode_active = False
        if self.config["enable_common_mode_rejection"] and len(self.baselines) >= 3:
            # Check tilt displacement vectors from baseline
            deltas_x = []
            deltas_y = []
            mags = []
            for nid, r in readings_by_node.items():
                if nid in self.baselines:
                    b = self.baselines[nid]
                    dx = r["tilt_x"] - b["tilt_x"]
                    dy = r["tilt_y"] - b["tilt_y"]
                    mag = math.hypot(dx, dy)
                    if mag >= 1.0:  # meaningful tilt movement
                        deltas_x.append(dx)
                        deltas_y.append(dy)
                        mags.append(mag)

            if len(mags) >= self.config["common_mode_node_count"]:
                med_mag = float(np.median(mags))
                if med_mag > 0:
                    # check if each is within tolerance
                    tol = self.config["common_mode_mag_tolerance"]
                    within_tol = [m for m in mags if abs(m - med_mag) / med_mag <= tol]
                    # check direction consistency: dot product between vectors > 0
                    signs_x = [math.copysign(1, dx) for dx in deltas_x]
                    signs_y = [math.copysign(1, dy) for dy in deltas_y]
                    dir_consistent = (abs(sum(signs_x)) >= len(mags) - 1) or (abs(sum(signs_y)) >= len(mags) - 1)
                    if len(within_tol) >= self.config["common_mode_node_count"] and dir_consistent:
                        common_mode_active = True

        # Process alerts per node
        for nid, reading in readings_by_node.items():
            if nid not in self.baselines:
                continue

            # Rule C: Health / suspect gating
            if self._has_fault_flag(reading) or self._is_stuck(self.node_history[nid]):
                continue
            if self.config["enable_rail_jump_rejection"] and self.suspect_countdown.get(nid, 0) > 0:
                continue

            # Cooldown check
            if nid in self.last_alert_time and (curr_dt - self.last_alert_time[nid]) < cooldown:
                continue

            base = self.baselines[nid]
            history = self.node_history[nid]
            recent = history[-p_win:]

            tilt_mags = [math.hypot(r["tilt_x"] - base["tilt_x"], r["tilt_y"] - base["tilt_y"]) for r in recent]
            vibs = [r["vibration"] for r in recent]
            dist_deltas = [abs(r["distance"] - base["distance"]) for r in recent]

            crit_tilt_pers = sum(1 for tm in tilt_mags if tm >= crit["tilt_deg"]) >= p_min
            crit_vib_pers = sum(1 for v in vibs if v >= crit["vibration_g"]) >= p_min
            crit_dist_pers = sum(1 for dd in dist_deltas if dd >= crit["distance_delta_cm"]) >= p_min

            warn_tilt_pers = sum(1 for tm in tilt_mags if tm >= warn["tilt_deg"]) >= p_min
            warn_vib_pers = sum(1 for v in vibs if v >= warn["vibration_g"]) >= p_min
            warn_dist_pers = sum(1 for dd in dist_deltas if dd >= warn["distance_delta_cm"]) >= p_min

            # Rule A: Significant-trend projection
            trend_crit = False
            trend_reasons = []

            # Only evaluate trend if not suppressed by common-mode rejection
            if len(history) >= trend_w:
                tail30 = history[-trend_w:]
                tilt_tail = [math.hypot(r["tilt_x"] - base["tilt_x"], r["tilt_y"] - base["tilt_y"]) for r in tail30]
                dist_tail = [abs(r["distance"] - base["distance"]) for r in tail30]

                # Tilt slope & t-stat
                slope_tilt, tstat_tilt = self._ols_slope_and_tstat(tilt_tail)
                curr_tilt = tilt_tail[-1]
                req_tstat = self.config["trend_min_tstat"] if self.config["enable_significant_trend"] else 0.0
                min_tilt_abs = self.config["trend_min_abs_change"]["tilt_deg"] if self.config["enable_significant_trend"] else 0.0

                if slope_tilt > 0 and (not common_mode_active):
                    proj_tilt = curr_tilt + slope_tilt * proj_min
                    if proj_tilt >= warn["tilt_deg"]:
                        if (not self.config["enable_significant_trend"]) or (tstat_tilt >= req_tstat and curr_tilt >= min_tilt_abs):
                            trend_crit = True
                            trend_reasons.append(f"tilt_trend_proj={proj_tilt:.1f}>={warn['tilt_deg']}deg(t={tstat_tilt:.1f})")

                # Distance slope & t-stat
                slope_dist, tstat_dist = self._ols_slope_and_tstat(dist_tail)
                curr_dist = dist_tail[-1]
                min_dist_abs = self.config["trend_min_abs_change"]["distance_delta_cm"] if self.config["enable_significant_trend"] else 0.0

                if slope_dist > 0:
                    proj_dist = curr_dist + slope_dist * proj_min
                    if proj_dist >= warn["distance_delta_cm"]:
                        if (not self.config["enable_significant_trend"]) or (tstat_dist >= req_tstat and curr_dist >= min_dist_abs):
                            trend_crit = True
                            trend_reasons.append(f"dist_trend_proj={proj_dist:.2f}>={warn['distance_delta_cm']}cm(t={tstat_dist:.1f})")

            # Evaluate alert level
            alert_level = None
            reasons = []

            # Persistent CRITICAL
            if crit_tilt_pers:
                alert_level = "CRITICAL"
                reasons.append(f"pers_tilt>={crit['tilt_deg']}deg")
            if crit_dist_pers:
                alert_level = "CRITICAL"
                reasons.append(f"pers_dist>={crit['distance_delta_cm']}cm")

            # Rule D: Transient-vibration gating
            if crit_vib_pers:
                piezo_inc = abs(reading["piezo_peak"] - base.get("piezo_peak", 0.02))
                has_geom_or_piezo = (
                    tilt_mags[-1] >= 1.0 or dist_deltas[-1] >= 0.5 or
                    warn_tilt_pers or warn_dist_pers or
                    piezo_inc >= self.config["piezo_trend_min_v"]
                )
                if not self.config["enable_transient_vibration_gating"]:
                    alert_level = "CRITICAL"
                    reasons.append(f"pers_vib>={crit['vibration_g']}g")
                elif has_geom_or_piezo:
                    alert_level = "CRITICAL"
                    reasons.append(f"pers_vib>={crit['vibration_g']}g_with_geom_piezo")
                else:
                    if alert_level is None:
                        alert_level = "WARNING"
                        reasons.append(f"pers_vib>={crit['vibration_g']}g_transient_gated")

            # Trend CRITICAL
            if trend_crit and alert_level != "CRITICAL":
                alert_level = "CRITICAL"
                reasons.extend(trend_reasons)

            # Check WARNING if not CRITICAL
            if alert_level is None:
                if warn_tilt_pers:
                    alert_level = "WARNING"
                    reasons.append(f"pers_tilt>={warn['tilt_deg']}deg")
                if warn_dist_pers:
                    alert_level = "WARNING"
                    reasons.append(f"pers_dist>={warn['distance_delta_cm']}cm")
                if warn_vib_pers:
                    alert_level = "WARNING"
                    reasons.append(f"pers_vib>={warn['vibration_g']}g")

            if alert_level:
                self.last_alert_time[nid] = curr_dt
                alerts.append(Alert(
                    scenario_id=self.scenario_id,
                    time=timestamp,
                    node_ids=[nid],
                    level=alert_level,
                    reason="; ".join(reasons),
                    source="B2"
                ))

        return alerts
