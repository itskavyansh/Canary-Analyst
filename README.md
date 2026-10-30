# Canary Analyst

Canary Analyst is built entirely during the Meta Global AI Developer Hackathon (Oct 27 - Nov 4, 2026). It is the AI layer for ProjectCanary, a student team's earlier sensor-hardware concept. All code in this repo was written during the hackathon. All sensor data is simulated unless explicitly stated.

## Overview
Canary Analyst monitors ground-subsidence sensor networks, analyzes telemetry, predicts geomechanical risk events, and provides automated decision-support insights powered by Meta's Muse Spark 1.3 foundation model.

## Project Structure
- `/agent`: Autonomous reasoning agent, tools, and LLM orchestration (Muse Spark 1.3).
- `/generator`: Synthetic sensor telemetry and geomechanical event stream generation.
- `/engine`: Subsidence analytics, spatial-temporal calculations, and hazard detection.
- `/eval`: Benchmark evaluations, test scenarios, and model scoring.
- `/api`: FastAPI backend services.
- `/web`: Web dashboard interface.
- `/tests`: Test suite (unit, integration, regression).
- `/docs`: Documentation, architecture diagrams, and hardware integration specs.

## Setup
1. Clone the repository and navigate into the root directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment:
   ```bash
   cp .env.example .env
   # Add your META_API_KEY to .env
   ```
4. Run agent smoke test:
   ```bash
   python agent/smoke_test.py
   ```

