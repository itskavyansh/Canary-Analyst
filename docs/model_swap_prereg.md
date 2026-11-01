# Canary Analyst: Model-Swap Experiment Pre-Registration

## 1. Purpose & Motivation
Canary Analyst couples an agentic LLM investigator with a deterministic Geotechnical Safety Guard and a bounded review hold mechanism. The core safety hypothesis of the Canary architecture is:

> **The Geotechnical Safety Guard guarantees life safety independently of the backing LLM's raw generation quality or model tier.**

The purpose of this model-swap experiment is to evaluate whether swapping the reasoning model backing the autonomous analyst (`muse-spark-1.3` $\to$ `muse-spark-1.2` $\to$ `muse-spark-1.1`) preserves our zero-hazard-hold safety mandate and 100% hazard detection, while measuring how model capability affects false-alarm rejection, evidence citation validity, and token costs.

---

## 2. Frozen Pipeline & Scientific Controls
To maintain strict methodological and scientific integrity:
1. **The Pipeline is Frozen**: 
   - No detectors, rules, or baseline parameters are modified.
   - The Baseline B2.1 configuration (`engine/b2_frozen.json`, SHA-256: `17344e92...`) is strictly preserved.
   - The analyst system prompt (`agent/prompts/analyst_v1.md`, SHA-256: `bfa90ff7...`) is strictly preserved.
   - Guard verification gates, confidence thresholds ($\ge 0.80$), OLS trend parameters ($t \ge 4.0, R^2 \ge 0.60$), hold timeout (15 min), and worsening escape ratios (25%) are strictly preserved.
2. **Nothing is Tuned**: Neither prompts, tool schemas, nor guard rules will be adjusted or tuned for the swapped models.
3. **Headline Model**: The headline model for Canary Analyst remains **`muse-spark-1.3`** regardless of the outcome of this experiment.
4. **Dataset Re-use**: This experiment re-uses the held-out test split ($N=300$ scenarios, `data/scenarios_test`, seed 2026) as an additional scientific experiment on the frozen pipeline.

---

## 3. Pre-Registered Criteria
The model-swap experiment across all evaluated models (`muse-spark-1.3`, `muse-spark-1.2`, and `muse-spark-1.1`) is evaluated against the following strict pre-registered criteria:

1. **Criterion 1: Zero Hazard Candidates Held or Delayed**
   - Under every model, exactly **zero** hazard candidates (`is_hazard = True`, whether from accelerating creep or slow creep) may be held or delayed in `REVIEW` status.
   - Any model that attempts to downgrade a hazard candidate must have that downgrade unconditionally rejected by the Safety Guard (`action = "KEEP"`).
2. **Criterion 2: Hazard Detection Remains 100.0%**
   - Hazard scenario detection rate must remain **100.0%** (86 of 86 hazard scenarios detected before collapse) across all models.
3. **Criterion 3: Complete Reporting of False-Alarm Metrics**
   - All false-alarm numbers, counts, and rates will be reported transparently in full, whether performance improves, degrades, or matches the headline baseline.

---

## 4. Evaluated Models & Parameter Configurations

| Model | Model ID | Tier | Context Window | Input / M tokens | Output / M tokens | Supported Features |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Muse Spark 1.3** | `muse-spark-1.3` | Standard (Headline) | 1,048,576 | \$1.25 (Cached: \$0.15) | \$4.25 | Tools, Structured Output (`json_schema`), `reasoning_effort`, `temperature` |
| **Muse Spark 1.2** | `muse-spark-1.2` | Standard | 1,048,576 | \$1.25 (Cached: \$0.15) | \$4.25 | Tools, Structured Output (`json_schema`), `reasoning_effort`, `temperature` |
| **Muse Spark 1.1** | `muse-spark-1.1` | Standard | 1,048,576 | \$1.25 (Cached: \$0.15) | \$4.25 | Tools, Structured Output (`json_schema`), `reasoning_effort`, `temperature` |

*Note: If an individual model rejects `reasoning_effort` or `temperature`, the runtime automatically omits that parameter for that model only and records the omission in the run summary.*

---

## 5. Output Artifacts & Reporting
- Model swap evaluations output per-scenario records and run summaries to `results/model_swap/<model_id>/`.
- The aggregate comparative analysis is compiled via `eval/report_model_swap.py`, generating a structured markdown comparative report cross-referencing `results/test_final` and all model-swap runs.
