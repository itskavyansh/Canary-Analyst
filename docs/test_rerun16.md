# Canary Analyst: Live Test Split Rerun Report (16 Candidates)

This report documents the live re-evaluation of the 16 test candidates that had previously been served from the development-split cache due to candidate ID collisions across splits.

The rerun was executed strictly on the held-out test split (`data/scenarios_test`) using **Muse Spark 1.3**, pointing to an empty isolated cache directory (`results/test_rerun16/cache/`), with a hard budget cap of \$1.00.

---

## 1. Experimental Setup & Cache Isolation Verification

- **Mechanism Used**: Modeled after the cache and runs directory isolation introduced in commit `637ba00` (`Analyst(cache_dir=..., runs_dir=...)`).
- **Target Output Directory**: `results/test_rerun16/`
- **Isolated Cache Directory**: `results/test_rerun16/cache/` (proven empty prior to execution: `len(list(cache_dir.iterdir())) == 0`).
- **Isolated Runs Log**: `results/test_rerun16/runs/transcripts.jsonl`
- **Execution Script**: Evaluated the 12 scenarios containing the 16 target candidates:
  `SCENARIO_0009_slow_creep`, `SCENARIO_0021_accelerating_creep`, `SCENARIO_0023_accelerating_creep`, `SCENARIO_0025_accelerating_creep`, `SCENARIO_0073_accelerating_creep`, `SCENARIO_0130_slow_creep`, `SCENARIO_0178_accelerating_creep`, `SCENARIO_0179_slow_creep`, `SCENARIO_0182_slow_creep`, `SCENARIO_0199_accelerating_creep`, `SCENARIO_0216_slow_creep`, `SCENARIO_0287_accelerating_creep`.
- **Other Candidates Called Live**: Exactly 1 additional candidate episode was generated on the stream for these 12 scenarios and called live:
  - `SCENARIO_0182_slow_creep_002` (cost: \$0.02462, hypothesis: `ground_movement`, recommendation: `KEEP`).
  Total live API calls executed: **17**.

---

## 2. Verification of Tool Outputs Against Held-Out TEST Split

For each of the 16 candidates, taking the first `get_node_history` call stored in the original dev cache entry (`results/agent_cache`) and in the new transcript (`results/test_rerun16/runs`):

### Original Dev Cache First `get_node_history` Call
| Candidate ID | Node | Channel | Window | Stored Mean (Dev Cache) | Recomputed on DEV | Recomputed on TEST | Match |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `SCENARIO_0009_slow_creep_001` | `NODE_03` | `distance` | 60 min | 0.3515 | 0.3515 | 0.1466 | DEV |
| `SCENARIO_0009_slow_creep_002` | `NODE_01` | `distance` | 60 min | 0.3273 | 0.3273 | 0.3501 | DEV |
| `SCENARIO_0021_accelerating_creep_001` | `NODE_04` | `distance` | 60 min | 0.406 | 0.406 | 0.2768 | DEV |
| `SCENARIO_0021_accelerating_creep_002` | `NODE_01` | `piezo_peak` | 60 min | 0.9853 | 0.9853 | 0.0261 | DEV |
| `SCENARIO_0023_accelerating_creep_001` | `NODE_03` | `distance` | 60 min | 0.2548 | 0.2548 | 0.5105 | DEV |
| `SCENARIO_0023_accelerating_creep_002` | `NODE_04` | `distance` | 60 min | 5.0798 | 5.0798 | 0.2905 | DEV |
| `SCENARIO_0025_accelerating_creep_001` | `NODE_03` | `distance` | 60 min | 0.5529 | 0.5529 | 16.1836 | DEV |
| `SCENARIO_0073_accelerating_creep_001` | `NODE_01` | `tilt` | 60 min | 4.9376 | 4.9376 | 3.2029 | DEV |
| `SCENARIO_0130_slow_creep_001` | `NODE_02` | `tilt` | 60 min | 5.0002 | 5.0002 | 0.2518 | DEV |
| `SCENARIO_0178_accelerating_creep_001` | `NODE_01` | `distance` | 60 min | 0.4284 | 0.4284 | 0.2526 | DEV |
| `SCENARIO_0179_slow_creep_001` | `NODE_01` | `distance` | 60 min | 0.3082 | 0.3082 | 0.3382 | DEV |
| `SCENARIO_0182_slow_creep_001` | `NODE_04` | `tilt` | 60 min | 6.4877 | 6.4877 | 7.012 | DEV |
| `SCENARIO_0199_accelerating_creep_001` | `NODE_01` | `distance` | 60 min | 0.424 | 0.424 | 0.292 | DEV |
| `SCENARIO_0216_slow_creep_001` | `NODE_04` | `tilt` | 60 min | 6.5748 | 6.5748 | 0.265 | DEV |
| `SCENARIO_0287_accelerating_creep_001` | `NODE_04` | `distance` | 60 min | 0.3958 | 0.3958 | 0.3224 | DEV |
| `SCENARIO_0287_accelerating_creep_002` | `NODE_04` | `tilt` | 60 min | 3.7267 | 3.7267 | 0.224 | DEV |

### New Live Test Rerun First `get_node_history` Call
| Candidate ID | Node | Channel | Window | Stored Mean (Rerun) | Recomputed on DEV | Recomputed on TEST | Match |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `SCENARIO_0009_slow_creep_001` | `NODE_04` | `tilt` | 60 min | 6.2156 | 0.3025 | 6.2156 | TEST |
| `SCENARIO_0009_slow_creep_002` | `NODE_01` | `tilt` | 60 min | 7.261 | 0.2683 | 7.261 | TEST |
| `SCENARIO_0021_accelerating_creep_001` | `NODE_03` | `distance` | 60 min | 0.4223 | 0.1684 | 0.4223 | TEST |
| `SCENARIO_0021_accelerating_creep_002` | `NODE_03` | `tilt` | 60 min | 4.2637 | 0.2101 | 4.2637 | TEST |
| `SCENARIO_0023_accelerating_creep_001` | `NODE_04` | `distance` | 60 min | 0.2678 | 0.25 | 0.2678 | TEST |
| `SCENARIO_0023_accelerating_creep_002` | `NODE_02` | `tilt` | 60 min | 1.8254 | 0.2254 | 1.8254 | TEST |
| `SCENARIO_0025_accelerating_creep_001` | `NODE_04` | `tilt` | 60 min | 2.3318 | 0.2063 | 2.3318 | TEST |
| `SCENARIO_0073_accelerating_creep_001` | `NODE_01` | `tilt` | 60 min | 4.2547 | 6.334 | 4.2547 | TEST |
| `SCENARIO_0130_slow_creep_001` | `NODE_01` | `tilt` | 60 min | 8.0812 | 0.2287 | 8.0812 | TEST |
| `SCENARIO_0178_accelerating_creep_001` | `NODE_03` | `tilt` | 60 min | 2.8439 | 0.2193 | 2.8439 | TEST |
| `SCENARIO_0179_slow_creep_001` | `NODE_01` | `tilt` | 60 min | 5.7974 | 3.5785 | 5.7974 | TEST |
| `SCENARIO_0182_slow_creep_001` | `NODE_03` | `tilt` | 60 min | 4.2734 | 0.253 | 4.2734 | TEST |
| `SCENARIO_0199_accelerating_creep_001` | `NODE_03` | `tilt` | 60 min | 3.7513 | 0.2619 | 3.7513 | TEST |
| `SCENARIO_0216_slow_creep_001` | `NODE_01` | `tilt` | 60 min | 5.5216 | 0.2449 | 5.5216 | TEST |
| `SCENARIO_0287_accelerating_creep_001` | `NODE_02` | `tilt` | 60 min | 3.7147 | 0.2564 | 3.7147 | TEST |
| `SCENARIO_0287_accelerating_creep_002` | `NODE_02` | `distance` | 60 min | 11.4601 | 0.0122 | 11.4601 | TEST |

**Result**: For all 16 candidates, the original dev-cache entry matches readings from the DEV split (`data/scenarios`), whereas the live rerun transcript matches readings from the TEST split (`data/scenarios_test`).

---

## 3. Candidate-by-Candidate Decision Comparison

| Candidate ID | Original Decision (DEV-served) | Live Re-Run Decision (TEST) | Hypothesis | Conf | Guard | Hold Created? | Cited IDs Valid? | Tool Calls | Cost (USD) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `SCENARIO_0009_slow_creep_001` | `KEEP` (`ground_movement`, 0.85) | **`KEEP`** | `ground_movement` | 0.88 | n/a (recommended KEEP) | No | Yes (5/5) | 6 | \$0.02673 |
| `SCENARIO_0009_slow_creep_002` | `KEEP` (`unclear`, 0.55) | **`KEEP`** | `ground_movement` | 0.90 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02893 |
| `SCENARIO_0021_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.88) | **`KEEP`** | `ground_movement` | 0.88 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02681 |
| `SCENARIO_0021_accelerating_creep_002` | `KEEP` (`ground_movement`, 0.90) | **`KEEP`** | `ground_movement` | 0.92 | n/a (recommended KEEP) | No | Yes (5/5) | 6 | \$0.02092 |
| `SCENARIO_0023_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.88) | **`KEEP`** | `ground_movement` | 0.68 | n/a (recommended KEEP) | No | Yes (4/4) | 6 | \$0.02870 |
| `SCENARIO_0023_accelerating_creep_002` | `KEEP` (`ground_movement`, 0.93) | **`KEEP`** | `ground_movement` | 0.93 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02445 |
| `SCENARIO_0025_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.90) | **`KEEP`** | `ground_movement` | 0.93 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02206 |
| `SCENARIO_0073_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.93) | **`KEEP`** | `ground_movement` | 0.93 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02541 |
| `SCENARIO_0130_slow_creep_001` | `KEEP` (`ground_movement`, 0.90) | **`KEEP`** | `ground_movement` | 0.88 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02759 |
| `SCENARIO_0178_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.88) | **`KEEP`** | `ground_movement` | 0.92 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02327 |
| `SCENARIO_0179_slow_creep_001` | `KEEP` (`ground_movement`, 0.70) | **`KEEP`** | `ground_movement` | 0.88 | n/a (recommended KEEP) | No | Yes (5/5) | 6 | \$0.02250 |
| `SCENARIO_0182_slow_creep_001` | `KEEP` (`ground_movement`, 0.88) | **`KEEP`** | `ground_movement` | 0.82 | n/a (recommended KEEP) | No | Yes (5/5) | 6 | \$0.02539 |
| `SCENARIO_0199_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.85) | **`KEEP`** | `ground_movement` | 0.93 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02591 |
| `SCENARIO_0216_slow_creep_001` | `KEEP` (`ground_movement`, 0.88) | **`KEEP`** | `ground_movement` | 0.88 | n/a (recommended KEEP) | No | Yes (5/5) | 6 | \$0.02252 |
| `SCENARIO_0287_accelerating_creep_001` | `KEEP` (`ground_movement`, 0.85) | **`KEEP`** | `ground_movement` | 0.92 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02306 |
| `SCENARIO_0287_accelerating_creep_002` | `KEEP` (`ground_movement`, 0.93) | **`KEEP`** | `ground_movement` | 0.90 | n/a (recommended KEEP) | No | Yes (6/6) | 6 | \$0.02257 |

---

## 4. Key Differences and Safety Invariant Checks

1. **Hazard Downgrades / Holds**:
   - Exactly **0** of the 16 candidates were downgraded.
   - Exactly **0** holds were created on hazard scenarios.
   - All 16 candidates recommended **`KEEP`**.
2. **Hypothesis Shifts**:
   - `SCENARIO_0009_slow_creep_002` shifted from `unclear` (confidence 0.55) to `ground_movement` (confidence 0.90).
   - All 16 candidates were classified as `ground_movement`.
3. **Detection and Lead Time Invariance**:
   - In all 12 evaluated scenarios, detection status remained **100% detected** (`detected = True`).
   - Lead times for accelerating creep matched `results/test_final` for these scenarios:
     - `SCENARIO_0021_accelerating_creep`: 77.0 min
     - `SCENARIO_0023_accelerating_creep`: 37.0 min
     - `SCENARIO_0025_accelerating_creep`: 48.0 min
     - `SCENARIO_0073_accelerating_creep`: 46.0 min
     - `SCENARIO_0178_accelerating_creep`: 46.0 min
     - `SCENARIO_0199_accelerating_creep`: 60.0 min
     - `SCENARIO_0287_accelerating_creep`: 54.0 min
   - Zero changes in detection, lead time, or false alarms occurred across any scenario.

---

## 5. Recomputed Aggregate Benchmark Metrics for Muse Spark 1.3 (16 Replaced)

Recomputing the full evaluation across the 133 stream candidates with the 16 replaced by their true live test evaluations:

| Metric | Original Reported / Cache Set | True Live Re-Run Set (16 Replaced) | Notes |
| :--- | :---: | :---: | :--- |
| **Hazard Detection Rate** | **100.0%** (86 / 86) | **100.0%** (86 / 86) | Zero hazard scenarios missed |
| **Hazard Candidates Held** | **0** | **0** | The guard's final action was KEEP on all 110 stream hazard candidates and none was held. On one of them (SCENARIO_0152_slow_creep_001) the analyst recommended a downgrade at confidence 0.78 and the guard vetoed it (minimum 0.80). |
| **`ground_movement` Labels on Hazards** | 106 / 110 (96.4%) | **107 / 110 (97.3%)** | `0009_slow_creep_002` improved from unclear to ground_movement |
| - *Across all 115 cached hazards* | 111 / 115 (96.5%) | **112 / 115 (97.4%)** | Including the 5 pre-benchmark exploratory hazards |
| **Evidence Validity Rate** | 100.0% | **100.0%** (714 / 714) | every cited evidence ID was returned by a tool call in the same investigation |
| **Cost of 117 Original Live Calls** | \$2.45896 USD | **\$2.45896 USD** | Exact sum from transcripts |
| **Cost of 16 New Live Calls** | \$0.35793 USD (dev-cached) | **\$0.39681 USD** | Actual cost of live API calls |
| **Total Stream Execution Cost (133)** | \$2.81689 USD | **\$2.85577 USD** | \$2.45896 + \$0.39681 |
| **Cost of All 17 Live Calls in Rerun** | - | **\$0.42144 USD** | Including `0182_slow_creep_002` (\$0.02462) |

