# Canary Analyst Sandbox Backend

An interactive simulation and evaluation service for geotechnical anomaly detection. The sandbox runs judge-designed scenarios through the frozen Baseline B2.1 detector and autonomous Agent (Analyst + SafetyGuard).

## Features

- **Synthetic Scenario Simulation**: Generates 4-node 1 reading/min time series with calibrated AR(1) noise from prototype profiles.
- **Candidate Path Evaluation**: Streams scenarios through the frozen Baseline B2.1 engine under strict no-lookahead constraints.
- **Autonomous Agent Investigation**: Investigates candidate episodes using the frozen Analyst model with fresh temporary cache and run directories per request.
- **Deterministic Safety Guard**: Evaluates model diagnoses and hold logic before any downgrade decision is honored.
- **Production Guardrails**:
  - IP-based rate limiting (5 runs per minute per IP).
  - Concurrency throttling (maximum 2 active agent jobs simultaneously).
  - Configurable daily spending cap (`SANDBOX_DAILY_USD`).
  - In-memory job store with automatic 30-minute expiration.
  - Strict CORS limited to `https://itskavyansh.github.io` and `http://localhost:5173`.

## Environment Variables

Configure these variables in your `.env` file or export them directly in your shell:

| Variable | Description | Default |
|---|---|---|
| `META_API_KEY` | Bearer API token for Muse Spark model | (None; if missing, agent reports status unavailable) |
| `AGENT_MODEL` | Model identifier for Analyst | `muse-spark-1.3` |
| `SANDBOX_MAX_CANDIDATES` | Maximum candidate alerts investigated per scenario run | `3` |
| `SANDBOX_DAILY_USD` | Daily expenditure cap in USD | `5.0` |

## Local Run Command

Run uvicorn as a single worker from the project root:

```powershell
uvicorn sandbox.service:app --host 127.0.0.1 --port 8000 --workers 1
```

## API Endpoints

- `GET /api/sandbox/health`: Health status and daily spend metrics.
- `POST /api/sandbox/run`: Simulates scenario, evaluates B2.1 alerts, downsamples series for plotting, and enqueues an Agent investigation if candidate alerts are detected.
- `GET /api/sandbox/job/{job_id}`: Retrieves job progress and per-candidate findings, evidence verification, and guard actions.
