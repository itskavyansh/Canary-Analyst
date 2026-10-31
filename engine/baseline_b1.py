from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional
import numpy as np

from engine.common import Alert, Detector

# Demonstration thresholds - NOT certified mine-safety limits.
# Strong engineered baseline with health gating, persistence, spatial context, and trend projection.
B1_CONFIG = {
    "baseline_window": 30,
    "cooldown_minutes": 15,
    "persistence_window": 5,
    "persistence_min_exceed": 3,
    "stuck_sensor_min_readings": 30,
    "trend_window": 30,
    "trend_projection_minutes": 60.0,
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
}


class BaselineB1(Detector):
    """B1: Strong engineered opponent baseline.
    
    Rules applied per node:
      a) Health gating: Ignores a node if any hardware status flag is 'fault',
         or if tilt, vibration, and distance have been exactly constant for 30+ consecutive readings.
      b) Persistence: A channel must exceed threshold on at least 3 of the last 5 readings
         to prevent single-spike false positives (e.g., transient impacts or telemetry spikes).
      c) Spatial gating: Vibration-only exceedance on a single node without concurrent tilt
         or distance deviation on that node counts only as WARNING, never CRITICAL (e.g. machinery strikes).
      d) Trend projection: Triggers CRITICAL if tilt or distance has a sustained positive slope
         (OLS regression over the last 30 readings) that projects to reach the threshold within 60 minutes.
      e) Standard 15-minute cooldown per node.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or B1_CONFIG
        self.scenario_id: str = ""
        self.node_history: Dict[str, List[Dict[str, Any]]] = {}
        self.baselines: Dict[str, Dict[str, float]] = {}
        self.last_alert_time: Dict[str, datetime] = {}

    def reset(self, scenario_meta: Dict[str, Any]) -> None:
        self.scenario_id = scenario_meta.get("scenario_id", "")
        self.node_history = {}
        self.baselines = {}
        self.last_alert_time = {}

    def _parse_ts(self, ts: str) -> datetime:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _is_stuck(self, history: List[Dict[str, Any]]) -> bool:
        """Check if tilt_x, tilt_y, vibration, and distance have been identical for 30+ readings."""
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

    def _ols_slope(self, series: List[float]) -> float:
        """Compute ordinary least squares slope per step (minute)."""
        n = len(series)
        if n < 5:
            return 0.0
        x = np.arange(n)
        y = np.array(series, dtype=float)
        x_mean = (n - 1) / 2.0
        y_mean = float(np.mean(y))
        denom = float(np.sum((x - x_mean)**2))
        if denom == 0.0:
            return 0.0
        numer = float(np.sum((x - x_mean) * (y - y_mean)))
        return numer / denom

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

        for nid, reading in readings_by_node.items():
            if nid not in self.node_history:
                self.node_history[nid] = []
            self.node_history[nid].append(reading)

            # Establish baseline from first 30 readings
            if nid not in self.baselines and len(self.node_history[nid]) >= baseline_w:
                first30 = self.node_history[nid][:baseline_w]
                self.baselines[nid] = {
                    "tilt_x": float(np.median([r["tilt_x"] for r in first30])),
                    "tilt_y": float(np.median([r["tilt_y"] for r in first30])),
                    "distance": float(np.median([r["distance"] for r in first30])),
                }

            if nid not in self.baselines:
                continue

            # Rule B: Health gating - ignore node if faulted or stuck
            if self._has_fault_flag(reading) or self._is_stuck(self.node_history[nid]):
                continue

            # Check cooldown
            if nid in self.last_alert_time and (curr_dt - self.last_alert_time[nid]) < cooldown:
                continue

            base = self.baselines[nid]
            history = self.node_history[nid]

            # Rule A: Persistence check over last 5 readings
            recent = history[-p_win:]
            
            # Compute deviations for recent window
            tilt_mags = [math.hypot(r["tilt_x"] - base["tilt_x"], r["tilt_y"] - base["tilt_y"]) for r in recent]
            vibs = [r["vibration"] for r in recent]
            dist_deltas = [abs(r["distance"] - base["distance"]) for r in recent]

            crit_tilt_pers = sum(1 for tm in tilt_mags if tm >= crit["tilt_deg"]) >= p_min
            crit_vib_pers = sum(1 for v in vibs if v >= crit["vibration_g"]) >= p_min
            crit_dist_pers = sum(1 for dd in dist_deltas if dd >= crit["distance_delta_cm"]) >= p_min

            warn_tilt_pers = sum(1 for tm in tilt_mags if tm >= warn["tilt_deg"]) >= p_min
            warn_vib_pers = sum(1 for v in vibs if v >= warn["vibration_g"]) >= p_min
            warn_dist_pers = sum(1 for dd in dist_deltas if dd >= warn["distance_delta_cm"]) >= p_min

            # Rule D: Trend rule (slope over last 30 readings projecting to threshold within 60 min)
            trend_crit = False
            trend_reasons = []
            if len(history) >= trend_w:
                tail30 = history[-trend_w:]
                tilt_tail = [math.hypot(r["tilt_x"] - base["tilt_x"], r["tilt_y"] - base["tilt_y"]) for r in tail30]
                dist_tail = [abs(r["distance"] - base["distance"]) for r in tail30]

                slope_tilt = self._ols_slope(tilt_tail)
                curr_tilt = tilt_tail[-1]
                if slope_tilt > 0:
                    proj_tilt = curr_tilt + slope_tilt * proj_min
                    if proj_tilt >= warn["tilt_deg"]:
                        trend_crit = True
                        trend_reasons.append(f"tilt_trend_proj={proj_tilt:.1f}>={warn['tilt_deg']}deg in {proj_min}m")

                slope_dist = self._ols_slope(dist_tail)
                curr_dist = dist_tail[-1]
                if slope_dist > 0:
                    proj_dist = curr_dist + slope_dist * proj_min
                    if proj_dist >= warn["distance_delta_cm"]:
                        trend_crit = True
                        trend_reasons.append(f"dist_trend_proj={proj_dist:.2f}>={warn['distance_delta_cm']}cm in {proj_min}m")

            # Evaluate alert level
            alert_level = None
            reasons = []

            # Check persistent CRITICAL
            if crit_tilt_pers:
                alert_level = "CRITICAL"
                reasons.append(f"pers_tilt>={crit['tilt_deg']}deg")
            if crit_dist_pers:
                alert_level = "CRITICAL"
                reasons.append(f"pers_dist>={crit['distance_delta_cm']}cm")

            # Rule C: Spatial gating for vibration
            if crit_vib_pers:
                # If vibration is accompanied by tilt or distance change, it can be CRITICAL.
                # If vibration-only on a single node with no tilt/dist anomaly, capped at WARNING.
                has_geom_change = (tilt_mags[-1] >= 1.0 or dist_deltas[-1] >= 0.5 or warn_tilt_pers or warn_dist_pers)
                if has_geom_change:
                    alert_level = "CRITICAL"
                    reasons.append(f"pers_vib>={crit['vibration_g']}g_with_geom")
                else:
                    if alert_level is None:
                        alert_level = "WARNING"
                        reasons.append(f"pers_vib>={crit['vibration_g']}g_single_node_gated")

            # Check trend projection for CRITICAL
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
                    source="B1"
                ))

        return alerts

