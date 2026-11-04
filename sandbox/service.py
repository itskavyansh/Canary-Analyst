"""FastAPI sandbox service for Canary Analyst.

Runs judge-designed scenarios through the frozen B2.1 and Agent pipeline.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, List, Literal, Optional
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Note: do not call load_dotenv(override=True) so unsetting in env is respected
load_dotenv()

from engine.baseline_b2 import BaselineB2, B2_CONFIG
from engine.candidates import CandidateEpisode, CandidateGenerator
from agent.analyst import Analyst, AnalystResult
from agent.guard import SafetyGuard, HoldManager
from sandbox.simulator import build_scenario, NODE_IDS

SANDBOX_NOTICE = "Sandbox run on a synthetic scenario built from your inputs. Not a benchmark result."

app = FastAPI(
    title="Canary Analyst Sandbox Service",
    description="Interactive sandbox backend for geotechnical anomaly analysis",
    version="1.0.0",
)

# CORS restricted strictly to approved origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://itskavyansh.github.io",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency & executor
agent_executor = ThreadPoolExecutor(max_workers=4)

# In-memory stores and state
# Rate limiter: IP -> list of timestamps
ip_request_timestamps: Dict[str, List[float]] = {}
rate_limit_lock = asyncio.Lock()


def get_real_client_ip(request: Request) -> str:
    """Extract real client IP: first entry of X-Forwarded-For if present, else client host."""
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[0]
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def extract_client_ip_from_values(forwarded_for: Optional[str], client_host: Optional[str]) -> str:
    """Unit-testable helper for client IP resolution."""
    if forwarded_for:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if parts:
            return parts[0]
    return client_host or "127.0.0.1"


# Unit-style check for client IP resolution
assert extract_client_ip_from_values("203.0.113.195, 70.41.3.18", "127.0.0.1") == "203.0.113.195"
assert extract_client_ip_from_values(None, "192.168.1.100") == "192.168.1.100"

# Concurrency semaphore for running agent jobs (max 2 concurrent)
MAX_CONCURRENT_JOBS = 2
agent_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
running_job_count = 0
running_job_lock = asyncio.Lock()

# Daily budget tracker
daily_spend_usd = 0.0
daily_spend_date = datetime.now(timezone.utc).date()
spend_lock = asyncio.Lock()

# Job store: job_id -> job_dict
# 30 minute expiry
JOB_EXPIRY_SECONDS = 30 * 60
job_store: Dict[str, Dict[str, Any]] = {}
job_store_lock = asyncio.Lock()


async def check_rate_limit(client_ip: str) -> bool:
    """Enforce 5 runs per minute per IP."""
    now = time.time()
    cutoff = now - 60.0
    async with rate_limit_lock:
        timestamps = ip_request_timestamps.get(client_ip, [])
        # Filter older than 60s
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= 5:
            ip_request_timestamps[client_ip] = timestamps
            return False
        timestamps.append(now)
        ip_request_timestamps[client_ip] = timestamps
        return True


async def get_daily_spend() -> float:
    global daily_spend_usd, daily_spend_date
    now_date = datetime.now(timezone.utc).date()
    async with spend_lock:
        if now_date != daily_spend_date:
            daily_spend_date = now_date
            daily_spend_usd = 0.0
        return daily_spend_usd


async def add_daily_spend(cost: float) -> None:
    global daily_spend_usd, daily_spend_date
    now_date = datetime.now(timezone.utc).date()
    async with spend_lock:
        if now_date != daily_spend_date:
            daily_spend_date = now_date
            daily_spend_usd = 0.0
        daily_spend_usd += cost


async def cleanup_expired_jobs() -> None:
    now = time.time()
    async with job_store_lock:
        expired = [
            jid for jid, job in job_store.items()
            if now - job.get("created_at", now) > JOB_EXPIRY_SECONDS
        ]
        for jid in expired:
            del job_store[jid]


def downsample_series(readings: List[Dict[str, Any]], max_points: int = 120) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Downsample per-node per-channel series to at most max_points for plotting."""
    by_node: Dict[str, List[Dict[str, Any]]] = {nid: [] for nid in NODE_IDS}
    for r in readings:
        nid = r.get("node_id")
        if nid in by_node:
            by_node[nid].append(r)

    channels = ["tilt_x", "tilt_y", "vibration", "distance", "piezo_peak"]
    result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {nid: {ch: [] for ch in channels} for nid in NODE_IDS}

    for nid, node_readings in by_node.items():
        total_len = len(node_readings)
        if total_len <= max_points:
            selected_indices = list(range(total_len))
        else:
            step = (total_len - 1) / float(max_points - 1)
            selected_indices = sorted(list({int(round(i * step)) for i in range(max_points)}))

        for idx in selected_indices:
            r = node_readings[idx]
            ts = r.get("timestamp", "")
            for ch in channels:
                val = r.get(ch, 0.0)
                result[nid][ch].append({"timestamp": ts, "value": val})

    return result


class RunRequest(BaseModel):
    preset: Optional[str] = Field("single_node_move", description="Scenario preset name")
    node: Optional[str] = Field("NODE_01", description="Target node for single-node presets")
    onset_minute: Optional[int] = Field(35, description="Minute when event begins (>= 35)")
    rise_minutes: Optional[int] = Field(0, description="Rise duration in minutes (0 = sudden)")
    tilt_deg: Optional[float] = Field(0.0, description="Tilt magnitude in degrees (0 to 45)")
    vibration_g: Optional[float] = Field(0.0, description="Vibration magnitude in g (0 to 5)")
    distance_cm: Optional[float] = Field(0.0, description="Distance delta in cm (0 to 20)")
    duration_minutes: Optional[int] = Field(90, description="Total simulation minutes (60 to 120)")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")


def execute_agent_job_sync(
    job_id: str,
    candidates: List[CandidateEpisode],
    accumulated_readings_up_to: Dict[str, List[Dict[str, Any]]],
    scenario_meta: Dict[str, Any],
    max_candidates: int,
    model: str,
    daily_budget_usd: float,
    current_spend: float,
) -> Dict[str, Any]:
    """Synchronous worker execution of agent investigation for candidates."""
    temp_dir = tempfile.mkdtemp(prefix=f"sandbox_run_{job_id}_")
    try:
        api_key = os.getenv("META_API_KEY", "")
        if not api_key:
            return {
                "status": "unavailable",
                "message": "META_API_KEY is not configured",
                "candidates": [],
                "seconds": 0.0,
                "cost": 0.0,
            }

        if current_spend >= daily_budget_usd:
            return {
                "status": "daily budget reached",
                "message": f"Daily budget of ${daily_budget_usd:.2f} reached",
                "candidates": [],
                "seconds": 0.0,
                "cost": 0.0,
            }

        start_time = time.time()
        analyst = Analyst(
            model=model,
            cache_dir=temp_dir,
            runs_dir=temp_dir,
            budget_usd=max(0.1, daily_budget_usd - current_spend),
        )
        guard = SafetyGuard()
        hold_manager = HoldManager()

        cands_to_run = candidates[:max_candidates]
        candidate_results: List[Dict[str, Any]] = []
        total_job_cost = 0.0

        for cand in cands_to_run:
            c_start = time.time()
            # Unique candidate id with uuid to guarantee fresh evaluation
            unique_cand_id = f"{cand.episode_id}_{uuid.uuid4().hex[:8]}"
            eval_cand = CandidateEpisode(
                scenario_id=cand.scenario_id,
                episode_id=unique_cand_id,
                trigger_time=cand.trigger_time,
                node_ids=cand.node_ids,
                level=cand.level,
                trigger_channels=cand.trigger_channels,
            )

            rec_history = accumulated_readings_up_to.get(cand.trigger_time, [])

            # Run investigation
            analyst_res: Optional[AnalystResult] = None
            investigate_error = None
            try:
                analyst_res = analyst.investigate(
                    candidate=eval_cand,
                    scenario_readings=rec_history,
                    scenario_meta=scenario_meta,
                )
            except Exception as e:
                investigate_error = str(e)

            c_seconds = time.time() - c_start
            c_cost = analyst_res.cost_usd if analyst_res else 0.0
            total_job_cost += c_cost

            if analyst_res is None:
                # API failure or budget stop
                guard_dec = guard.evaluate(eval_cand, None)
                candidate_results.append({
                    "episode_id": cand.episode_id,
                    "unique_id": unique_cand_id,
                    "trigger_time": cand.trigger_time,
                    "level": cand.level,
                    "recommendation": "KEEP",
                    "hypothesis": "unclear",
                    "confidence": 0.0,
                    "brief": "Analyst investigation unavailable or failed.",
                    "findings": [],
                    "cited_evidence_ids": [],
                    "evidence_validity": {},
                    "tool_names": [],
                    "guard_action": guard_dec.action,
                    "failed_conditions": guard_dec.failed_conditions,
                    "hold_created": False,
                    "cost": c_cost,
                    "seconds": c_seconds,
                    "error": investigate_error,
                })
                continue

            parsed = analyst_res.parsed or {}
            recommendation = parsed.get("recommendation", "KEEP")
            hypothesis = parsed.get("hypothesis", "unclear")
            confidence = float(parsed.get("confidence", 0.0))
            brief = parsed.get("brief", "")
            findings = parsed.get("findings", [])
            cited_evidence_ids = parsed.get("cited_evidence_ids", [])

            # Evidence validity
            known_evidence_ids = {
                v.get("evidence_id")
                for v in analyst_res.tool_results.values()
                if isinstance(v, dict) and v.get("evidence_id")
            }
            evidence_validity = {
                eid: (eid in known_evidence_ids) for eid in cited_evidence_ids
            }

            # Tool names extracted from tool_calls and tool_results
            tool_names_set = set()
            for call in analyst_res.tool_calls:
                if isinstance(call, dict):
                    name = call.get("function", {}).get("name") or call.get("name")
                    if name:
                        tool_names_set.add(name)
            for v in analyst_res.tool_results.values():
                if isinstance(v, dict) and v.get("tool"):
                    tool_names_set.add(v["tool"])
            tool_names = sorted(list(tool_names_set))

            # Guard evaluation
            guard_dec = guard.evaluate(eval_cand, analyst_res)
            hold_created = (guard_dec.action == "DOWNGRADE")

            candidate_results.append({
                "episode_id": cand.episode_id,
                "unique_id": unique_cand_id,
                "trigger_time": cand.trigger_time,
                "level": cand.level,
                "recommendation": recommendation,
                "hypothesis": hypothesis,
                "confidence": confidence,
                "brief": brief,
                "findings": findings,
                "cited_evidence_ids": cited_evidence_ids,
                "evidence_validity": evidence_validity,
                "tool_names": tool_names,
                "guard_action": guard_dec.action,
                "failed_conditions": guard_dec.failed_conditions,
                "hold_created": hold_created,
                "cost": c_cost,
                "seconds": c_seconds,
            })

        total_seconds = time.time() - start_time
        return {
            "status": "done",
            "candidates": candidate_results,
            "seconds": total_seconds,
            "cost": total_job_cost,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "candidates": [],
            "seconds": 0.0,
            "cost": 0.0,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def run_agent_job_background(
    job_id: str,
    candidates: List[CandidateEpisode],
    accumulated_readings_up_to: Dict[str, List[Dict[str, Any]]],
    scenario_meta: Dict[str, Any],
    max_candidates: int,
    model: str,
    daily_budget_usd: float,
) -> None:
    global running_job_count

    loop = asyncio.get_running_loop()
    try:
        async with job_store_lock:
            if job_id in job_store:
                job_store[job_id]["status"] = "running"

        current_spend = await get_daily_spend()

        result = await loop.run_in_executor(
            agent_executor,
            execute_agent_job_sync,
            job_id,
            candidates,
            accumulated_readings_up_to,
            scenario_meta,
            max_candidates,
            model,
            daily_budget_usd,
            current_spend,
        )

        # Update spent budget
        if result.get("cost", 0.0) > 0.0:
            await add_daily_spend(result["cost"])

        async with job_store_lock:
            if job_id in job_store:
                job_store[job_id]["status"] = result.get("status", "done")
                job_store[job_id]["candidates"] = result.get("candidates", [])
                job_store[job_id]["cost"] = result.get("cost", 0.0)
                job_store[job_id]["seconds"] = result.get("seconds", 0.0)
                if "message" in result:
                    job_store[job_id]["message"] = result["message"]

    except Exception as e:
        async with job_store_lock:
            if job_id in job_store:
                job_store[job_id]["status"] = "error"
                job_store[job_id]["message"] = str(e)
    finally:
        async with running_job_lock:
            running_job_count = max(0, running_job_count - 1)
        agent_job_semaphore.release()


@app.get("/api/sandbox/health")
async def health():
    return {
        "status": "ok",
        "service": "Canary Analyst Sandbox",
        "running_jobs": running_job_count,
        "sandbox_notice": SANDBOX_NOTICE,
    }


@app.post("/api/sandbox/run")
async def run_scenario(req: RunRequest, request: Request):
    try:
        # Rate limiting: 5 runs per minute per real client IP
        client_ip = get_real_client_ip(request)
        allowed = await check_rate_limit(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded. Maximum 5 runs per minute per IP.",
                    "sandbox_notice": SANDBOX_NOTICE,
                },
            )

        await cleanup_expired_jobs()

        # Build scenario safely without crashing
        params = req.model_dump()
        seed = params.get("seed")
        readings, meta = build_scenario(params=params, seed=seed)

        # Run Candidate path through frozen Baseline B2.1
        b2 = BaselineB2(B2_CONFIG)
        b2.reset(meta)
        cg = CandidateGenerator(detector=BaselineB2(B2_CONFIG))
        cg.reset(meta)

        by_time: Dict[str, Dict[str, Any]] = {}
        for r in readings:
            ts = r["timestamp"]
            if ts not in by_time:
                by_time[ts] = {}
            by_time[ts][r["node_id"]] = r

        b2_alerts = []
        candidates: List[CandidateEpisode] = []
        accumulated_history: List[Dict[str, Any]] = []
        accumulated_up_to: Dict[str, List[Dict[str, Any]]] = {}

        for ts in sorted(by_time.keys()):
            for nid, r in by_time[ts].items():
                accumulated_history.append(r)
            step_alerts = b2.update(ts, by_time[ts])
            if step_alerts:
                b2_alerts.extend(step_alerts)
            step_cands = cg.update(ts, by_time[ts])
            if step_cands:
                candidates.extend(step_cands)
                # Store snapshot up to candidate trigger time
                accumulated_up_to[ts] = list(accumulated_history)

        # Format alerts
        formatted_alerts = [
            {
                "time": a.time,
                "node_ids": a.node_ids,
                "level": a.level,
                "reason": a.reason,
            }
            for a in b2_alerts
        ]

        # Downsample series for plotting
        series = downsample_series(readings, max_points=120)

        # Check candidate availability
        if not candidates:
            return {
                "inputs": meta.get("applied_params", {}),
                "seed": meta.get("seed"),
                "b2_alerts": formatted_alerts,
                "series": series,
                "job_id": None,
                "message": "no alert: below demonstration thresholds or no sustained change",
                "sandbox_notice": SANDBOX_NOTICE,
            }

        # Candidate alert found -> check API key and daily budget
        api_key = os.getenv("META_API_KEY", "")
        max_cands = int(os.getenv("SANDBOX_MAX_CANDIDATES", "3"))
        daily_limit = float(os.getenv("SANDBOX_DAILY_USD", "5.0"))
        model = os.getenv("AGENT_MODEL", "muse-spark-1.3")
        current_spend = await get_daily_spend()

        if not api_key:
            return {
                "inputs": meta.get("applied_params", {}),
                "seed": meta.get("seed"),
                "b2_alerts": formatted_alerts,
                "series": series,
                "job_id": None,
                "agent_status": "unavailable",
                "message": "Agent unavailable: META_API_KEY is not configured",
                "max_candidates_investigated": max_cands,
                "sandbox_notice": SANDBOX_NOTICE,
            }

        if current_spend >= daily_limit:
            return {
                "inputs": meta.get("applied_params", {}),
                "seed": meta.get("seed"),
                "b2_alerts": formatted_alerts,
                "series": series,
                "job_id": None,
                "agent_status": "daily budget reached",
                "message": f"Daily budget of ${daily_limit:.2f} reached",
                "max_candidates_investigated": max_cands,
                "sandbox_notice": SANDBOX_NOTICE,
            }

        # Check concurrency (at most 2 concurrent agent jobs)
        global running_job_count
        async with running_job_lock:
            if running_job_count >= MAX_CONCURRENT_JOBS:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "At most 2 concurrent agent jobs allowed. Please wait for active investigations to complete.",
                        "sandbox_notice": SANDBOX_NOTICE,
                    },
                )
            running_job_count += 1

        try:
            await agent_job_semaphore.acquire()
        except Exception:
            async with running_job_lock:
                running_job_count = max(0, running_job_count - 1)
            raise

        job_id = f"job_{uuid.uuid4().hex}"
        now_ts = time.time()
        job_info = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now_ts,
            "max_candidates": max_cands,
            "candidates": [],
            "cost": 0.0,
            "seconds": 0.0,
        }

        async with job_store_lock:
            job_store[job_id] = job_info

        # Launch background task
        asyncio.create_task(
            run_agent_job_background(
                job_id=job_id,
                candidates=candidates,
                accumulated_readings_up_to=accumulated_up_to,
                scenario_meta=meta,
                max_candidates=max_cands,
                model=model,
                daily_budget_usd=daily_limit,
            )
        )

        return {
            "inputs": meta.get("applied_params", {}),
            "seed": meta.get("seed"),
            "b2_alerts": formatted_alerts,
            "series": series,
            "job_id": job_id,
            "agent_status": "queued",
            "max_candidates_investigated": max_cands,
            "sandbox_notice": SANDBOX_NOTICE,
        }

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": f"Invalid request or simulation failure: {str(e)}",
                "sandbox_notice": SANDBOX_NOTICE,
            },
        )


@app.get("/api/sandbox/job/{job_id}")
async def get_job_status(job_id: str):
    await cleanup_expired_jobs()
    async with job_store_lock:
        job = job_store.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    return {
        "job_id": job["job_id"],
        "status": job.get("status", "queued"),
        "candidates": job.get("candidates", []),
        "cost": job.get("cost", 0.0),
        "seconds": job.get("seconds", 0.0),
        "message": job.get("message"),
        "sandbox_notice": SANDBOX_NOTICE,
    }
