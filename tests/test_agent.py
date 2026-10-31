import os
from unittest.mock import MagicMock
import pytest

from agent.analyst import Analyst, AnalystResult
from agent.guard import ActiveHold, HoldManager, SafetyGuard
from agent.detector_agent import AgentDetector
from engine.candidates import CandidateEpisode
from engine.common import Alert


def test_guard_rejects_missing_or_failed_schema():
    guard = SafetyGuard()
    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="S1_ep0",
        trigger_time="2026-03-30T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["tilt"]
    )
    # None result
    dec1 = guard.evaluate(cand, None)
    assert dec1.action == "KEEP"
    assert "schema_parse_failure" in dec1.failed_conditions

    # Malformed parsed
    res2 = AnalystResult(
        parsed=None,
        transcript=[],
        tool_calls=[],
        tool_results={},
        token_usage={},
        cost_usd=0.01,
        latency_sec=1.0,
        prompt_hash="dummy"
    )
    dec2 = guard.evaluate(cand, res2)
    assert dec2.action == "KEEP"
    assert "schema_parse_failure" in dec2.failed_conditions


def test_guard_rejects_low_confidence():
    guard = SafetyGuard(min_confidence=0.80)
    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="S1_ep0",
        trigger_time="2026-03-30T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["vibration"]
    )
    res = AnalystResult(
        parsed={
            "hypothesis": "machinery_impact",
            "recommendation": "DOWNGRADE",
            "confidence": 0.65,
            "cited_evidence_ids": ["ev1", "ev2"],
            "findings": ["Small bump"],
            "brief": "Check sensor."
        },
        transcript=[],
        tool_calls=[],
        tool_results={
            "ev1": {"evidence_id": "ev1", "tool": "get_sensor_health"},
            "ev2": {"evidence_id": "ev2", "tool": "compare_neighbor_nodes"}
        },
        token_usage={},
        cost_usd=0.01,
        latency_sec=1.0,
        prompt_hash="dummy"
    )
    dec = guard.evaluate(cand, res)
    assert dec.action == "KEEP"
    assert any("insufficient_confidence" in c for c in dec.failed_conditions)


def test_guard_rejects_invented_evidence_ids():
    guard = SafetyGuard()
    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="S1_ep0",
        trigger_time="2026-03-30T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["vibration"]
    )
    res = AnalystResult(
        parsed={
            "hypothesis": "machinery_impact",
            "recommendation": "DOWNGRADE",
            "confidence": 0.95,
            "cited_evidence_ids": ["ev_invented_123"],
            "findings": ["Bump on node"],
            "brief": "Check site."
        },
        transcript=[],
        tool_calls=[],
        tool_results={
            "ev_real_456": {"evidence_id": "ev_real_456", "tool": "get_sensor_health"}
        },
        token_usage={},
        cost_usd=0.01,
        latency_sec=1.0,
        prompt_hash="dummy"
    )
    dec = guard.evaluate(cand, res)
    assert dec.action == "KEEP"
    assert any("unverified_evidence_id" in c for c in dec.failed_conditions)


def test_guard_global_veto_on_reliable_trend():
    guard = SafetyGuard()
    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="S1_ep0",
        trigger_time="2026-03-30T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["vibration"]
    )
    res = AnalystResult(
        parsed={
            "hypothesis": "blast",
            "recommendation": "DOWNGRADE",
            "confidence": 0.92,
            "cited_evidence_ids": ["ev1", "ev2"],
            "findings": ["Synchronous vibration spike"],
            "brief": "Scheduled blast occurred."
        },
        transcript=[],
        tool_calls=[],
        tool_results={
            "ev1": {
                "evidence_id": "ev1",
                "tool": "check_blast_schedule",
                "match_found": True,
                "scheduled_blasts": [{"start_time": "2026-03-30T10:05:00+00:00"}]
            },
            "ev2": {
                "evidence_id": "ev2",
                "tool": "get_node_history",
                "node_id": "NODE_01",
                "channel": "vibration",
                "returned_to_baseline": True
            },
            # Non-suspect node NODE_02 has reliable active trend!
            "trend_NODE_02": {
                "tool": "project_time_to_threshold",
                "node_id": "NODE_02",
                "reliable_trend": True,
                "t_statistic": 5.2,
                "r_squared": 0.75,
                "projected_minutes_to_threshold": 45.0
            }
        },
        token_usage={},
        cost_usd=0.01,
        latency_sec=1.0,
        prompt_hash="dummy"
    )
    dec = guard.evaluate(cand, res)
    assert dec.action == "KEEP"
    assert any("global_veto" in c for c in dec.failed_conditions)


def test_hold_manager_timeout_and_worsening():
    mgr = HoldManager(hold_timeout_minutes=15.0)
    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="ep1",
        trigger_time="2026-10-27T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["tilt"]
    )
    readings = {"NODE_01": {"tilt": 10.0}}
    mgr.start_hold(cand, readings)
    assert "ep1" in mgr.active_holds

    # At 5 minutes, normal readings -> hold continues
    reemitted, cleared = mgr.check_escapes("2026-10-27T10:05:00+00:00", {"NODE_01": {"tilt": 10.2}}, [])
    assert len(reemitted) == 0
    assert len(cleared) == 0

    # Case 1: Worsening by > 25% (10.0 -> 13.5) re-emits immediately
    reemitted, cleared = mgr.check_escapes("2026-10-27T10:06:00+00:00", {"NODE_01": {"tilt": 13.5}}, [])
    assert "ep1" in reemitted
    assert "ep1" not in mgr.active_holds
    assert mgr.hold_resolutions_log[-1].outcome == "REEMITTED_BY_WORSENING"

    # Case 2: New CRITICAL elsewhere re-emits immediately
    mgr.start_hold(cand, readings)
    crit_alert = Alert(
        scenario_id="S1",
        time="2026-10-27T10:07:00+00:00",
        node_ids=["NODE_02"],
        level="CRITICAL",
        reason="trend critical",
        source="B2"
    )
    reemitted, cleared = mgr.check_escapes("2026-10-27T10:07:00+00:00", {"NODE_01": {"tilt": 10.1}}, [crit_alert])
    assert "ep1" in reemitted
    assert mgr.hold_resolutions_log[-1].outcome == "REEMITTED_BY_CRITICAL"

    # Case 3: Resolved case clears at timeout (15 minutes)
    mgr.start_hold(cand, readings)
    # mock b2 detector with baseline
    mock_b2 = MagicMock()
    mock_b2.node_baselines = {"NODE_01": {"tilt_x": 0.0, "tilt_y": 0.0, "distance": 18.0, "vibration": 0.04}}
    mock_b2.config = {"warning": {"tilt_deg": 15.0, "distance_delta_cm": 2.0, "vibration_g": 1.0}}

    # Readings returned to nominal tilt (1.0 deg < 15.0 warning)
    nom_readings = {"NODE_01": {"tilt_x": 1.0, "tilt_y": 0.0, "distance": 18.0, "vibration": 0.04}}
    reemitted, cleared = mgr.check_escapes("2026-10-27T10:15:01+00:00", nom_readings, [], b2_detector=mock_b2)
    assert "ep1" in cleared
    assert len(reemitted) == 0
    assert mgr.hold_resolutions_log[-1].outcome == "CLEARED"

    # Case 4: Persists case re-emits at timeout (still exceeding warning threshold 16.0 deg >= 15.0 deg)
    mgr.start_hold(cand, readings)
    high_readings = {"NODE_01": {"tilt_x": 16.0, "tilt_y": 0.0, "distance": 18.0, "vibration": 0.04}}
    reemitted, cleared = mgr.check_escapes("2026-10-27T10:15:01+00:00", high_readings, [], b2_detector=mock_b2)
    assert "ep1" in reemitted
    assert len(cleared) == 0
    assert mgr.hold_resolutions_log[-1].outcome == "REEMITTED_BY_TIMEOUT_PERSISTENCE"


def test_cache_hit_makes_no_api_calls(tmp_path):
    mock_client = MagicMock()
    analyst = Analyst(
        cache_dir=str(tmp_path / "cache"),
        runs_dir=str(tmp_path / "runs"),
        client=mock_client
    )
    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="ep_cache_test",
        trigger_time="2026-03-30T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["tilt"]
    )
    # Save a cached result manually
    dummy_res = AnalystResult(
        parsed={"recommendation": "KEEP"},
        transcript=[],
        tool_calls=[],
        tool_results={},
        token_usage={},
        cost_usd=0.005,
        latency_sec=0.1,
        prompt_hash=analyst.prompt_hash,
        from_cache=False
    )
    analyst._save_cache("ep_cache_test", dummy_res)

    res = analyst.investigate(cand, [], {})
    assert res is not None
    assert res.from_cache is True
    # Verify no HTTP calls made
    mock_client.post.assert_not_called()


def test_budget_guard_stops_calls(tmp_path):
    analyst = Analyst(
        cache_dir=str(tmp_path / "cache"),
        runs_dir=str(tmp_path / "runs"),
        budget_usd=0.01
    )
    analyst.total_cost_spent = 0.02  # Already exceeded

    cand = CandidateEpisode(
        scenario_id="S1",
        episode_id="ep_budget_test",
        trigger_time="2026-03-30T10:00:00+00:00",
        node_ids=["NODE_01"],
        level="WARNING",
        trigger_channels=["tilt"]
    )
    res = analyst.investigate(cand, [], {})
    assert res is None  # Stops and falls back to None (which guard maps to KEEP)


def test_agent_never_sees_ground_truth():
    detector = AgentDetector()
    tainted_meta = {
        "scenario_id": "SCEN_TEST",
        "type": "accelerating_creep",
        "is_hazard": True,
        "onset_time": "2026-03-30T11:00:00+00:00",
        "collapse_time": "2026-03-30T13:00:00+00:00",
        "node_coordinates_m": {"NODE_01": [0, 0]},
        "blast_schedule": []
    }
    detector.reset(tainted_meta)
    # Verify detector.scenario_meta strictly stripped all truth fields
    assert "type" not in detector.scenario_meta
    assert "is_hazard" not in detector.scenario_meta
    assert "onset_time" not in detector.scenario_meta
    assert "collapse_time" not in detector.scenario_meta

