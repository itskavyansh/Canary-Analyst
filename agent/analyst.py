import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from dotenv import load_dotenv

from agent.tool_schemas import TOOL_SCHEMAS, ToolDispatcher
from engine.candidates import CandidateEpisode

load_dotenv()

# Schema definition for structured JSON output
ANALYST_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "analyst_investigation_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "hypothesis": {
                    "type": "string",
                    "enum": [
                        "blast",
                        "machinery_impact",
                        "environmental_tilt",
                        "sensor_fault",
                        "sensor_stuck",
                        "ground_movement",
                        "unclear"
                    ]
                },
                "recommendation": {
                    "type": "string",
                    "enum": ["KEEP", "DOWNGRADE"]
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0.0 and 1.0"
                },
                "cited_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "brief": {
                    "type": "string",
                    "description": "Plain language summary max 90 words for mine safety officer"
                }
            },
            "required": [
                "hypothesis",
                "recommendation",
                "confidence",
                "cited_evidence_ids",
                "findings",
                "brief"
            ],
            "additionalProperties": False
        }
    }
}

SCHEMA_VERSION = "v1"

# Cost rates per million tokens
COST_PER_M_INPUT = 1.25
COST_PER_M_CACHED_INPUT = 0.15
COST_PER_M_OUTPUT = 4.25


@dataclass
class AnalystResult:
    parsed: Optional[Dict[str, Any]]
    transcript: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    tool_results: Dict[str, Any]  # evidence_id -> tool output or tool_name -> result
    token_usage: Dict[str, Any]
    cost_usd: float
    latency_sec: float
    prompt_hash: str
    from_cache: bool = False


class GlobalBudgetExceeded(Exception):
    pass


class Analyst:
    def __init__(
        self,
        model: str = "muse-spark-1.3",
        prompt_path: Optional[str] = None,
        cache_dir: str = "results/agent_cache",
        runs_dir: str = "results/agent_runs",
        budget_usd: Optional[float] = None,
        max_tool_rounds: int = 8,
        temperature: float = 0.1,
        reasoning_effort: str = "low",
        client: Optional[Any] = None
    ):
        self.model = model
        self.max_tool_rounds = max_tool_rounds
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.client = client

        # Prompt resolution
        if prompt_path is None:
            prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "analyst_v1.md")
        self.prompt_path = prompt_path
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()
        self.prompt_hash = hashlib.sha256(self.system_prompt.encode("utf-8")).hexdigest()

        # Cache & run directories
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        # Budget guard
        env_budget = os.getenv("AGENT_BUDGET_USD")
        if budget_usd is not None:
            self.budget_usd = budget_usd
        elif env_budget:
            self.budget_usd = float(env_budget)
        else:
            self.budget_usd = 20.0

        self.total_cost_spent: float = 0.0

    def compute_cost(self, usage: Dict[str, Any]) -> float:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        prompt_details = usage.get("prompt_tokens_details", {}) or {}
        cached_tokens = prompt_details.get("cached_tokens", 0)
        uncached_prompt_tokens = max(0, prompt_tokens - cached_tokens)

        cost = (
            (uncached_prompt_tokens / 1_000_000.0) * COST_PER_M_INPUT
            + (cached_tokens / 1_000_000.0) * COST_PER_M_CACHED_INPUT
            + (completion_tokens / 1_000_000.0) * COST_PER_M_OUTPUT
        )
        return cost

    def _get_cache_key(self, candidate_id: str) -> str:
        raw = f"{self.model}:{self.prompt_hash}:{candidate_id}:{SCHEMA_VERSION}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_cache(self, candidate_id: str) -> Optional[AnalystResult]:
        cache_key = self._get_cache_key(candidate_id)
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AnalystResult(
                    parsed=data.get("parsed"),
                    transcript=data.get("transcript", []),
                    tool_calls=data.get("tool_calls", []),
                    tool_results=data.get("tool_results", {}),
                    token_usage=data.get("token_usage", {}),
                    cost_usd=data.get("cost_usd", 0.0),
                    latency_sec=data.get("latency_sec", 0.0),
                    prompt_hash=data.get("prompt_hash", self.prompt_hash),
                    from_cache=True
                )
            except Exception:
                return None
        return None

    def _save_cache(self, candidate_id: str, result: AnalystResult) -> None:
        cache_key = self._get_cache_key(candidate_id)
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            temp_file = cache_file.with_suffix(".tmp")
            data = asdict(result)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(cache_file)
        except Exception:
            pass

    def _save_run_transcript(self, candidate_id: str, result: AnalystResult) -> None:
        run_file = self.runs_dir / "transcripts.jsonl"
        entry = {
            "timestamp": time.time(),
            "candidate_id": candidate_id,
            "prompt_hash": self.prompt_hash,
            "result": asdict(result)
        }
        try:
            with open(run_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _call_api_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        api_key = os.getenv("META_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        url = "https://api.meta.ai/v1/chat/completions"

        max_tries = 5
        backoff = 1.0

        for attempt in range(max_tries):
            try:
                if self.client:
                    # Test spy or custom client
                    resp = self.client.post(url, headers=headers, json=payload, timeout=45.0)
                else:
                    with httpx.Client(timeout=45.0) as client:
                        resp = client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                else:
                    # Non-retryable error
                    return {"error": f"HTTP {resp.status_code}: {resp.text}"}
            except Exception as e:
                time.sleep(backoff)
                backoff *= 2.0
                if attempt == max_tries - 1:
                    return {"error": str(e)}

        return {"error": "Max retries exceeded"}

    def investigate(
        self,
        candidate: CandidateEpisode,
        scenario_readings: List[Dict[str, Any]],
        scenario_meta: Dict[str, Any]
    ) -> Optional[AnalystResult]:
        """Investigate a candidate alert.
        Strictly sanitizes inputs: never receives scenario type, ground truth, or onset/collapse.
        """
        # Check cache
        cached = self._load_cache(candidate.episode_id)
        if cached is not None:
            return cached

        # Check budget
        if self.total_cost_spent >= self.budget_usd:
            print(f"[Analyst WARNING] Global budget ${self.budget_usd:.2f} exceeded! Total spent: ${self.total_cost_spent:.2f}. Falling back to KEEP.")
            return None

        start_time = time.time()

        # Sanitize metadata (ONLY node_layout and blast_schedule)
        node_layout = scenario_meta.get("node_layout", {})
        blast_schedule = scenario_meta.get("blast_schedule", [])

        # Initialize dispatcher
        dispatcher = ToolDispatcher(
            readings=scenario_readings,
            blast_schedule=blast_schedule,
            as_of=candidate.trigger_time,
            node_layout=node_layout
        )

        user_content = (
            f"CANDIDATE ALERT INVESTIGATION:\n"
            f"- Candidate ID: {candidate.episode_id}\n"
            f"- Detection / As-Of Time: {candidate.trigger_time}\n"
            f"- Severity Level: {candidate.level}\n"
            f"- Suspect Node IDs: {candidate.node_ids}\n"
            f"- Triggering Channels: {candidate.trigger_channels}\n"
            f"- Array Layout: Square 4-node network (coordinates in meters: {node_layout})\n\n"
            f"Perform an active multi-tool investigation into this event. You must call `get_sensor_health` "
            f"and `compare_neighbor_nodes` at least once. Conclude with your diagnostic hypothesis, findings citing valid evidence IDs, "
            f"recommendation ('KEEP' or 'DOWNGRADE'), confidence, and concise brief."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content}
        ]

        transcript: List[Dict[str, Any]] = list(messages)
        accumulated_tool_calls: List[Dict[str, Any]] = []
        collected_tool_results: Dict[str, Any] = {}
        total_usage: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0}
        }

        # Step A: Tool investigation loop
        tool_round = 0
        while tool_round < self.max_tool_rounds:
            tool_round += 1

            payload = {
                "model": self.model,
                "messages": messages,
                "tools": TOOL_SCHEMAS,
                "temperature": self.temperature,
                "reasoning_effort": self.reasoning_effort,
                "max_completion_tokens": 2048
            }

            resp_json = self._call_api_with_retry(payload)
            if "error" in resp_json or not resp_json.get("choices"):
                # Persistent failure -> fallback to None (guard keeps alert)
                return None

            choice = resp_json["choices"][0]
            msg = choice.get("message", {})
            usage = resp_json.get("usage", {})

            # Accumulate usage
            total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            total_usage["total_tokens"] += usage.get("total_tokens", 0)
            total_usage["prompt_tokens_details"]["cached_tokens"] += (
                usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            )
            total_usage["completion_tokens_details"]["reasoning_tokens"] += (
                usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
            )

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                # Model finished calling tools
                messages.append(msg)
                transcript.append(msg)
                break

            # Process tool calls
            messages.append(msg)
            transcript.append(msg)

            for tc in tool_calls:
                accumulated_tool_calls.append(tc)
                call_id = tc.get("id")
                fn_name = tc.get("function", {}).get("name", "")
                fn_args_raw = tc.get("function", {}).get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw)
                except Exception:
                    fn_args = {}

                tool_res = dispatcher.dispatch(fn_name, fn_args)
                tool_res["tool"] = fn_name
                ev_id = tool_res.get("evidence_id")
                if ev_id:
                    collected_tool_results[ev_id] = tool_res
                # Also store by call_id / tool_name for lookup
                collected_tool_results[f"{fn_name}_{len(accumulated_tool_calls)}"] = tool_res

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(tool_res)
                }
                messages.append(tool_msg)
                transcript.append(tool_msg)

        # Step B: Final synthesis call with structured response_format
        final_prompt_msg = {
            "role": "user",
            "content": (
                "Investigation complete. Provide your final diagnostic assessment in strict JSON schema. "
                "Include hypothesis, recommendation (KEEP or DOWNGRADE), confidence, cited_evidence_ids, "
                "up to 4 findings with specific numbers from evidence, and a brief max 90 words for the mine safety officer."
            )
        }
        messages.append(final_prompt_msg)
        transcript.append(final_prompt_msg)

        final_payload = {
            "model": self.model,
            "messages": messages,
            "response_format": ANALYST_OUTPUT_SCHEMA,
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": 2048
        }

        final_resp = self._call_api_with_retry(final_payload)
        if "error" in final_resp or not final_resp.get("choices"):
            return None

        final_choice = final_resp["choices"][0]
        final_msg = final_choice.get("message", {})
        final_usage = final_resp.get("usage", {})

        total_usage["prompt_tokens"] += final_usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += final_usage.get("completion_tokens", 0)
        total_usage["total_tokens"] += final_usage.get("total_tokens", 0)
        total_usage["prompt_tokens_details"]["cached_tokens"] += (
            final_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        )
        total_usage["completion_tokens_details"]["reasoning_tokens"] += (
            final_usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        )

        transcript.append(final_msg)
        raw_content = final_msg.get("content", "")

        try:
            parsed = json.loads(raw_content)
        except Exception:
            parsed = None

        cost = self.compute_cost(total_usage)
        self.total_cost_spent += cost
        latency = time.time() - start_time

        result = AnalystResult(
            parsed=parsed,
            transcript=transcript,
            tool_calls=accumulated_tool_calls,
            tool_results=collected_tool_results,
            token_usage=total_usage,
            cost_usd=cost,
            latency_sec=latency,
            prompt_hash=self.prompt_hash,
            from_cache=False
        )

        self._save_cache(candidate.episode_id, result)
        self._save_run_transcript(candidate.episode_id, result)

        return result

