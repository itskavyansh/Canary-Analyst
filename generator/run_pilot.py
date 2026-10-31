import json
import time
from pathlib import Path
from engine.candidates import CandidateGenerator
from agent.analyst import Analyst
from agent.guard import SafetyGuard

def run_pilot():
    print("=" * 70)
    print("CANARY ANALYST PILOT INVESTIGATION (20 CANDIDATES)")
    print("=" * 70)
    
    scen_path = Path("data/scenarios")
    with open(scen_path / "index.json", "r") as f:
        idx = json.load(f)
    
    # Stratified selection
    # 10 Non-hazard candidates across types:
    # 2 blast, 2 machinery_impact, 2 rain_tilt, 2 sensor_fault, 2 stuck_sensor
    # 10 Hazard candidates:
    # At least 3 creep-plus-blast combos, plus accelerating & slow creep
    
    non_hazard_targets = {
        "blast": 2,
        "machinery_impact": 2,
        "rain_tilt": 2,
        "sensor_fault": 2,
        "stuck_sensor": 2
    }
    
    cgen = CandidateGenerator()
    selected_pilot = [] # list of (candidate, scenario_meta, readings, truth_type, is_hazard)
    
    selected_nh_counts = {k: 0 for k in non_hazard_targets}
    selected_hazard_count = 0
    selected_creep_blast_count = 0
    
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
            
        cands = []
        for ts in sorted(by_time.keys()):
            c = cgen.update(ts, by_time[ts])
            if c:
                cands.extend(c)
                
        if not cands:
            continue
            
        stype = truth["type"]
        is_haz = truth["is_hazard"]
        blasts = truth.get("blast_schedule", [])
        
        # Meta for analyst (sanitized)
        meta = {
            "scenario_id": truth["scenario_id"],
            "node_layout": truth.get("node_coordinates_m", {}),
            "blast_schedule": blasts
        }
        
        if not is_haz:
            if stype in non_hazard_targets and selected_nh_counts[stype] < non_hazard_targets[stype]:
                # Pick the first candidate
                c = cands[0]
                # Filter readings up to trigger time (strictly no lookahead)
                tr_readings = [r for r in all_readings if r["timestamp"] <= c.trigger_time]
                selected_pilot.append((c, meta, tr_readings, stype, is_haz, "non_hazard"))
                selected_nh_counts[stype] += 1
        else:
            # Hazard candidate
            is_creep_blast = len(blasts) > 0
            if is_creep_blast and selected_creep_blast_count < 3:
                c = cands[0]
                tr_readings = [r for r in all_readings if r["timestamp"] <= c.trigger_time]
                selected_pilot.append((c, meta, tr_readings, stype, is_haz, "creep_blast"))
                selected_creep_blast_count += 1
                selected_hazard_count += 1
            elif selected_hazard_count < 10 and not (is_creep_blast and selected_creep_blast_count >= 3):
                c = cands[0]
                tr_readings = [r for r in all_readings if r["timestamp"] <= c.trigger_time]
                selected_pilot.append((c, meta, tr_readings, stype, is_haz, "hazard"))
                selected_hazard_count += 1
                
        if sum(selected_nh_counts.values()) == 10 and selected_hazard_count == 10:
            break
            
    print(f"Selected {len(selected_pilot)} pilot candidates:")
    print(f"- Non-hazards: {sum(selected_nh_counts.values())} (breakdown: {selected_nh_counts})")
    print(f"- Hazards: {selected_hazard_count} (including {selected_creep_blast_count} creep-plus-blast combos)")
    
    analyst = Analyst(budget_usd=10.0)
    guard = SafetyGuard()
    
    pilot_results = []
    total_cost = 0.0
    total_tokens = 0
    total_time = 0.0
    hazard_holds = 0
    
    for idx_num, (cand, meta, readings, true_type, is_haz, cat) in enumerate(selected_pilot, 1):
        print(f"\n[{idx_num:02d}/20] Running candidate: {cand.episode_id} ({true_type}, hazard={is_haz}) as_of={cand.trigger_time}")
        t0 = time.time()
        res = analyst.investigate(cand, readings, meta)
        t1 = time.time()
        
        if res is None:
            print("  Result: None (Analyst failed or budget exceeded)")
            guard_dec = guard.evaluate(cand, None)
        else:
            total_cost += res.cost_usd
            toks = res.token_usage.get("total_tokens", 0)
            total_tokens += toks
            total_time += (t1 - t0)
            guard_dec = guard.evaluate(cand, res)
            
            p = res.parsed or {}
            hyp = p.get("hypothesis", "unknown")
            rec = p.get("recommendation", "unknown")
            conf = p.get("confidence", 0.0)
            brief = p.get("brief", "")
            
            print(f"  Analyst: hyp={hyp}, rec={rec}, conf={conf:.2f}, tokens={toks}, cost=${res.cost_usd:.4f}")
            print(f"  Guard: action={guard_dec.action}, reason={guard_dec.reason}")
            print(f"  Brief: {brief[:80]}...")
            
            if is_haz and guard_dec.action == "DOWNGRADE":
                hazard_holds += 1
                print(f"  [CRITICAL ALERT] HAZARD CANDIDATE WAS DOWNGRADED/HELD!")
                
        pilot_results.append({
            "candidate_id": cand.episode_id,
            "scenario_type": true_type,
            "is_hazard": is_haz,
            "analyst_hyp": res.parsed.get("hypothesis") if res and res.parsed else None,
            "analyst_rec": res.parsed.get("recommendation") if res and res.parsed else None,
            "guard_action": guard_dec.action,
            "guard_reason": guard_dec.reason,
            "cost_usd": res.cost_usd if res else 0.0,
            "tokens": res.token_usage.get("total_tokens", 0) if res else 0
        })
        
    print("\n" + "=" * 70)
    print("PILOT EXECUTION COMPLETE")
    print(f"Total candidates evaluated: {len(pilot_results)}")
    print(f"Total API Cost: ${total_cost:.4f}")
    print(f"Total Tokens: {total_tokens}")
    print(f"Total Elapsed Time: {total_time:.1f}s (mean {total_time/len(pilot_results):.1f}s/cand)")
    print(f"Hazard Candidates Held (must be 0): {hazard_holds}")
    print("=" * 70)
    
    with open("results/pilot_summary.json", "w") as f:
        json.dump({
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "hazard_holds": hazard_holds,
            "results": pilot_results
        }, f, indent=2)

if __name__ == "__main__":
    run_pilot()

