# Canary Analyst: Autonomous Geotechnical AI Analyst for Subsidence Networks

> **Built entirely from scratch during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026).**  
> All code in this repository was authored during the hackathon period. It is the autonomous AI reasoning and decision-support layer for ProjectCanary, our team's earlier sensor-hardware concept. All evaluation sensor telemetry is simulated unless explicitly stated.

---

## Overview

Canary Analyst monitors 4-node surface sensor arrays deployed over abandoned room-and-pillar coal mines. It addresses the fundamental trade-off in mine safety: **false alarms cause disruptive operational shutdowns, but missed hazards cause catastrophic loss of human life.**

To solve this, Canary Analyst uses an **"AI Proposes, Deterministic Code Decides"** safety architecture:
1. **Tier-1 Fast Rules Baseline (B2.1)**: Deterministic persistent thresholding and autocorrelation-adjusted OLS linear trend fitting screen incoming sensor streams tick-by-tick.
2. **Tier-2 Autonomous Analyst Agent (Muse Spark 1.3)**: When candidate excursions trigger, the agent executes targeted diagnostic tool calls (neighbor node comparisons, acoustic piezo emissions, blast schedules, sensor health diagnostics).
3. **Deterministic Safety Guard & Review Hold**: The agent recommends an operational action (`KEEP` vs `DOWNGRADE`), but a deterministic safety guard audits physical invariants. Approved downgrades are placed in a **15-minute Review Hold** that automatically re-emits if conditions worsen by >25% or persist at timeout.

---

## Key Results Summary (Held-Out Test Set)

Evaluated under a pre-registered protocol on a 300-scenario held-out test split (seed 2026) frozen before testing (git tag `frozen-before-test`):

- **Hazard Detection Rate**: **100.0%** (86 / 86 hazards detected across accelerating creep and slow creep).
- **Hazard Delay**: **0.0 minutes** (0 hazard candidates ever placed on hold or delayed).
- **False Alarm Rate**: Reduced from **40.0%** (naive thresholds) and **8.0%** (rules baseline) to **5.3%** (**-33.8% relative reduction** over B2.1).
- **Non-Hazard Alarm-Minutes**: Reduced from **139.0 minutes** to **15.0 minutes** (**-89.2% reduction**).
- **Statistical Significance**: Paired comparison showed 8 false alarms removed with 0 added (exact two-sided sign test $p = \mathbf{0.0078125}$).
- **API Efficiency**: Mean cost of **$0.0211 / candidate**, **100.0% evidence validity rate** (zero hallucinated evidence IDs).

*See [`docs/results.md`](docs/results.md) for full benchmark tables, ablation studies, and scientific methodology.*

---

## Engineering Limitations & Claims

1. **Synthetic Sensor Telemetry**: Data is synthesized using physics-inspired mathematical models (exponential creep, linear shear, seismic impulse decay) rather than raw underground mine records.
2. **Bench-Noise Calibration**: Noise distributions and baseline drift parameters were calibrated from prototype hardware benchtop readings (`data/real_readings.csv`).
3. **Silent Sensor Faults**: Unflagged transducer drift on a single axis without diagnostic status flags cannot be reliably separated from localized physical strain without manual inspection.
4. **Generator Dynamics**: Synthetic collapse profiles follow deterministic acceleration curves; real geomechanical failures can feature sudden brittle stick-slip behavior.
5. **Demonstration Thresholds**: Warning (15° tilt, 2.0 cm displacement, 1.0 g vibration) and critical thresholds are demonstration values; real sites require site-specific baseline surveys.
6. **Operational Role**: **The system advises and recommends; human site authorities decide and command evacuations.**

---

## How to Run the Pipeline

### 1. Environment & Dependencies
```bash
# Clone the repository
git clone https://github.com/your-username/canary-analyst.git
cd canary-analyst

# Install Python dependencies (Python 3.11+)
pip install -r requirements.txt

# (Optional) For live LLM calls, create .env from template
cp .env.example .env
# Add your META_API_KEY to .env (not needed for cached replay or testing)
```

### 2. Run the Benchmark Evaluations
```bash
# Run unit and integration tests (all 27 pass offline)
python -m pytest tests/ -v

# Run evaluation on the DEV split
python -m eval.run_eval --detectors B0 B1 B2 AGENT --split dev

# Run evaluation on the frozen TEST split (requires --final flag)
python -m eval.run_eval --detectors B0 B1 B2 AGENT --split test --final
```

### 3. Re-export Demo Data
```bash
python -m eval.export_demo
```

---

## Interactive Web Demo (Vite + React)

Canary Analyst includes a standalone, self-contained interactive web application to replay 4 representative test scenarios tick-by-tick across all 360 simulation minutes.

### Launching Locally
```bash
cd web
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### Building for Static Deployment (GitHub Pages / Vercel)
```bash
cd web
npm run build
```
The compiled static assets are output to `web/dist/` with relative base paths (`./`) and make zero external network requests.

#### Deploying to GitHub Pages or Vercel
- **GitHub Pages**: A preconfigured GitHub Actions workflow [`.github/workflows/pages.yml`](.github/workflows/pages.yml) automatically builds `web/` and deploys `web/dist/` on push to `master` or `main`. No secrets or tokens are needed.
- **Vercel**: Import the repository in Vercel, set the **Root Directory** to `web`, with Framework Preset **Vite**, Build Command `npm run build`, and Output Directory `dist`. Because all asset paths are relative and data is loaded from local static JSON, zero environment variables or secrets are required.
