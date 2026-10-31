import copy
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.analyst import Analyst
from agent.guard import HoldManager, SafetyGuard
from engine.baseline_b2 import BaselineB2, B2_CONFIG
from engine.candidates import CandidateGenerator, CandidateEpisode
from engine.common import Alert, Detector


class AgentDetector(Detector):
    """Detector 'AGENT': Autonomous AI Geotechnical Analyst with Deterministic Safety Guard.
    
    1. Runs Baseline B2 internally to generate raw candidate episodes.
    2. Intercepts each CandidateEpisode.
    3. Calls Muse Spark 1.3 Analyst to perform an active tool investigation.
    4. Evaluates the Analyst's output through the SafetyGuard.
    5. Holds downgraded candidates in 'REVIEW' status (bounded by 10m timeout / worsening / new critical).
    6. Attaches the Analyst's concise brief to the alert reason for kept alerts.
    7. Emits standard Alert instances for evaluation.
    """

    def __init__(
        self,
        b2_config: Optional[Dict[str, Any]] = None,
        analyst: Optional[Analyst] = None,
        guard: Optional[SafetyGuard] = None,
        hold_timeout_minutes: float = 10.0
    ):
        self.b2_config = b2_config or B2_CONFIG
        self.b2 = BaselineB2(self.b2_config)
        self.candidate_gen = CandidateGenerator(detector=self.b2)
        self.analyst = analyst or Analyst()
        self.guard = guard or SafetyGuard()
        self.hold_manager = HoldManager(hold_timeout_minutes=hold_timeout_minutes)

        self.scenario_meta: Dict[str, Any] = {}
        self.accumulated_readings: List[Dict[str, Any]] = []
        self.candidate_history: List[CandidateEpisode] = []
        self.decisions_log: List[Dict[str, Any]] = []
        self.latest_briefs_by_episode: Dict[str, str] = {}
        self.episodes_in_review: Dict[str, Alert] = {}

    def reset(self, scenario_meta: Dict[str, Any]) -> None:
        """Reset state for a new scenario stream. Strictly sanitizes metadata."""
        # Enforce that scenario_meta only contains safe operational metadata
        self.scenario_meta = {
            "scenario_id": scenario_meta.get("scenario_id", ""),
            "node_layout": scenario_meta.get("node_coordinates_m", {}),
            "blast_schedule": scenario_meta.get("blast_schedule", [])
        }
        self.candidate_gen.reset(self.scenario_meta)
        self.hold_manager = HoldManager()
        self.accumulated_readings = []
        self.candidate_history = []
        self.decisions_log = []
        self.latest_briefs_by_episode = {}
        self.episodes_in_review = {}

    def update(self, timestamp: str, readings_dict_by_node: Dict[str, Dict[str, Any]]) -> List[Alert]:
        """Process incoming sensor timestep and return alerts."""
        # 1. Accumulate readings strictly up to this timestamp (no lookahead)
        for nid, r in readings_dict_by_node.items():
            self.accumulated_readings.append(r)

        # 2. Feed into CandidateGenerator (which steps B2)
        candidates = self.candidate_gen.update(timestamp, readings_dict_by_node)

        # 3. For any new candidate, run Analyst investigation + Safety Guard
        new_criticals = []
        for cand in candidates:
            self.candidate_history.append(cand)

            # Run investigation
            analyst_res = self.analyst.investigate(
                candidate=cand,
                scenario_readings=self.accumulated_readings,
                scenario_meta=self.scenario_meta
            )

            # Evaluate guard decision
            guard_dec = self.guard.evaluate(cand, analyst_res)
            self.decisions_log.append({
                "episode_id": cand.episode_id,
                "timestamp": timestamp,
                "analyst_result": analyst_res,
                "guard_decision": guard_dec
            })

            # Extract brief if present
            brief = ""
            if analyst_res and analyst_res.parsed:
                brief = analyst_res.parsed.get("brief", "")
                self.latest_briefs_by_episode[cand.episode_id] = brief

            # Action decision
            if guard_dec.action == "DOWNGRADE":
                # Start review hold
                self.hold_manager.start_hold(cand, readings_dict_by_node)
                # Emit REVIEW alert
                rev_alert = Alert(
                    scenario_id=cand.scenario_id,
                    time=timestamp,
                    node_ids=cand.node_ids,
                    level="REVIEW",
                    reason=f"[HOLD: UNDER_REVIEW] {guard_dec.reason}. Brief: {brief}",
                    source="AGENT"
                )
                self.episodes_in_review[cand.episode_id] = Alert(
                    scenario_id=cand.scenario_id,
                    time=timestamp,
                    node_ids=cand.node_ids,
                    level=cand.level,
                    reason=f"{cand.level} alert. Brief: {brief}",
                    source="AGENT"
                )
            else:
                # KEEP action: emit candidate's original level
                if cand.level == "CRITICAL":
                    new_criticals.append(cand)

        # 4. Check hold escapes on active holds
        reemitted_episodes, cleared_episodes = self.hold_manager.check_escapes(
            current_time_str=timestamp,
            current_readings_by_node=readings_dict_by_node,
            new_critical_alerts=new_criticals,
            b2_detector=self.b2
        )

        emitted_alerts: List[Alert] = []

        # For cleared episodes, remove from episodes_in_review without re-emitting
        for ep_id in cleared_episodes:
            self.episodes_in_review.pop(ep_id, None)

        # Re-emit escaped alerts at their original level
        for ep_id in reemitted_episodes:
            if ep_id in self.episodes_in_review:
                orig_alert = self.episodes_in_review.pop(ep_id)
                escaped_alert = Alert(
                    scenario_id=orig_alert.scenario_id,
                    time=timestamp,
                    node_ids=orig_alert.node_ids,
                    level=orig_alert.level,
                    reason=f"[HOLD_TERMINATED] {orig_alert.reason}",
                    source="AGENT"
                )
                emitted_alerts.append(escaped_alert)

        # For non-held candidate alerts in this timestep, emit them with brief attached
        for cand in candidates:
            # If it was placed on hold, it is in episodes_in_review (or just escaped/cleared)
            if cand.episode_id in self.hold_manager.active_holds:
                # Emit REVIEW alert
                brief = self.latest_briefs_by_episode.get(cand.episode_id, "")
                emitted_alerts.append(Alert(
                    scenario_id=cand.scenario_id,
                    time=timestamp,
                    node_ids=cand.node_ids,
                    level="REVIEW",
                    reason=f"[HOLD: UNDER_REVIEW] Brief: {brief}",
                    source="AGENT"
                ))
            elif cand.episode_id not in reemitted_episodes and cand.episode_id not in cleared_episodes:
                # Standard KEEP alert
                brief = self.latest_briefs_by_episode.get(cand.episode_id, "")
                reason = f"{cand.level} on {cand.trigger_channels}."
                if brief:
                    reason += f" Geotechnical Brief: {brief}"
                emitted_alerts.append(Alert(
                    scenario_id=cand.scenario_id,
                    time=timestamp,
                    node_ids=cand.node_ids,
                    level=cand.level,
                    reason=reason,
                    source="AGENT"
                ))

        return emitted_alerts

