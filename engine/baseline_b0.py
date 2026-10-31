from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional
import numpy as np

from engine.common import Alert, Detector

# Demonstration thresholds - NOT certified mine-safety limits.
# These thresholds mirror standard baseline operational logic for telemetry monitoring.
B0_CONFIG = {
    "baseline_window": 30,  # first 30 readings to estimate median baseline per node
    "cooldown_minutes": 15,  # per-node alert cooldown in minutes
    "warning": {
        "tilt_deg": 15.0,  # sqrt(dx^2 + dy^2) >= 15.0 deg
        "vibration_g": 1.0,  # peak vibration >= 1.0 g
        "distance_delta_cm": 2.0,  # abs(distance - baseline) >= 2.0 cm
    },
    "critical": {
        "tilt_deg": 22.5,  # 1.5x demo threshold
        "vibration_g": 1.5,
        "distance_delta_cm": 3.0,
    },
}


class BaselineB0(Detector):
    """B0: Naive threshold baseline reflecting legacy production telemetry monitoring.
    
    Operates per node:
      - Computes median baseline from the first 30 readings of tilt_x, tilt_y, and distance.
      - Triggers instantaneous WARNING or CRITICAL on a SINGLE reading exceedance.
      - Enforces a 15-minute per-node cooldown between alert firings.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or B0_CONFIG
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

    def update(self, timestamp: str, readings_by_node: Dict[str, Any]) -> List[Alert]:
        alerts: List[Alert] = []
        curr_dt = self._parse_ts(timestamp)
        cooldown = timedelta(minutes=self.config["cooldown_minutes"])
        baseline_w = self.config["baseline_window"]

        # Track readings
        for nid, reading in readings_by_node.items():
            if nid not in self.node_history:
                self.node_history[nid] = []
            self.node_history[nid].append(reading)

            # Establish baseline once first 30 readings are collected
            if nid not in self.baselines and len(self.node_history[nid]) >= baseline_w:
                first30 = self.node_history[nid][:baseline_w]
                self.baselines[nid] = {
                    "tilt_x": float(np.median([r["tilt_x"] for r in first30])),
                    "tilt_y": float(np.median([r["tilt_y"] for r in first30])),
                    "distance": float(np.median([r["distance"] for r in first30])),
                }

            # If baseline is not ready yet, cannot assess drift
            if nid not in self.baselines:
                continue

            # Check cooldown
            if nid in self.last_alert_time and (curr_dt - self.last_alert_time[nid]) < cooldown:
                continue

            base = self.baselines[nid]
            tilt_x = reading["tilt_x"]
            tilt_y = reading["tilt_y"]
            tilt_mag = math.hypot(tilt_x - base["tilt_x"], tilt_y - base["tilt_y"])
            dist_delta = abs(reading["distance"] - base["distance"])
            vib = reading["vibration"]

            # Evaluate CRITICAL then WARNING
            crit = self.config["critical"]
            warn = self.config["warning"]

            alert_level = None
            reasons = []

            # Check CRITICAL
            if tilt_mag >= crit["tilt_deg"]:
                alert_level = "CRITICAL"
                reasons.append(f"tilt_delta={tilt_mag:.1f}>={crit['tilt_deg']}deg")
            if vib >= crit["vibration_g"]:
                alert_level = "CRITICAL"
                reasons.append(f"vibration={vib:.2f}>={crit['vibration_g']}g")
            if dist_delta >= crit["distance_delta_cm"]:
                alert_level = "CRITICAL"
                reasons.append(f"distance_delta={dist_delta:.2f}>={crit['distance_delta_cm']}cm")

            # If not CRITICAL, check WARNING
            if alert_level is None:
                if tilt_mag >= warn["tilt_deg"]:
                    alert_level = "WARNING"
                    reasons.append(f"tilt_delta={tilt_mag:.1f}>={warn['tilt_deg']}deg")
                if vib >= warn["vibration_g"]:
                    alert_level = "WARNING"
                    reasons.append(f"vibration={vib:.2f}>={warn['vibration_g']}g")
                if dist_delta >= warn["distance_delta_cm"]:
                    alert_level = "WARNING"
                    reasons.append(f"distance_delta={dist_delta:.2f}>={warn['distance_delta_cm']}cm")

            if alert_level:
                self.last_alert_time[nid] = curr_dt
                alerts.append(Alert(
                    scenario_id=self.scenario_id,
                    time=timestamp,
                    node_ids=[nid],
                    level=alert_level,
                    reason="; ".join(reasons),
                    source="B0"
                ))

        return alerts

