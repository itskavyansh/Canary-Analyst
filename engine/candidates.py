from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from engine.common import Alert
from engine.baseline_b2 import BaselineB2, B2_CONFIG


@dataclass
class CandidateEpisode:
    scenario_id: str
    episode_id: str
    trigger_time: str
    node_ids: List[str]
    level: Literal["WARNING", "CRITICAL"]
    trigger_channels: List[str]


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class CandidateGenerator:
    """Wraps BaselineB2 to emit CandidateEpisode instances.
    
    A CandidateEpisode represents an investigative candidate for an autonomous agent:
      - Emitted at the first WARNING-or-above alert of each episode (15 min merge gap).
      - Re-emitted if the episode escalates in severity (e.g. from WARNING to CRITICAL).
      - Always dated 'as of' its trigger_time.
      - Strictly sanitized: no ground truth fields included.
    """

    def __init__(self, detector: Optional[BaselineB2] = None, merge_gap_minutes: float = 15.0):
        self.detector = detector or BaselineB2(B2_CONFIG)
        self.merge_gap = timedelta(minutes=merge_gap_minutes)
        self.scenario_id: str = ""
        self.active_episodes: List[Dict[str, Any]] = []
        self.episode_counter: int = 0

    def reset(self, scenario_meta: Dict[str, Any]) -> None:
        self.scenario_id = scenario_meta.get("scenario_id", "")
        self.detector.reset(scenario_meta)
        self.active_episodes = []
        self.episode_counter = 0

    def _extract_channels(self, reasons: str) -> List[str]:
        channels = set()
        r_lower = reasons.lower()
        if "tilt" in r_lower:
            channels.add("tilt")
        if "vib" in r_lower:
            channels.add("vibration")
        if "dist" in r_lower:
            channels.add("distance")
        if "piezo" in r_lower:
            channels.add("piezo")
        return sorted(list(channels)) if channels else ["unknown"]

    def update(self, timestamp: str, readings_by_node: Dict[str, Any]) -> List[CandidateEpisode]:
        alerts = self.detector.update(timestamp, readings_by_node)
        if not alerts:
            return []

        curr_dt = parse_ts(timestamp)
        emitted_candidates: List[CandidateEpisode] = []

        for a in alerts:
            # Check if this alert attaches to an existing active episode
            matched_ep = None
            for ep in self.active_episodes:
                if (curr_dt - ep["last_alert_time"]) <= self.merge_gap:
                    matched_ep = ep
                    break

            channels = self._extract_channels(a.reason)

            if matched_ep is None:
                # New episode started
                self.episode_counter += 1
                ep_id = f"{self.scenario_id}_{self.episode_counter:03d}" if self.scenario_id else f"EP_{self.episode_counter:03d}"
                new_ep = {
                    "episode_id": ep_id,
                    "first_trigger_time": a.time,
                    "last_alert_time": curr_dt,
                    "highest_level": a.level,
                    "node_ids": set(a.node_ids),
                    "channels": set(channels)
                }
                self.active_episodes.append(new_ep)

                candidate = CandidateEpisode(
                    scenario_id=self.scenario_id,
                    episode_id=ep_id,
                    trigger_time=a.time,
                    node_ids=sorted(list(new_ep["node_ids"])),
                    level=a.level,
                    trigger_channels=sorted(list(new_ep["channels"]))
                )
                emitted_candidates.append(candidate)
            else:
                # Existing episode
                matched_ep["last_alert_time"] = curr_dt
                matched_ep["node_ids"].update(a.node_ids)
                matched_ep["channels"].update(channels)

                # Check escalation (WARNING -> CRITICAL)
                if matched_ep["highest_level"] == "WARNING" and a.level == "CRITICAL":
                    matched_ep["highest_level"] = "CRITICAL"
                    escalation_candidate = CandidateEpisode(
                        scenario_id=self.scenario_id,
                        episode_id=matched_ep["episode_id"],
                        trigger_time=a.time,
                        node_ids=sorted(list(matched_ep["node_ids"])),
                        level="CRITICAL",
                        trigger_channels=sorted(list(matched_ep["channels"]))
                    )
                    emitted_candidates.append(escalation_candidate)

        return emitted_candidates

