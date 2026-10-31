import json
from pathlib import Path
from engine.candidates import CandidateGenerator

def get_candidates():
    scen_path = Path("data/scenarios")
    with open(scen_path / "index.json", "r") as f:
        idx = json.load(f)
    
    cgen = CandidateGenerator()
    hazards = []
    non_hazards = []
    
    for s in idx["scenarios"]:
        tf = scen_path / s["truth_file"]
        rf = scen_path / s["readings_file"]
        with open(tf, "r") as f:
            truth = json.load(f)
        
        cgen.reset({"scenario_id": truth["scenario_id"]})
        
        all_readings = []
        with open(rf, "r") as f:
            for line in f:
                all_readings.append(json.loads(line))
        by_time = {}
        for r in all_readings:
            ts = r["timestamp"]
            if ts not in by_time: by_time[ts] = {}
            by_time[ts][r["node_id"]] = r
            
        scen_cands = []
        for ts in sorted(by_time.keys()):
            c = cgen.update(ts, by_time[ts])
            if c:
                scen_cands.extend(c)
        
        if scen_cands:
            item = {
                "scenario_id": truth["scenario_id"],
                "type": truth["type"],
                "is_hazard": truth["is_hazard"],
                "blast_schedule": truth.get("blast_schedule", []),
                "events": truth.get("events", []),
                "candidates": scen_cands,
                "readings_file": str(rf),
                "truth_file": str(tf)
            }
            if truth["is_hazard"]:
                hazards.append(item)
            else:
                non_hazards.append(item)
    return hazards, non_hazards

hazards, non_hazards = get_candidates()

# Find creep with blast
creep_blast = [h for h in hazards if any(e.get("type") == "blast" or "blast" in str(e) for e in h.get("events", [])) or len(h.get("blast_schedule", [])) > 0]
print(f"Hazard with blasts/schedule: {len(creep_blast)}")
for h in creep_blast[:5]:
    print(" ", h["scenario_id"], h["type"], "blasts:", len(h["blast_schedule"]), "candidates:", len(h["candidates"]))

print(f"Non-hazard types:")
types_count = {}
for nh in non_hazards:
    types_count[nh["type"]] = types_count.get(nh["type"], 0) + 1
print(" ", types_count)
