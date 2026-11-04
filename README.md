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

All four detectors evaluated on the held-out test split (=300$, seed 2026) under a strict no-lookahead streaming contract.

**Key Findings:**
- **Paired Result:** Across all 214 non-hazard test scenarios, the agent removed 8 false alarms and added 0 (exact sign test  = 0.0078$).
- **Hazard Detection & Safety:** 86 of 86 hazards detected and 0 hazard scenarios ever held (all 110 stream hazard candidates recommended KEEP).
- **False-Alarm Scenarios:** 24 to 16 of 300 (8.0% to 5.3%), with the note that the 95% intervals overlap ([5.0, 11.3] and [3.0, 7.7]).
- **Baseline vs Agent Attribution:** Most of the false-alarm reduction (40.0% to 8.0%) comes from the frozen rules baseline B2.1, whose 90-minute projection window was chosen after a sweep on dev data (80/90/100 gave 10.7/6.7/11.2% false alarms); the agent adds a further 8 removals on top, each one checked by the guard.
- **Known Limits:** 12 of 43 silent sensor faults still alarm, results are on simulated data, thresholds are demonstration values.

| Metric | B0 (Naive Raw Thresholds) | B1 (Stateful Persistence + Trend) | B2.1 (Frozen Engineered Rules) | AGENT (Muse Spark 1.3 + Guard) |
| :--- | :---: | :---: | :---: | :---: |
| **Hazard Detection Rate** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |
| **Overall False Alarm Rate** | 40.0% | 39.3% | 8.0% | **5.3%** |
| 95% Bootstrap CI (FA) | [34.0%, 45.7%] | [34.0%, 45.0%] | [5.0%, 11.3%] | [3.0%, 7.7%] |
| **Median Lead Time (min)** | 10.0 min | 57.0 min | 52.0 min | **52.0 min** |
| IQR Lead Time (p25–p75) | 0.5–31.5 min | 42.0–78.5 min | 44.5–60.5 min | 44.5–60.5 min |
| Detected Before Collapse | 74.4% | 100.0% | 100.0% | **100.0%** |
| Mean Alert Episodes / Scenario | 0.81 | 1.02 | 0.44 | **0.42** |

Model sensitivity. The frozen pipeline was also run on the held-out test split with muse-spark-1.2 and 1.1 (cache keys include the model name, so no earlier entries were served). The 1.2 run made live calls for 131 of the 133 candidates on Nov 1. The other 2 (SCENARIO_0062_stuck_sensor_001 and SCENARIO_0183_slow_creep_001) were run live on Nov 4 (about .06) and how the Nov 1 summary handled them is unconfirmed, so the 1.2 figure carries that caveat. If an uninvestigated candidate occurred, the fail-closed SafetyGuard (agent/guard.py line 58) defaults to KEEP, which preserves B2's alert and marks SCENARIO_0062 as a false alarm. False-alarm scenarios of 300: 16 (1.3), 17 (1.2), 15 (1.1). Hazard detection: 86 of 86 for all three. Hold, cost and tool-call comparisons across models are not reported.

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

These sources motivate the problem; none is used as data in our benchmark. We found no public labelled dataset of surface sensor readings above underground workings.

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

- **Foundation Model**: muse-spark-1.3 (Meta Model API), supporting native tool calling, reasoning effort, and temperature parameters.
- **Cross-Model Comparison**: We did not compare against non-Meta models, so we make no claim that Muse Spark beats them.
- **Evaluation Cost**: Total test split inference cost was **.86 USD** across 133 candidate anomaly episodes (.0215 / candidate).
- **Evidence Integrity**: **100.0% evidence validity rate** (714 / 714 cited evidence IDs verified against raw tool hashes).

---

## Corrections and Known Issues

An audit of the evaluation artifacts and code identified several candidate-level inconsistencies and implementation edge cases:

1. **Cache Key Without Split Prefix and Test Rerun**:
   - The original cache key formula in `agent/analyst.py` (`hashlib.sha256(f"{model}:{prompt_hash}:{candidate_id}:v1")`) did not incorporate a dataset split prefix or file hash.
   - Because scenario IDs are shared between the dev and test splits, 16 test candidates were inadvertently served cached outputs from earlier development-split test runs rather than executing live API calls against test data.
   - All 16 candidates were re-run live against true held-out test split telemetry (`data/scenarios_test`) using Muse Spark 1.3 in an isolated, empty cache directory (`results/test_rerun16/`, which is local only and not in the repo, documented in `docs/test_rerun16.md` which is tracked in the repo).
   - All 16 reran live as KEEP; 15 kept the same label (ground_movement) and 1 (SCENARIO_0009_slow_creep_002) changed from unclear (0.55) to ground_movement (0.90); detection and scenario-level results unchanged.
2. **Correction of Stale Candidate-Level Metrics**:
   - As originally published, candidate-level headline metrics reported 142 candidates, $2.99 USD ($2.99488), 761 of 761 evidence IDs valid, and 111 of 115 hazard candidates labelled `ground_movement`.
   - Those original figures included 9 exploratory dev-run cache entries (5 hazard, 4 non-hazard).
   - Filtered strictly to the 133 test stream candidates and incorporating the live test rerun data, the true test set statistics are: 133 candidate episodes, **$2.86 USD** ($2.85577 USD; mean $0.0215 / candidate), **714 of 714** evidence IDs valid (100.0%), and **107 of 110** hazard candidates labelled `ground_movement` (97.3%).
3. **Agent Neighbour Comparison Reference Window**:
   - The `compare_neighbor_nodes` tool uses the first 30 readings of the provided session to establish its baseline median.
   - If a disturbance or step change occurs during those first 30 minutes (as seen in the Nov 3 prototype bench recording at 13:38 IST on NODE_02), the reference absorbs part of the shift, making the tool's finding less sensitive to early offsets.
4. **Two-Node Array Neighbour Verification**:
   - In 2-node prototype bench recording deployments, spatial consistency gates requiring confirmation across at least 3 nodes (such as common-mode environmental tilt rejection) remain inert because the array lacks the geometry of the target 4-node deployment.
5. **Real Prototype Recording Session Duration**:
   - The prototype recording shown in the demo is a single 37-minute unlabelled bench session (13:27 to 14:04 IST on Nov 3, 2026).
   - Older raw logs in `data/real_readings.csv` (such as Sep 13 sessions) did not qualify for full agent pipeline replay because they either monitored only a single node or had active durations under 35 minutes, whereas the baseline detectors require a 30-reading warm-up window.
   - Two Sep 13 sessions did qualify and were replayed through B0, B1 and B2. They produced 0 alerts because NODE_01 had only 13 one-minute readings in the first session and never finished the 30-reading warm-up, so its large tilt and vibration were never judged.
6. **Constant Distance Reading on Prototype Bench**:
   - During the Sep 13 prototype session, NODE_02 reported a constant -1.00 distance reading. The detectors took the constant -1.00 as the node's baseline median, so the change from baseline stayed 0.0 cm and no alert was raised; the cause of the -1.00 reading (probably no echo) is unverified.
7. **Silent Sensor Faults**:
   - 12 of 43 silent sensor fault scenarios still alarm, and 128 of 139 baseline alarm-minutes come from sensor faults.
8. **Noise Profile Calibration and Sampling Interval**:
   - `generator/noise_profile.json` states `source: calibrated_on_prototype_readings` while the README notes the profile was informed by prototype logs.
   - The prototype sensor noise was recorded at approximately 1-second sampling and subsequently applied to simulated 1-minute time steps with noise caps (distance 0.35 cm, tilt 0.20 deg, vibration 0.015 g), meaning simulated noise is an approximation and lacks real-world environmental temperature drift.
9. **Implementation Edge Cases Identified in Code Walkthrough**:
   - KeyError in B2 Rule C can occur when a node first appears in the same update as another node's 10 cm jump; Rule C neighbour comparison is order-dependent; a 15-minute per-node cooldown can hide a WARNING to CRITICAL escalation; detection metric is not node-aware and counts WARNING; candidate channel guess is by substring; escalation candidates reuse the episode id (possible cache collision, unchecked); --final can be bypassed with --scenarios.
10. **Model-Swap Report Script**:
   - eval/report_model_swap.py falls back to hardcoded Muse Spark 1.3 values when a model's files lack candidate-level data, and it can mix entries from a shared transcript log. Do not use its candidate-level output (holds, cost, tool calls).
