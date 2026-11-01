# Canary Analyst: Autonomous Geotechnical AI Analyst for Subsidence Networks

Canary Analyst monitors ground subsidence above abandoned underground coal workings using surface sensor arrays to detect catastrophic collapses early. It couples a multi-tool autonomous AI agent with a deterministic safety guard to eliminate false alarms without delaying or missing life-critical hazard alerts.

Live Interactive Demo: [https://itskavyansh.github.io/Canary-Analyst/](https://itskavyansh.github.io/Canary-Analyst/)

---

## Table of Contents
1. [Headline Benchmark Results](#headline-benchmark-results)
2. [What It Does](#what-it-does)
3. [Hackathon Provenance & Hardware Credit](#hackathon-provenance--hardware-credit)
4. [Evaluation Protocol](#evaluation-protocol)
5. [Limitations & Engineering Disclaimers](#limitations--engineering-disclaimers)
6. [Related Work & Motivation](#related-work--motivation)
7. [How to Run](#how-to-run)
8. [Repository Map](#repository-map)
9. [Models Used & Cost Efficiency](#models-used--cost-efficiency)

---

## Headline Benchmark Results

All four detectors evaluated on the held-out test split ($N=300$, seed 2026) under a strict no-lookahead streaming contract:

| Metric | B0 (Naive Raw Thresholds) | B1 (Stateful Persistence + Trend) | B2.1 (Frozen Engineered Rules) | AGENT (Muse Spark 1.3 + Guard) |
| :--- | :---: | :---: | :---: | :---: |
| **Hazard Detection Rate** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |
| **Overall False Alarm Rate** | 40.0% | 39.3% | 8.0% | **5.3%** |
| 95% Bootstrap CI (FA) | [34.0%, 45.7%] | [34.0%, 45.0%] | [5.0%, 11.3%] | [3.0%, 7.7%] |
| **Median Lead Time (min)** | 10.0 min | 57.0 min | 52.0 min | **52.0 min** |
| IQR Lead Time (p25–p75) | 0.5–31.5 min | 42.0–78.5 min | 44.5–60.5 min | 44.5–60.5 min |
| Detected Before Collapse | 74.4% | 100.0% | 100.0% | **100.0%** |
| Mean Alert Episodes / Scenario | 0.81 | 1.02 | 0.44 | **0.42** |

*Paired Evaluation Line*: Across all 214 non-hazard test scenarios, the paired exact sign test versus the frozen B2.1 baseline removed 8 false alarms with 0 added ($p = 0.0078$, statistically significant).

---

## What It Does

- **Perceive-decide-act agent loop with five tools**: Investigates candidate anomalies by querying spatial neighbors, physical baselines, acoustic emissions, scheduled blasts, and sensor diagnostics.
- **Fail-closed deterministic safety guard**: Audits all agent downgrade proposals against physical invariants before approval, ensuring unverified hypotheses default to `KEEP`.
- **Audit log of replayable investigation transcripts**: Retains a complete cryptographic chain of tool inputs, outputs, and reasoning steps for forensic post-incident review.
- **Structured JSON output**: Strictly enforces schema validation across confidence levels, root-cause hypotheses, and operational recommendations.
- **Native tool calling with Muse Spark 1.3 through the Meta Model API**: Coordinates tool calls natively using standard parameter contracts to triage live sensor streams.

---

## Hackathon Provenance & Hardware Credit

All code in this repository was written between Oct 27 and Nov 4, 2026 for the Meta Global AI Developer Hackathon. The ProjectCanary sensor hardware and its data format are the author's earlier prototype and are not code in this repository.

---

## Evaluation Protocol

The system was evaluated across two distinct splits:
1. **Development Split ($N=300$, seed 42)**: Used for exploratory failure analysis, threshold calibration, and baseline tuning.
2. **Held-Out Test Split ($N=300$, seed 2026)**: Evaluated only after freezing all detectors, guard gates, prompts, and configurations.

Everything was frozen before the test run (git tag `frozen-before-test`, commit `77ae260`, documented in [`results/freeze_manifest.json`](results/freeze_manifest.json)), and all results are reported exactly as measured without post-unblinding adjustments. After the freeze tag, one commit added a missing `typing` import so the code also runs on Python 3.11 to 3.13, with no change in behaviour.

---

## Limitations & Engineering Disclaimers

1. **Approximation of Noise**: Sensor noise was measured on prototype bench logs sampled about once per second, then applied to simulated 1-minute readings, and the generator caps noise levels (distance 0.35 cm, tilt 0.20 degrees, vibration 0.015 g), so simulated noise is an approximation. The generator has no temperature drift, which real tiltmeters show.
2. **Synthetic Hazards vs Reality**: Simulated hazards are easier than real collapses because synthetic collapse profiles follow continuous deterministic acceleration curves, whereas real geomechanical failures often feature brittle, stick-slip discontinuities.
3. **Silent Sensor Faults**: Silent sensor faults remain unresolved; unflagged calibration drift on a single axis without diagnostic hardware error codes cannot be reliably distinguished from localized ground strain.
4. **Benign Cause Misclassifications**: Benign causes are often mislabelled, but the fail-closed safety guard preserves system safety by defaulting unproven hypotheses to `KEEP`.
5. **Demonstration Thresholds**: Thresholds (15° tilt, 2.0 cm displacement, 1.0 g vibration) are engineering demonstration values; real deployments require site-specific baseline surveys.
6. **Operational Scope**: The system provides automated decision support; human geotechnical engineers retain command authority for site evacuations.

---

## Related Work & Motivation

These sources motivate the problem; none is used as data in our benchmark.

- [Louisiana Department of Energy and Natural Resources, Sulphur Mines Monthly Deformation Reports (October 2024)](https://www.dnr.louisiana.gov/assets/OC/SulphurMines/InSAR/DeformationReports/October_2024_Deformation_Report.pdf): Monthly monitoring reports document short-lived tilt anomalies caused by weather precipitation and mechanical activity near surface sensors, demonstrating the operational necessity of filtering false alarms.
- [Qiu et al., JISDM 2025, Tiltmeters as a Low-Cost Technology for Baseline Ground-Movement Monitoring](https://jisdm2025.gik.kit.edu/downloads/JISDM2025_Qiu_et_al.pdf): Field evaluation of low-cost tilt sensors confirms that thermal variations and temperature drift directly affect tiltmeter stability over multi-day monitoring periods.
- [Gu et al., Sustainability 2022, 14(16), 10421, 'Research on Mining Maximum Subsidence Prediction Based on Genetic Algorithm Combined with XGBoost Model'](https://www.mdpi.com/2071-1050/14/16/10421): Historical modeling predicts ultimate maximum subsidence extent from 78 geological and extraction parameters, contrasting with real-time streaming anomaly triage.

---

## How to Run

**Prerequisites**: Python 3.11+ (verified on Python 3.11, 3.12, 3.13, and 3.14).

```bash
pip install -r requirements.txt
```

### 1. Scenario Generator
```bash
# Generate the 300-scenario development split (seed 42)
python -m generator.build_dataset --n 300 --seed 42 --out data/scenarios
```

### 2. Evaluation Harness
```bash
# Run unit and integration tests (no API calls)
python -m pytest tests/ -q

# Run baseline detectors on the dev split (no API calls; note that detector B2 is the frozen B2.1 baseline)
python -m eval.run_eval --detectors B0,B1,B2 --split dev

# Run all detectors including the AI agent on the dev split (requires META_API_KEY in .env)
python -m eval.run_eval --detectors B0,B1,B2,AGENT --split dev

# Run benchmark evaluation on the frozen held-out test split
python -m eval.run_eval --detectors B0,B1,B2,AGENT --split test --final
```

### 3. Demo Export & Web Application
```bash
# Run web application locally (pre-exported static demo data is already included in web/public/demo/)
cd web
npm install
npm run dev

# Build production static bundle for GitHub Pages / Vercel
npm run build

# (Optional) Re-export demo scenarios from local test split & agent cache
cd ..
python -m eval.export_demo
```

---

## Repository Map

```text
canary-analyst/
├── agent/
│   ├── analyst.py              # Autonomous LLM analyst with ReAct tool-calling loop
│   ├── guard.py                # Deterministic Safety Guard checking physical invariants
│   ├── tools.py                # Five diagnostic tools querying array context
│   └── prompts/
│       └── analyst_v1.md       # Frozen system prompt
├── engine/
│   ├── baseline_b0.py          # Naive instantaneous threshold baseline
│   ├── baseline_b1.py          # Persistence and linear trend baseline
│   ├── baseline_b2.py          # Multimodal engineered baseline
│   └── b2_frozen.json          # Frozen parameter weights for B2.1
├── eval/
│   ├── run_eval.py             # Evaluation harness streaming tick-by-tick
│   ├── export_demo.py          # Exporter generating static web demo artifacts
│   └── report_model_swap.py    # Multi-model comparison report generator
├── generator/
│   └── scenarios.py            # Synthetic scenario generator (7 failure / benign classes)
├── docs/
│   ├── results.md              # Detailed evaluation report, tables, and ablations
│   ├── safety_design.md        # Safety guard architecture and verification gates
│   └── model_swap_prereg.md    # Pre-registration for model-swap sensitivity experiment
├── web/
│   ├── src/                    # React + Vite interactive dashboard
│   └── public/demo/            # Exported demo scenarios and summary JSON
└── tests/                      # Pytest test suite
```

---

## Models Used & Cost Efficiency

- **Foundation Model**: `muse-spark-1.3` (Meta Model API), supporting native tool calling, reasoning effort, and temperature parameters.
- **Evaluation Cost**: Total test split inference cost was **$2.99 USD** across 142 candidate anomaly episodes ($0.0211 / candidate).
- **Evidence Integrity**: **100.0% evidence validity rate** (761 / 761 cited evidence IDs verified against raw tool hashes).
