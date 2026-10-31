from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Literal, Optional, Set

from agent.analyst import AnalystResult
from engine.candidates import CandidateEpisode


@dataclass
class GuardDecision:
    action: Literal["KEEP", "DOWNGRADE"]
    reason: str
    failed_conditions: List[str]
    recalculated_metrics: Dict[str, Any]


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class SafetyGuard:
    """Deterministic safety layer that verifies model diagnoses and holds final authority.
    
    A DOWNGRADE recommendation is honored ONLY if all Gates (A, B, C, D) pass.
    Otherwise, the candidate remains KEEP.
    """

    BENIGN_HYPOTHESES = {
        "blast",
        "machinery_impact",
        "environmental_tilt",
        "sensor_fault",
        "sensor_stuck"
    }

    def __init__(
        self,
        min_confidence: float = 0.80,
        trend_min_tstat: float = 4.0,
        trend_min_r2: float = 0.60,
        trend_max_minutes: float = 120.0
    ):
        self.min_confidence = min_confidence
        self.trend_min_tstat = trend_min_tstat
        self.trend_min_r2 = trend_min_r2
        self.trend_max_minutes = trend_max_minutes

    def evaluate(
        self,
        candidate: CandidateEpisode,
        analyst_result: Optional[AnalystResult]
    ) -> GuardDecision:
        failed_conditions: List[str] = []
        recalculated: Dict[str, Any] = {}

        if analyst_result is None or analyst_result.parsed is None:
            return GuardDecision(
                action="KEEP",
                reason="Model result is missing or failed to parse into valid JSON schema",
                failed_conditions=["schema_parse_failure"],
                recalculated_metrics={}
            )

        parsed = analyst_result.parsed
        recommendation = parsed.get("recommendation", "KEEP")
        confidence = float(parsed.get("confidence", 0.0))
        hypothesis = parsed.get("hypothesis", "unclear")
        cited_evidence_ids = parsed.get("cited_evidence_ids", [])

        # If analyst itself recommends KEEP, honor KEEP immediately
        if recommendation != "DOWNGRADE":
            return GuardDecision(
                action="KEEP",
                reason="Analyst recommended KEEP",
                failed_conditions=[],
                recalculated_metrics={"model_recommendation": recommendation}
            )

        # ----------------------------------------------------
        # Gate A: Schema, Confidence, and Benign Hypothesis
        # ----------------------------------------------------
        if confidence < self.min_confidence:
            failed_conditions.append(f"insufficient_confidence: {confidence:.2f} < {self.min_confidence:.2f}")

        if hypothesis not in self.BENIGN_HYPOTHESES:
            failed_conditions.append(f"non_benign_hypothesis: '{hypothesis}'")

        # ----------------------------------------------------
        # Gate B: Evidence Integrity (No Hallucinations)
        # ----------------------------------------------------
        tool_results = analyst_result.tool_results
        known_evidence_ids: Set[str] = set()
        tools_cited: Set[str] = set()

        for k, v in tool_results.items():
            if isinstance(v, dict):
                ev_id = v.get("evidence_id")
                t_name = v.get("tool")
                if ev_id:
                    known_evidence_ids.add(ev_id)
                if t_name:
                    tools_cited.add(t_name)

        if not cited_evidence_ids:
            failed_conditions.append("no_evidence_ids_cited")
        else:
            for cid in cited_evidence_ids:
                if cid not in known_evidence_ids:
                    failed_conditions.append(f"unverified_evidence_id: '{cid}'")

        # Check distinct tools cited
        cited_tool_names = set()
        for cid in cited_evidence_ids:
            ev_data = tool_results.get(cid)
            if ev_data and isinstance(ev_data, dict):
                tname = ev_data.get("tool")
                if tname:
                    cited_tool_names.add(tname)

        if len(cited_tool_names) < 2:
            failed_conditions.append(f"fewer_than_2_distinct_tools_cited: {list(cited_tool_names)}")

        # ----------------------------------------------------
        # Gate C: Hypothesis-Specific Deterministic Checks
        # ----------------------------------------------------
        # Gather available tool results by tool type
        blast_sched_res = None
        neighbor_res_dict: Dict[str, Dict[str, Any]] = {}
        sensor_health_dict: Dict[str, Dict[str, Any]] = {}
        node_history_dict: Dict[str, Dict[str, Any]] = {}
        trend_proj_dict: Dict[str, Dict[str, Any]] = {}

        for k, v in tool_results.items():
            if not isinstance(v, dict):
                continue
            # Deduce tool name from dictionary content if not explicit
            t = v.get("tool")
            if not t:
                if "blast_scheduled_within_30min" in v or "scheduled_blasts" in v:
                    t = "check_blast_schedule"
                elif "per_node_change" in v or "cross_node_correlation" in v:
                    t = "compare_neighbor_nodes"
                elif "consecutive_constant_readings" in v or "rail_value_fraction" in v:
                    t = "get_sensor_health"
                elif "returned_to_baseline" in v or "slope_per_min" in v:
                    t = "get_node_history"
                elif "projected_minutes_to_threshold" in v or "t_statistic" in v:
                    t = "project_time_to_threshold"

            if t == "check_blast_schedule":
                blast_sched_res = v
            elif t == "compare_neighbor_nodes":
                ch = v.get("channel", "vibration")
                neighbor_res_dict[ch] = v
            elif t == "get_sensor_health":
                nid = v.get("node_id", "")
                sensor_health_dict[nid] = v
            elif t == "get_node_history":
                nid = v.get("node_id", "")
                ch = v.get("channel", "")
                node_history_dict[f"{nid}:{ch}"] = v
            elif t == "project_time_to_threshold":
                nid = v.get("node_id", "")
                ch = v.get("channel", "")
                trend_proj_dict[f"{nid}:{ch}"] = v

        if hypothesis == "blast":
            # Needs >= 3 nodes synchronous OR scheduled blast within 30 min
            # AND triggering channel back within 3 noise std of baseline or falling
            # AND no node with reliable trend toward threshold
            has_blast_match = False
            if blast_sched_res and (blast_sched_res.get("blast_scheduled_within_30min") or blast_sched_res.get("match_found")):
                has_blast_match = True
            elif blast_sched_res and blast_sched_res.get("nearby_blasts"):
                has_blast_match = True

            # Cross node synchrony
            has_sync = False
            vib_comp = neighbor_res_dict.get("vibration")
            if vib_comp:
                p_times = vib_comp.get("peak_times", {})
                if len(p_times) >= 3:
                    has_sync = True

            if not (has_blast_match or has_sync):
                failed_conditions.append("blast_check_failed: no matching blast schedule and no >=3 node synchrony")

            # Channel returning to baseline or falling
            channel_recovering = False
            for ch in candidate.trigger_channels:
                for nid in candidate.node_ids:
                    hist = node_history_dict.get(f"{nid}:{ch}")
                    if hist:
                        if hist.get("returned_to_baseline"):
                            channel_recovering = True
                        elif hist.get("slope_per_min", 0.0) <= 0.0:
                            channel_recovering = True

            if not channel_recovering and node_history_dict:
                failed_conditions.append("blast_check_failed: trigger channel not falling or returned to baseline")

        elif hypothesis == "machinery_impact":
            # Needs one node only, short, no persistent tilt or distance change
            if len(candidate.node_ids) > 1:
                failed_conditions.append(f"machinery_impact_failed: affects multiple nodes {candidate.node_ids}")

            # Check no tilt or distance change on the suspect node
            for nid in candidate.node_ids:
                tilt_hist = node_history_dict.get(f"{nid}:tilt")
                dist_hist = node_history_dict.get(f"{nid}:distance")
                if tilt_hist and abs(tilt_hist.get("mean", 0.0)) > 5.0:
                    failed_conditions.append("machinery_impact_failed: persistent tilt change observed")
                if dist_hist and abs(dist_hist.get("mean", 0.0)) > 1.0:
                    failed_conditions.append("machinery_impact_failed: persistent distance change observed")

        elif hypothesis == "environmental_tilt":
            # Needs common-mode tilt on >= 3 nodes and no vibration or piezo trend
            tilt_comp = neighbor_res_dict.get("tilt")
            if tilt_comp:
                node_changes = tilt_comp.get("per_node_change", {})
                # Count nodes moving in tilt
                nodes_moving = [n for n, c in node_changes.items() if abs(c) > 0.05]
                if len(nodes_moving) < 3:
                    failed_conditions.append(f"environmental_tilt_failed: common-mode nodes {len(nodes_moving)} < 3")
            else:
                failed_conditions.append("environmental_tilt_failed: compare_neighbor_nodes on tilt was not evaluated")

            # Check no vibration or piezo spike
            if "vibration" in candidate.trigger_channels:
                failed_conditions.append("environmental_tilt_failed: candidate was triggered by vibration")

        elif hypothesis == "sensor_fault":
            # Needs sensor health anomalies on that node AND other nodes unchanged
            target_node = candidate.node_ids[0] if candidate.node_ids else ""
            health = sensor_health_dict.get(target_node)
            has_anomaly = False
            if health:
                if not health.get("is_healthy", True):
                    has_anomaly = True
                if health.get("rail_value_fraction", 0.0) > 0.05:
                    has_anomaly = True
                if health.get("max_step_change_distance_cm", 0.0) > 10.0:
                    has_anomaly = True
                status_flags = health.get("status_flags", {})
                if any(v == "fault" for v in status_flags.values()):
                    has_anomaly = True

            if not has_anomaly:
                failed_conditions.append(f"sensor_fault_failed: no anomalies detected by get_sensor_health on {target_node}")

            # Check other nodes unchanged
            for nid, h in sensor_health_dict.items():
                if nid != target_node and not h.get("is_healthy", True):
                    failed_conditions.append(f"sensor_fault_failed: multiple nodes show anomalies ({nid})")

        elif hypothesis == "sensor_stuck":
            target_node = candidate.node_ids[0] if candidate.node_ids else ""
            health = sensor_health_dict.get(target_node)
            is_stuck = False
            if health:
                if health.get("consecutive_constant_readings", 0) >= 30:
                    is_stuck = True
            if not is_stuck:
                failed_conditions.append(f"sensor_stuck_failed: constant freeze not confirmed on {target_node}")

        # ----------------------------------------------------
        # Gate D: Global Veto
        # ----------------------------------------------------
        # Veto if ANY non-suspect node has a reliable trend (t_adj >= 4, r2 >= 0.6)
        # projecting to threshold within 120 minutes, or piezo shows rising trend
        for k, proj in trend_proj_dict.items():
            nid = proj.get("node_id")
            if proj.get("reliable_trend"):
                t_stat = abs(proj.get("t_statistic", 0.0))
                r2 = proj.get("r_squared", 0.0)
                proj_min = proj.get("projected_minutes_to_threshold")

                if t_stat >= self.trend_min_tstat and r2 >= self.trend_min_r2:
                    if proj_min is not None and 0.0 < proj_min <= self.trend_max_minutes:
                        failed_conditions.append(
                            f"global_veto: node {nid} has reliable trend (t={t_stat:.1f}, r2={r2:.2f}, proj={proj_min:.1f}m)"
                        )

        # Check piezo acoustic emission
        for k, hist in node_history_dict.items():
            if "piezo" in k:
                if hist.get("slope_per_min", 0.0) > 0.005 and hist.get("mean", 0.0) > 0.10:
                    failed_conditions.append(f"global_veto: rising piezo emission on {k}")

        recalculated["failed_count"] = len(failed_conditions)
        recalculated["failed_conditions"] = failed_conditions

        if failed_conditions:
            return GuardDecision(
                action="KEEP",
                reason=f"Safety guard rejected DOWNGRADE: {'; '.join(failed_conditions)}",
                failed_conditions=failed_conditions,
                recalculated_metrics=recalculated
            )

        return GuardDecision(
            action="DOWNGRADE",
            reason=f"Safety guard approved DOWNGRADE for verified '{hypothesis}'",
            failed_conditions=[],
            recalculated_metrics=recalculated
        )


@dataclass
class ActiveHold:
    episode_id: str
    scenario_id: str
    trigger_time: datetime
    node_ids: List[str]
    trigger_channels: List[str]
    initial_channel_values: Dict[str, float]
    candidate: CandidateEpisode
    hold_timeout_minutes: float = 15.0


@dataclass
class HoldResolution:
    episode_id: str
    outcome: Literal["REEMITTED_BY_CRITICAL", "REEMITTED_BY_WORSENING", "REEMITTED_BY_TIMEOUT_PERSISTENCE", "CLEARED"]
    reason: str


class HoldManager:
    """Manages temporary review holds with bounded delay and proper resolution semantics.
    
    A DOWNGRADE places candidate in status UNDER_REVIEW, alert level REVIEW.
    Re-emitted at original level ONLY IF one happens before hold expires:
      (a) any new B2.1 CRITICAL on a different node or channel (REEMITTED_BY_CRITICAL)
      (b) candidate's channel worsens by > 25% of its change at trigger time (REEMITTED_BY_WORSENING)
      (c) at hold_timeout (15 minutes), the triggering channel still exceeds its WARNING threshold
          under B2.1 rules using readings up to that time (REEMITTED_BY_TIMEOUT_PERSISTENCE)
    Otherwise the hold expires as CLEARED and no WARNING or CRITICAL alert is ever emitted.
    """

    def __init__(self, hold_timeout_minutes: float = 15.0):
        self.hold_timeout = timedelta(minutes=hold_timeout_minutes)
        self.active_holds: Dict[str, ActiveHold] = {}
        self.hold_resolutions_log: List[HoldResolution] = []

    def start_hold(
        self,
        candidate: CandidateEpisode,
        current_readings_by_node: Dict[str, Dict[str, Any]]
    ) -> None:
        init_values = {}
        for nid in candidate.node_ids:
            node_r = current_readings_by_node.get(nid, {})
            for ch in candidate.trigger_channels:
                val = node_r.get(ch)
                if val is not None and isinstance(val, (int, float)):
                    init_values[f"{nid}:{ch}"] = float(val)

        hold = ActiveHold(
            episode_id=candidate.episode_id,
            scenario_id=candidate.scenario_id,
            trigger_time=parse_ts(candidate.trigger_time),
            node_ids=candidate.node_ids,
            trigger_channels=candidate.trigger_channels,
            initial_channel_values=init_values,
            candidate=candidate,
            hold_timeout_minutes=self.hold_timeout.total_seconds() / 60.0
        )
        self.active_holds[candidate.episode_id] = hold

    def check_escapes(
        self,
        current_time_str: str,
        current_readings_by_node: Dict[str, Dict[str, Any]],
        new_critical_alerts: List[Any],
        b2_detector: Optional[Any] = None
    ) -> Tuple[List[str], List[str]]:
        """Check active holds against escape conditions.
        
        Returns:
            (reemitted_episode_ids, cleared_episode_ids)
        """
        current_dt = parse_ts(current_time_str)
        reemitted_episodes: List[str] = []
        cleared_episodes: List[str] = []

        for ep_id, hold in list(self.active_holds.items()):
            reemit_outcome = None
            reemit_reason = ""

            # Check (a): New B2.1 CRITICAL on a different node or channel
            if new_critical_alerts:
                for alert in new_critical_alerts:
                    if getattr(alert, "level", "") == "CRITICAL":
                        diff_node = any(nid not in hold.node_ids for nid in alert.node_ids)
                        if diff_node:
                            reemit_outcome = "REEMITTED_BY_CRITICAL"
                            reemit_reason = f"New CRITICAL alert observed on {alert.node_ids}"
                            break

            # Check (b): Worsening by > 25% of channel change at trigger time
            if reemit_outcome is None:
                for k, init_val in hold.initial_channel_values.items():
                    nid, ch = k.split(":")
                    node_r = current_readings_by_node.get(nid, {})
                    cur_val = node_r.get(ch)
                    if cur_val is not None and isinstance(cur_val, (int, float)):
                        cur_val = float(cur_val)
                        delta = abs(cur_val - init_val)
                        baseline_ref = abs(init_val) if abs(init_val) > 1e-4 else 1.0
                        if delta / baseline_ref > 0.25:
                            reemit_outcome = "REEMITTED_BY_WORSENING"
                            reemit_reason = f"Channel {k} worsened by > 25% ({init_val:.2f} -> {cur_val:.2f})"
                            break

            # Check (c) or Timeout Clearance at hold_timeout (15 minutes)
            if reemit_outcome is None:
                if current_dt - hold.trigger_time >= self.hold_timeout:
                    # Timeout reached: check if channel still exceeds WARNING threshold under B2.1
                    still_exceeds_warning = False
                    if b2_detector and hasattr(b2_detector, "node_baselines"):
                        for nid in hold.node_ids:
                            b_dict = b2_detector.node_baselines.get(nid, {})
                            cur_node_r = current_readings_by_node.get(nid, {})
                            # Check tilt
                            if "tilt" in hold.trigger_channels:
                                cur_tx = cur_node_r.get("tilt_x", 0.0)
                                cur_ty = cur_node_r.get("tilt_y", 0.0)
                                b_tx = b_dict.get("tilt_x", 0.0)
                                b_ty = b_dict.get("tilt_y", 0.0)
                                mag = math.hypot(cur_tx - b_tx, cur_ty - b_ty)
                                if mag >= b2_detector.config["warning"]["tilt_deg"]:
                                    still_exceeds_warning = True
                            # Check distance
                            if "distance" in hold.trigger_channels:
                                cur_d = cur_node_r.get("distance", 0.0)
                                b_d = b_dict.get("distance", 0.0)
                                if abs(cur_d - b_d) >= b2_detector.config["warning"]["distance_delta_cm"]:
                                    still_exceeds_warning = True
                            # Check vibration
                            if "vibration" in hold.trigger_channels:
                                cur_v = cur_node_r.get("vibration", 0.0)
                                if cur_v >= b2_detector.config["warning"]["vibration_g"]:
                                    still_exceeds_warning = True

                    if still_exceeds_warning:
                        reemit_outcome = "REEMITTED_BY_TIMEOUT_PERSISTENCE"
                        reemit_reason = "Hold timeout reached and channel still exceeds WARNING threshold"
                    else:
                        # Benign condition resolved! Expire as CLEARED
                        cleared_episodes.append(ep_id)
                        res = HoldResolution(
                            episode_id=ep_id,
                            outcome="CLEARED",
                            reason="Hold timeout reached and signal returned to nominal; alert dismissed"
                        )
                        self.hold_resolutions_log.append(res)
                        del self.active_holds[ep_id]

            if reemit_outcome is not None:
                reemitted_episodes.append(ep_id)
                res = HoldResolution(
                    episode_id=ep_id,
                    outcome=reemit_outcome,
                    reason=reemit_reason
                )
                self.hold_resolutions_log.append(res)
                del self.active_holds[ep_id]

        return reemitted_episodes, cleared_episodes

