@echo off
cd /d "C:\Users\HP\Downloads\Canary Analyst"
python -u -m eval.run_eval --detectors AGENT --scenarios data/scenarios --out results/agent_v1 > results\agent_v1.log 2>&1

