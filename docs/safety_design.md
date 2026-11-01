# Geotechnical Safety Guard & Deterministic Verification Architecture

Canary Analyst combines probabilistic deep reasoning with a deterministic safety guard. While the LLM (`muse-spark-1.3`) generates rich forensic analyses and diagnoses hypotheses, it is **never granted unilateral authority to silence or dismiss a safety alert**.

---

### Core Philosophy: Asymmetric Risk
In ground-subsidence monitoring above abandoned underground coal workings, missing a progressive catastrophic failure carries life-safety consequences. A false alarm causes a temporary review or inspection delay. Therefore:
1. **The Default Action is Always `KEEP`**: Unless every safety check passes deterministically, alerts remain active and escalate normally.
2. **Deterministic Re-verification**: All facts claimed by the model (cross-node synchrony, schedule proximity, return to baseline, sensor errors) are re-calculated directly by deterministic Python code against the underlying tool evidence. The model's prose is never trusted for verification.
3. **No Unilateral Dismissals (`HOLD` Instead of Dismissal)**: A verified benign downgrade never suppresses the event permanently. Instead, it places the episode into a temporary `REVIEW` status (`Alert.level = "REVIEW"`, metrics ignore `REVIEW`), bounded by strict physical and temporal escape triggers.

---

### Guard Verification Pipeline ([`SafetyGuard`](../agent/guard.py))

A candidate episode proposed for `DOWNGRADE` must satisfy all four gates simultaneously:

#### Gate A: Schema & Confidence
- Result must parse into strict JSON.
- Model confidence must be $\ge 0.80$.
- Classified hypothesis must be one of the 5 benign classes:
  - `blast`
  - `machinery_impact`
  - `environmental_tilt`
  - `sensor_fault`
  - `sensor_stuck`

#### Gate B: Evidence Integrity
- Every single cited `evidence_id` must match a cryptographic hash emitted during this candidate's tool investigation. No hallucinated IDs are permitted.
- The analyst must cite results from at least **2 distinct tools**.

#### Gate C: Hypothesis-Specific Physical Invariants
Re-verified by deterministic code from the raw tool outputs:
1. **`blast`**:
   - Array-wide synchrony: $\ge 3$ nodes peak within 1 minute, OR a scheduled blast was confirmed within $\pm 30\text{ min}$.
   - Transient recovery: Triggering channel must be within $3\sigma$ of baseline or actively falling.
   - Stability: No node shows an active linear trend projecting to critical threshold.
2. **`machinery_impact`**:
   - Spatial isolation: Only 1 node experienced anomalous vibration; neighbors remain at baseline.
   - No deformation: Node exhibits zero persistent tilt or distance displacement.
3. **`environmental_tilt`**:
   - Common-mode response: $\ge 3$ nodes exhibit uniform tilt in the same direction.
   - Non-seismic: Zero vibration exceedance and zero rising piezo acoustic emission.
4. **`sensor_fault`**:
   - Hardware anomaly confirmed: `get_sensor_health` flags rail values, ultrasonic distance pinning ($350\text{ cm}$), or I2C errors on that node.
   - Spatial consistency: All other 3 nodes are completely normal with no trend.
5. **`sensor_stuck`**:
   - Sensor freeze confirmed: Exactly $\ge 30$ identical consecutive readings on the suspect node while neighbor nodes record natural ambient variance.

#### Gate D: Global Safety Veto
- If **ANY** non-suspect node exhibits a statistically significant trend ($t \ge 4.0$, $R^2 \ge 0.60$) projecting to threshold within 120 minutes, or if acoustic piezo emission is rising, the downgrade is **immediately vetoed**.

---

### Temporary Review Hold Dynamics & Bounded Delay

When the guard approves a `DOWNGRADE`, the candidate enters a `HOLD` state (`UNDER_REVIEW`). The episode emits `Alert(level="REVIEW")` while monitoring persists.

The hold automatically terminates, restoring the original alert level (`WARNING` or `CRITICAL`), upon the **earliest** of three conditions:
1. **Hold Timeout**: $10\text{ minutes}$ elapsed since the candidate's trigger time.
2. **Spatial Escalation**: Any new `CRITICAL` alert raised on another node or channel.
3. **Deformation Worsening**: The candidate's triggering channel degrades by more than $25\%$ beyond its level at trigger time.

**Theoretical Guarantee**: The worst-case delay for a held genuine hazard is strictly bounded to $10\text{ minutes}$. Because slow creep progresses over hours and accelerating creep undergoes tertiary acceleration that breaches the $25\%$ worsening threshold within minutes, this architecture provides ironclad safety bounds against model error.

