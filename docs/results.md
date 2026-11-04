# Canary Analyst: Evaluation Results & Methodology

Canary Analyst is an AI geotechnical analyst designed for a 4-node ground-subsidence monitoring network above abandoned coal workings. This document presents the evaluation of our four detectors across the development and held-out test benchmarks.

---

## 1. Pre-Registration & Scientific Protocol

To adhere to rigorous ML evaluation standards and prevent data snooping:
1. **DEV Split ($N=300$, seed 42)**: Used exclusively for exploratory failure analysis, threshold calibration, baseline engineering (B0 $\to$ B1 $\to$ B2 $\to$ B2.1), and prompt/guard development.
2. **Pre-Test Freeze**: Prior to running any detector on the held-out test split:
   - System prompt (`agent/prompts/analyst_v1.md`), guard gates, hold timeout (15 min), and B2.1 configuration (`engine/b2_frozen.json`) were frozen.
   - All parameters and SHA-256 hashes were recorded in [`results/freeze_manifest.json`](file:///c:/Users/HP/Downloads/Canary%20Analyst/results/freeze_manifest.json).
   - A git tag **`frozen-before-test`** was created at commit `77ae260`.
3. **Held-Out TEST Split ($N=300$, seed 2026)**: Run exactly once using the frozen pipeline. No per-scenario tuning or threshold adjustments were made post-unblinding.

---

## 2. Test Set Benchmark Results ($N=300$)

All four detectors evaluated on the held-out test split under the strict no-lookahead streaming contract:

| Metric | B0 (Naive Raw Thresholds) | B1 (Stateful Persistence + Trend) | B2.1 (Frozen Engineered Rules) | AGENT (Muse Spark 1.3 + Guard) |
| :--- | :---: | :---: | :---: | :---: |
| **Hazard Detection Rate** | **100.0%** | **100.0%** | **100.0%** | **100.0%** |
| **Overall False Alarm Rate** | 40.0% | 39.3% | 8.0% | **5.3%** |
| 95% Bootstrap CI (FA) | [34.0%, 45.7%] | [34.0%, 45.0%] | [5.0%, 11.3%] | [3.0%, 7.7%] |
| **Median Lead Time (min)** | 10.0 min | 57.0 min | 52.0 min | **52.0 min** |
| IQR Lead Time (p25–p75) | 0.5–31.5 min | 42.0–78.5 min | 44.5–60.5 min | 44.5–60.5 min |
| Detected Before Collapse | 74.4% | 100.0% | 100.0% | **100.0%** |
| Mean Alert Episodes / Scenario | 0.81 | 1.02 | 0.44 | **0.42** |

### Breakdown by Scenario Type on Test Set (False Alarm Rate %)

| Scenario Type ($N$ scenarios) | B0 | B1 | B2.1 | AGENT |
| :--- | :---: | :---: | :---: | :---: |
| `accelerating_creep` ($N=43$) | 0.0% *(100% det)* | 2.3% *(100% det)* | 2.3% *(100% det)* | 2.3% *(100% det)* |
| `slow_creep` ($N=43$) | 0.0% *(100% det)* | 7.0% *(100% det)* | 0.0% *(100% det)* | 0.0% *(100% det)* |
| `blast` ($N=43$) | 95.3% | 25.6% | 9.3% | **2.3%** |
| `machinery_impact` ($N=43$) | 81.4% | 44.2% | 2.3% | **0.0%** |
| `rain_tilt` ($N=43$) | 2.3% | 93.0% | 9.3% | **2.3%** |
| `sensor_fault` ($N=43$) | 100.0% | 74.4% | 27.9% | 27.9% |
| `stuck_sensor` ($N=42$) | 0.0% | 28.6% | 4.8% | **2.4%** |

---

## 3. DEV Split vs TEST Split Comparison

Comparing the performance of our engineered rules baseline (B2.1) and AGENT across both splits:

| Benchmark Split | Metric | B2.1 Baseline | AGENT (Muse Spark 1.3) | Relative FA Reduction |
| :--- | :--- | :---: | :---: | :---: |
| **DEV Split** ($N=300$, seed 42) | Hazard Detection Rate | 100.0% | 100.0% | — |
| | Overall False Alarm Rate | 6.7% | 4.3% | **$-35.8\%$** |
| | Median Lead Time | 50.0 min | 50.0 min | 0.0 min diff |
| **TEST Split** ($N=300$, seed 2026) | Hazard Detection Rate | 100.0% | 100.0% | — |
| | Overall False Alarm Rate | 8.0% | 5.3% | **$-33.8\%$** |
| | Median Lead Time | 52.0 min | 52.0 min | 0.0 min diff |

---

## 4. Ablation & Incremental Architectural Impact

| Configuration Tier | Architectural Additions | Test FA Rate | Test Median Lead Time | Key Failure Mode Addressed |
| :--- | :--- | :---: | :---: | :--- |
| **B0** | Instantaneous single-sample thresholds | 40.0% | 10.0 min | Transient vibration spikes trigger immediate false criticals; missed early creep. |
| **B1** | Rolling baselines, persistence (3/5), linear trend fitting | 39.3% | 57.0 min | High early detection, but severe false alarms on common-mode rain tilt and ultrasonic rail jumps. |
| **B2.1** | Common-mode rejection, rail-jump suppression, OLS $t_{\text{adj}}$ autocorrelation correction | 8.0% | 52.0 min | Filters spurious noise drift and mechanical transients with minimal loss of lead time. |
| **AGENT** | Muse Spark 1.3 multi-tool investigation + Deterministic Safety Guard + 15-min Review Hold | **5.3%** | **52.0 min** | Disambiguates complex multi-channel context (blasts vs impacts), achieving 0 added false alarms and 84% alarm-minute reduction. |

---

## 5. Non-Hazard Alarm-Minutes & Paired Statistical Significance

### Alarm-Minutes by Scenario Type (Test Split)
Duration (in minutes) during which the monitoring array remained in an active `WARNING` or `CRITICAL` state:

| Scenario Type | B2.1 Alarm-Minutes | AGENT Alarm-Minutes | Reduction (%) | Contributing Scenarios (B2.1 vs AGENT) |
| :--- | :---: | :---: | :---: | :---: |
| `blast` | 4.0 min | 1.0 min | $-75.0\%$ | 4 vs 1 |
| `machinery_impact` | 1.0 min | 0.0 min | $-100.0\%$ | 1 vs 0 |
| `rain_tilt` | 4.0 min | 1.0 min | $-75.0\%$ | 4 vs 1 |
| `sensor_fault` | 128.0 min | 12.0 min | **$-90.6\%$** | 12 vs 12 |
| `stuck_sensor` | 2.0 min | 1.0 min | $-50.0\%$ | 2 vs 1 |
| **Total Non-Hazard Alarm-Minutes** | **139.0 min** | **15.0 min** | **$-89.2\%$** | **23 vs 15** |

### Paired Comparison & Exact Sign Test (Test Split)
Evaluated across all non-hazard scenarios ($N=214$):
- **False alarms removed by AGENT that B2.1 had**: **8**
- **False alarms added by AGENT that B2.1 did not have**: **0**
- Both detectors triggered a false alarm: 15
- Neither detector triggered a false alarm: 191
- **Exact Two-Sided Sign Test $p$-value**:
  $$p = 2 \times \binom{8}{0} (0.5)^8 = 2 \times \frac{1}{256} = \mathbf{0.0078125}$$
  *(Statistically significant at $\alpha = 0.01$)*.

---

## 6. Pre-Registration Verification Checklist

| Pre-Registered Criterion | Target | Test Set Result | Verdict |
| :--- | :---: | :---: | :---: |
| **Hazard Candidates Held or Delayed** | Exactly 0 | **0** (0 hazard candidates ever held or delayed) | **PASS** |
| **Hazard Detection Rate** | 100.0% | **100.0%** (86 / 86 hazard scenarios detected) | **PASS** |
| **Median Lead Time vs B2.1** | Within 5.0 min | **52.0 min vs 52.0 min** ($\Delta = 0.0$ min) | **PASS** |
| **False Alarm Reduction** | Documented & improved | **8.0% $\to$ 5.3%** ($p = 0.0078$) | **PASS** |

---

## 7. Known Limitations & Engineering Disclaimers

1. **Synthetic Scenario Generator**: Scenarios are generated by physics-inspired mathematical models (exponential accelerating creep, linear slow creep, impulse decays). Real-world geological faults involve anisotropic strata, rock fracture mechanics, and complex seismic reverberations not modeled here.
2. **Prototype Test-Noise Modeling**: Noise distributions and sensor drift characteristics were informed by prototype sensor test readings (`data/real_readings.csv`), which represent test noise rather than long-term outdoor underground mine conditions.
   - *Noise Limitation*: Sensor noise was measured on prototype bench logs sampled about once per second, then applied to simulated 1-minute readings, and the generator caps noise levels (distance 0.35 cm, tilt 0.20 degrees, vibration 0.015 g), so simulated noise is an approximation. The generator has no temperature drift, which real tiltmeters show.
3. **Silent Sensor Faults**: While the Safety Guard and B2.1 filter ultrasonic transducer rail jumps and frozen constant outputs, subtle partial-calibration drift on a single axis without diagnostic error flags cannot be reliably distinguished from localized micro-strain without ground truthing.
4. **Generator Hazards vs Reality**: Synthetic collapse profiles follow deterministic acceleration curves. Actual rock falls may undergo discontinuous step-like stick-slip behavior with sudden brittle failure.
5. **Demonstration Thresholds**: Warning (15° tilt, 2.0 cm displacement, 1.0 g vibration) and critical thresholds are engineering demonstration values chosen for demonstration testing; site-specific geotechnical installations require customized geotechnical baseline surveying.

---

## 8. Candidate-Level Evaluation Metrics & Rerun Audit

The headline benchmark evaluation across the 300 held-out test scenarios generated exactly **133 candidate anomaly episodes** through the frozen B2.1 detector pipeline.

### Verified Candidate Metrics (Stream Only, N=133)
- **Candidate Episodes Investigated**: 133
- **Hazard Candidates**: 110 (all 110 recommended `KEEP`, 0 held)
- **Hazard Candidates Labelled `ground_movement`**: **107 of 110** (97.3%)
- **Evidence Verification Integrity**: **100.0%** (714 of 714 cited evidence IDs verified against raw tool output hashes)
- **Total Test Inference Cost**: **$2.86 USD** ($2.85577 USD; mean $0.02147 / candidate)

### As originally published
*As originally published, candidate-level statistics reported 142 candidates, $2.99 USD ($2.99488), 761 of 761 evidence IDs valid, and 111 of 115 hazard candidates labelled ground_movement. These original figures included 9 development-run cache entries (5 hazard, 4 non-hazard) that were stored in the global cache directory during pre-freeze testing and shared candidate ID keys because the cache hash did not include a split prefix. In an audit, the 16 test candidates that had been served from dev-split cache entries were re-run live on true test data in `results/test_rerun16/`. All 16 reran live as KEEP; 15 kept the same label (ground_movement) and 1 (SCENARIO_0009_slow_creep_002) changed from unclear (0.55) to ground_movement (0.90); detection and scenario-level results are unchanged. Scenario-level numbers (86/86 detection, 16 false-alarm scenarios, 8 holds cleared, paired sign test p=0.0078) are as published, and the candidate-level statistics above reflect strictly the 133 stream candidates with the live test data.*

---

## 9. Post-hoc breakdown (descriptive, not a test)

These breakdowns were computed after the test run and played no part in any design choice.

### Non-Hazard False Alarm Removals by Scenario Type (=214$)

Across all 214 non-hazard scenarios in the held-out test split, comparing the frozen B2.1 baseline to the agent:

| Scenario Type | Total Non-Hazard Scenarios | B2.1 False Alarms | Agent False Alarms | Removed | Added |
| :--- | :---: | :---: | :---: | :---: | :---: |
| last | 43 | 4 | 1 | 3 | 0 |
| machinery_impact | 43 | 1 | 0 | 1 | 0 |
| 
ain_tilt | 43 | 4 | 1 | 3 | 0 |
| sensor_fault | 43 | 12 | 12 | 0 | 0 |
| stuck_sensor | 42 | 2 | 1 | 1 | 0 |
| **Total** | **214** | **23** | **15** | **8** | **0** |

*Note: 8 false alarms removed, 0 added (exact two-sided sign test p = 0.0078).*

### Candidate Decision and Guard Verification Counts (=133$)

Across all 133 candidate anomaly episodes evaluated for Muse Spark 1.3 (117 live test stream decisions plus 16 live test reruns in 
esults/test_rerun16):
- **Analyst Recommendations**:
  - KEEP: 113
  - DOWNGRADE: 20
- **Safety Guard Disposition on Downgrades**:
  - Guard Approved: 8 (all 8 entered 15-minute review hold and safely cleared)
  - Guard Vetoed: 12 (all 12 failed-closed to KEEP)
- **Breakdown of Guard Vetoes by Gate**:
  - sensor_fault_failed (Gate C): 10 (no anomalous error flags or rail jumps verified on sensor hardware)
  - environmental_tilt_failed (Gate C): 1 (common-mode tilt observed on fewer than 3 nodes)
  - insufficient_confidence (Gate A): 1 (model confidence 0.78 below 0.80 minimum threshold)

The 8 guard-approved downgrades reconcile exactly with the 8 review holds cleared in the test evaluation.

