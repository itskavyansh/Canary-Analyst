from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from engine.common import Alert


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def group_alert_episodes(alerts: List[Alert], merge_gap_minutes: float = 15.0) -> List[List[Alert]]:
    """Group alerts into discrete alert episodes with a 15-minute merge gap."""
    if not alerts:
        return []

    # Sort alerts by timestamp
    sorted_alerts = sorted(alerts, key=lambda a: parse_iso(a.time))
    episodes: List[List[Alert]] = []
    current_ep: List[Alert] = [sorted_alerts[0]]
    merge_gap = timedelta(minutes=merge_gap_minutes)

    for a in sorted_alerts[1:]:
        prev_time = parse_iso(current_ep[-1].time)
        curr_time = parse_iso(a.time)
        if (curr_time - prev_time) <= merge_gap:
            current_ep.append(a)
        else:
            episodes.append(current_ep)
            current_ep = [a]
    if current_ep:
        episodes.append(current_ep)

    return episodes


@dataclass
class ScenarioOutcome:
    scenario_id: str
    scenario_type: str
    is_hazard: bool
    false_alarm: bool
    false_alarm_episodes: int
    detected: bool
    time_to_detect: Optional[float]  # in minutes
    first_critical_time: Optional[float]  # in minutes from start of scenario
    lead_time: Optional[float]  # in minutes before collapse (accelerating_creep)
    detected_before_collapse: Optional[bool]
    total_episodes: int


def evaluate_scenario(
    alerts: List[Alert],
    ground_truth: Dict[str, Any]
) -> ScenarioOutcome:
    """Evaluate detection metrics for a single scenario."""
    scenario_id = ground_truth["scenario_id"]
    scenario_type = ground_truth["type"]
    is_hazard = ground_truth.get("is_hazard", False)

    # Operational evaluation filters out transient 'REVIEW' alerts (holds)
    operational_alerts = [a for a in alerts if getattr(a, "level", "") != "REVIEW"]

    episodes = group_alert_episodes(operational_alerts, merge_gap_minutes=15.0)
    total_episodes = len(episodes)

    # First critical timing
    crit_alerts = [a for a in operational_alerts if a.level == "CRITICAL"]
    first_critical_iso = min([a.time for a in crit_alerts], default=None)
    first_crit_min = None
    if first_critical_iso:
        # compute minutes from scenario start
        pass

    if not is_hazard:
        # For non-hazard scenarios: false_alarm = any alert episode
        fa = (total_episodes > 0)
        return ScenarioOutcome(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            is_hazard=False,
            false_alarm=fa,
            false_alarm_episodes=total_episodes,
            detected=False,
            time_to_detect=None,
            first_critical_time=None,
            lead_time=None,
            detected_before_collapse=None,
            total_episodes=total_episodes
        )

    # For hazard scenarios (slow_creep, accelerating_creep)
    onset_ts = ground_truth["onset_time"]
    onset_dt = parse_iso(onset_ts)
    collapse_ts = ground_truth.get("collapse_time")
    collapse_dt = parse_iso(collapse_ts) if collapse_ts else None

    # Alerts earlier than onset_time minus 5 minutes count as false alarms
    early_cutoff = onset_dt - timedelta(minutes=5.0)
    fa_episodes = 0
    valid_hazard_alerts: List[Alert] = []

    for ep in episodes:
        ep_start = parse_iso(ep[0].time)
        if ep_start < early_cutoff:
            fa_episodes += 1
        if any(parse_iso(a.time) >= onset_dt for a in ep):
            valid_hazard_alerts.extend([a for a in ep if parse_iso(a.time) >= onset_dt])

    false_alarm = (fa_episodes > 0)
    detected = len(valid_hazard_alerts) > 0

    time_to_detect = None
    lead_time = None
    detected_before_collapse = None

    if detected:
        first_alert_dt = min(parse_iso(a.time) for a in valid_hazard_alerts)
        time_to_detect = (first_alert_dt - onset_dt).total_seconds() / 60.0

        if collapse_dt:
            lead_time = (collapse_dt - first_alert_dt).total_seconds() / 60.0
            detected_before_collapse = (lead_time > 0)

    # Record first critical alert time after onset
    first_crit_after_onset = None
    crit_after_onset = [a for a in valid_hazard_alerts if a.level == "CRITICAL"]
    if crit_after_onset:
        first_crit_dt = min(parse_iso(a.time) for a in crit_after_onset)
        first_crit_after_onset = (first_crit_dt - onset_dt).total_seconds() / 60.0

    return ScenarioOutcome(
        scenario_id=scenario_id,
        scenario_type=scenario_type,
        is_hazard=True,
        false_alarm=false_alarm,
        false_alarm_episodes=fa_episodes,
        detected=detected,
        time_to_detect=time_to_detect,
        first_critical_time=first_crit_after_onset,
        lead_time=lead_time,
        detected_before_collapse=detected_before_collapse,
        total_episodes=total_episodes
    )


def bootstrap_ci(
    values: List[float],
    stat_fn: Any,
    n_resamples: int = 1000,
    seed: int = 42,
    ci: float = 0.95
) -> Tuple[float, float]:
    """Compute deterministic bootstrap confidence interval."""
    if not values:
        return (0.0, 0.0)
    arr = np.array(values, dtype=float)
    if len(arr) == 1:
        v = float(stat_fn(arr))
        return (v, v)
    rng = np.random.Generator(np.random.PCG64(seed))
    n = len(arr)
    boot_stats = np.empty(n_resamples)
    for i in range(n_resamples):
        sample = rng.choice(arr, size=n, replace=True)
        boot_stats[i] = stat_fn(sample)

    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_stats, alpha * 100))
    high = float(np.percentile(boot_stats, (1.0 - alpha) * 100))
    return (low, high)


def compute_aggregate_metrics(
    outcomes: List[ScenarioOutcome],
    seed: int = 42
) -> Dict[str, Any]:
    """Aggregate metrics with 95% bootstrap confidence intervals."""
    total = len(outcomes)
    if total == 0:
        return {}

    hazards = [o for o in outcomes if o.is_hazard]
    non_hazards = [o for o in outcomes if not o.is_hazard]

    # False alarm rate: on non-hazards + early alerts on hazards
    fa_binary = [1.0 if o.false_alarm else 0.0 for o in outcomes]
    fa_rate = float(np.mean(fa_binary))
    fa_ci = bootstrap_ci(fa_binary, np.mean, seed=seed)

    # Detection rate & missed hazard rate on hazards
    if hazards:
        det_binary = [1.0 if o.detected else 0.0 for o in hazards]
        det_rate = float(np.mean(det_binary))
        det_ci = bootstrap_ci(det_binary, np.mean, seed=seed + 1)
        miss_rate = 1.0 - det_rate
        miss_ci = (1.0 - det_ci[1], 1.0 - det_ci[0])

        # Time to detect
        ttds = [o.time_to_detect for o in hazards if o.time_to_detect is not None]
        med_ttd = float(np.median(ttds)) if ttds else None
        ttd_ci = bootstrap_ci(ttds, np.median, seed=seed + 2) if ttds else (0.0, 0.0)

        # Lead time on accelerating_creep
        accels = [o for o in hazards if o.scenario_type == "accelerating_creep"]
        lead_times = [o.lead_time for o in accels if o.lead_time is not None]
        if lead_times:
            med_lead = float(np.median(lead_times))
            p25_lead = float(np.percentile(lead_times, 25))
            p75_lead = float(np.percentile(lead_times, 75))
            lead_ci = bootstrap_ci(lead_times, np.median, seed=seed + 3)
            det_before_col = float(np.mean([1.0 if o.detected_before_collapse else 0.0 for o in accels]))
        else:
            med_lead, p25_lead, p75_lead, lead_ci, det_before_col = None, None, None, (0.0, 0.0), None
    else:
        det_rate, det_ci = None, (0.0, 0.0)
        miss_rate, miss_ci = None, (0.0, 0.0)
        med_ttd, ttd_ci = None, (0.0, 0.0)
        med_lead, p25_lead, p75_lead, lead_ci, det_before_col = None, None, None, (0.0, 0.0), None

    # Mean alert episodes per scenario
    episodes_counts = [float(o.total_episodes) for o in outcomes]
    mean_episodes = float(np.mean(episodes_counts))
    episodes_ci = bootstrap_ci(episodes_counts, np.mean, seed=seed + 4)

    return {
        "count": total,
        "false_alarm_rate": fa_rate,
        "false_alarm_ci": fa_ci,
        "detection_rate": det_rate,
        "detection_ci": det_ci,
        "missed_hazard_rate": miss_rate,
        "missed_hazard_ci": miss_ci,
        "median_time_to_detect_min": med_ttd,
        "time_to_detect_ci": ttd_ci,
        "median_lead_time_min": med_lead,
        "p25_lead_time_min": p25_lead,
        "p75_lead_time_min": p75_lead,
        "lead_time_ci": lead_ci,
        "detected_before_collapse_rate": det_before_col,
        "mean_alert_episodes": mean_episodes,
        "mean_alert_episodes_ci": episodes_ci
    }

