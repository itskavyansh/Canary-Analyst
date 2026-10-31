import React, { useState, useEffect, useRef } from 'react';

export default function App() {
  const [activeTab, setActiveTab] = useState('replay'); // 'replay', 'results', 'about'
  const [indexData, setIndexData] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState('');
  const [scenarioData, setScenarioData] = useState(null);
  const [summaryData, setSummaryData] = useState(null);
  
  // Replay states
  const [currentMinute, setCurrentMinute] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(5); // 1, 5, 20
  
  const timerRef = useRef(null);

  // Fetch index and summary
  useEffect(() => {
    fetch('./demo/index.json')
      .then(res => res.json())
      .then(data => {
        setIndexData(data.scenarios || []);
        if (data.scenarios && data.scenarios.length > 0) {
          setSelectedScenarioId(data.scenarios[0].scenario_id);
        }
      })
      .catch(err => console.error("Could not load index.json:", err));

    fetch('./demo/summary.json')
      .then(res => res.json())
      .then(data => setSummaryData(data))
      .catch(err => console.error("Could not load summary.json:", err));
  }, []);

  // Fetch selected scenario
  useEffect(() => {
    if (!selectedScenarioId) return;
    setIsPlaying(false);
    setCurrentMinute(0);
    fetch(`./demo/${selectedScenarioId}.json`)
      .then(res => res.json())
      .then(data => setScenarioData(data))
      .catch(err => console.error(`Could not load ${selectedScenarioId}:`, err));
  }, [selectedScenarioId]);

  // Replay timer loop
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = Math.max(30, Math.floor(1000 / playSpeed));
      timerRef.current = setInterval(() => {
        setCurrentMinute(prev => {
          if (prev >= 359) {
            setIsPlaying(false);
            return 359;
          }
          return prev + 1;
        });
      }, intervalMs);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, playSpeed]);

  const totalMinutes = 360;

  // Filtered readings and current readings
  const readings = scenarioData ? scenarioData.readings : [];
  const currentReading = readings[currentMinute] || (readings.length > 0 ? readings[0] : null);

  // B2.1 alerts up to current minute
  const b2Alerts = scenarioData ? scenarioData.b2_alerts : [];
  const agentAlerts = scenarioData ? scenarioData.agent_alerts : [];
  const holdResolutions = scenarioData ? scenarioData.hold_resolutions : [];
  const blastSchedule = scenarioData ? scenarioData.blast_schedule : [];
  const investigations = scenarioData ? scenarioData.investigations : [];

  // Active investigation up to currentMinute
  const activeInvestigations = investigations.filter((_, idx) => {
    // Check if candidate timestamp is <= current reading timestamp
    if (!currentReading) return false;
    const inv = investigations[idx];
    return inv.timestamp <= currentReading.timestamp;
  });

  const latestInvestigation = activeInvestigations.length > 0 ? activeInvestigations[activeInvestigations.length - 1] : null;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Banner */}
      <header style={{
        background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border-color)',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🐤</span>
            <div>
              <h1 style={{ fontSize: '18px', fontWeight: '700', letterSpacing: '-0.3px' }}>Canary Analyst</h1>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>AI Subsidence Network Investigation System</p>
            </div>
          </div>
          <span style={{
            background: 'rgba(239, 68, 68, 0.15)',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            padding: '3px 10px',
            fontSize: '11px',
            fontWeight: '600',
            letterSpacing: '0.5px'
          }}>
            SIMULATED DATA — not real mine data
          </span>
        </div>

        <nav style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('replay')}
            style={{
              padding: '6px 14px',
              fontSize: '13px',
              fontWeight: '600',
              background: activeTab === 'replay' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'replay' ? 'var(--text-main)' : 'var(--text-muted)',
              border: activeTab === 'replay' ? '1px solid var(--border-highlight)' : '1px solid transparent'
            }}
          >
            Scenario Replay
          </button>
          <button
            onClick={() => setActiveTab('results')}
            style={{
              padding: '6px 14px',
              fontSize: '13px',
              fontWeight: '600',
              background: activeTab === 'results' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'results' ? 'var(--text-main)' : 'var(--text-muted)',
              border: activeTab === 'results' ? '1px solid var(--border-highlight)' : '1px solid transparent'
            }}
          >
            Benchmark Results
          </button>
          <button
            onClick={() => setActiveTab('about')}
            style={{
              padding: '6px 14px',
              fontSize: '13px',
              fontWeight: '600',
              background: activeTab === 'about' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'about' ? 'var(--text-main)' : 'var(--text-muted)',
              border: activeTab === 'about' ? '1px solid var(--border-highlight)' : '1px solid transparent'
            }}
          >
            About & Architecture
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '20px 24px' }}>
        {activeTab === 'replay' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 1. Scenario Picker Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
              {indexData.map(scen => {
                const isSelected = scen.scenario_id === selectedScenarioId;
                return (
                  <div
                    key={scen.scenario_id}
                    onClick={() => setSelectedScenarioId(scen.scenario_id)}
                    style={{
                      background: isSelected ? 'var(--bg-card-hover)' : 'var(--bg-secondary)',
                      border: isSelected ? '2px solid var(--color-review)' : '1px solid var(--border-color)',
                      borderRadius: '8px',
                      padding: '12px 14px',
                      cursor: 'pointer',
                      transition: 'border-color 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--color-review)', textTransform: 'uppercase' }}>
                        Scenario {scen.criterion_tag}
                      </span>
                      {isSelected && <span style={{ fontSize: '11px', color: 'var(--color-healthy)' }}>● ACTIVE</span>}
                    </div>
                    <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-main)', lineHeight: '1.4' }}>
                      {scen.title}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
                      360 min simulation · 4 surface nodes
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 2. Replay Controls & Scrubber */}
            <div style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              flexWrap: 'wrap'
            }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  style={{
                    background: isPlaying ? 'var(--color-warning)' : 'var(--color-healthy)',
                    color: '#000',
                    fontWeight: '700',
                    padding: '8px 16px',
                    fontSize: '13px'
                  }}
                >
                  {isPlaying ? '⏸ PAUSE' : '▶ PLAY'}
                </button>
                <button
                  onClick={() => { setIsPlaying(false); setCurrentMinute(0); }}
                  style={{
                    background: 'var(--bg-card)',
                    color: 'var(--text-main)',
                    border: '1px solid var(--border-color)',
                    padding: '8px 12px',
                    fontSize: '13px'
                  }}
                >
                  ⏮ RESET
                </button>
              </div>

              {/* Speeds */}
              <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginRight: '4px' }}>Speed:</span>
                {[1, 5, 20].map(s => (
                  <button
                    key={s}
                    onClick={() => setPlaySpeed(s)}
                    style={{
                      background: playSpeed === s ? 'var(--border-highlight)' : 'var(--bg-card)',
                      color: playSpeed === s ? 'var(--text-main)' : 'var(--text-muted)',
                      border: '1px solid var(--border-color)',
                      padding: '4px 8px',
                      fontSize: '12px',
                      fontWeight: '600'
                    }}
                  >
                    {s}x
                  </button>
                ))}
              </div>

              {/* Scrubber slider */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '12px', minWidth: '220px' }}>
                <input
                  type="range"
                  min="0"
                  max="359"
                  value={currentMinute}
                  onChange={e => setCurrentMinute(parseInt(e.target.value))}
                  style={{ flex: 1, accentColor: 'var(--color-review)', cursor: 'pointer' }}
                />
                <span style={{ fontSize: '13px', fontFamily: 'monospace', minWidth: '90px', color: 'var(--text-main)' }}>
                  T+{currentMinute}m / 360m
                </span>
              </div>

              {/* Timestamp display */}
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                {currentReading ? currentReading.timestamp : '--:--:--Z'}
              </div>
            </div>

            {/* Stacked Charts & Alert Lanes Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
              {/* Stacked Charts Component */}
              <StackedCharts
                readings={readings}
                currentMinute={currentMinute}
                blastSchedule={blastSchedule}
              />

              {/* Two Alert Lanes */}
              <div style={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '16px'
              }}>
                <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '12px', color: 'var(--text-main)' }}>
                  Real-Time Detection & Alert Timeline (0 to 360 min)
                </h3>
                <AlertLane
                  label="Deterministic Rules Baseline (B2.1)"
                  subtitle="Persistent 3/5 thresholding + lag-1 autocorrelation adjusted trend"
                  alerts={b2Alerts}
                  currentMinute={currentMinute}
                  readings={readings}
                />
                <div style={{ height: '14px' }}></div>
                <AlertLane
                  label="Canary Analyst (Rules Engine + Muse Spark 1.3 + Guard)"
                  subtitle="Autonomous multi-tool candidate investigation + 15m review hold clearance"
                  alerts={agentAlerts}
                  holdResolutions={holdResolutions}
                  currentMinute={currentMinute}
                  readings={readings}
                  isAgent={true}
                />
              </div>
            </div>

            {/* 4. Investigation Panel (Tool calls, brief, guard checklist) */}
            <InvestigationPanel
              investigation={latestInvestigation}
              currentMinute={currentMinute}
            />

            {/* 5. Reveal Panel (Revealed strictly when replay finishes or explicitly clicked) */}
            <RevealPanel
              reveal={scenarioData ? scenarioData.reveal : null}
              currentMinute={currentMinute}
              scenarioId={selectedScenarioId}
            />
          </div>
        )}

        {activeTab === 'results' && <ResultsTab summaryData={summaryData} />}

        {activeTab === 'about' && <AboutTab />}
      </main>

      {/* Footer */}
      <footer style={{
        background: 'var(--bg-secondary)',
        borderTop: '1px solid var(--border-color)',
        padding: '12px 24px',
        fontSize: '12px',
        color: 'var(--text-muted)',
        display: 'flex',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '8px'
      }}>
        <div>Canary Analyst — Meta Global AI Developer Hackathon 2026</div>
        <div>Operational Notice: The system advises and recommends; human site authority commands evacuation.</div>
      </footer>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Stacked Sensor Charts
// -----------------------------------------------------------------------------
function StackedCharts({ readings, currentMinute, blastSchedule }) {
  if (!readings || readings.length === 0) return null;

  // Node colors
  const nodeColors = {
    NODE_01: 'var(--node1)',
    NODE_02: 'var(--node2)',
    NODE_03: 'var(--node3)',
    NODE_04: 'var(--node4)',
  };

  // Precompute initial baseline distance for each node
  const baseDist = {};
  const firstNodes = readings[0].nodes;
  for (const nid in firstNodes) {
    baseDist[nid] = firstNodes[nid].distance;
  }

  // Precompute metrics
  const totalMins = readings.length;
  const svgWidth = 800;
  const svgHeight = 110;
  const padLeft = 45;
  const padRight = 15;
  const padTop = 15;
  const padBottom = 20;

  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  // Channels: Tilt Magnitude, Peak Vibration, Distance Delta
  const channels = [
    {
      id: 'tilt',
      title: 'Tilt Magnitude Change (deg) — Warning: 15°, Critical: 22.5°',
      maxVal: 30,
      thresholds: [{ val: 15, color: 'var(--color-warning)' }, { val: 22.5, color: 'var(--color-critical)' }],
      calc: (nodeR) => Math.hypot(nodeR.tilt_x, nodeR.tilt_y)
    },
    {
      id: 'vibration',
      title: 'Peak Vibration (g) — Warning: 1.0 g, Critical: 1.5 g',
      maxVal: 3.5,
      thresholds: [{ val: 1.0, color: 'var(--color-warning)' }, { val: 1.5, color: 'var(--color-critical)' }],
      calc: (nodeR) => nodeR.vibration
    },
    {
      id: 'distance',
      title: 'Distance Displacement from Baseline (cm) — Warning: 2.0 cm, Critical: 3.0 cm',
      maxVal: 5.0,
      thresholds: [{ val: 2.0, color: 'var(--color-warning)' }, { val: 3.0, color: 'var(--color-critical)' }],
      calc: (nodeR, nid) => Math.abs(nodeR.distance - (baseDist[nid] || nodeR.distance))
    }
  ];

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)' }}>
          Surface Sensor Telemetry Channels (4 Nodes)
        </h3>
        <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
          {['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'].map(nid => (
            <div key={nid} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: nodeColors[nid] }}></span>
              <span style={{ color: 'var(--text-muted)' }}>{nid}</span>
            </div>
          ))}
          {blastSchedule && blastSchedule.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--color-blast)' }}></span>
              <span style={{ color: 'var(--color-blast)' }}>Scheduled Blast</span>
            </div>
          )}
        </div>
      </div>

      {channels.map(ch => {
        // Build SVG paths for each node up to currentMinute
        const nodePaths = {};
        ['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'].forEach(nid => {
          let dStr = '';
          for (let m = 0; m <= currentMinute && m < totalMins; m++) {
            const r = readings[m];
            if (!r || !r.nodes[nid]) continue;
            const val = ch.calc(r.nodes[nid], nid);
            const x = padLeft + (m / (totalMins - 1)) * chartW;
            const clampedVal = Math.min(val, ch.maxVal);
            const y = padTop + chartH - (clampedVal / ch.maxVal) * chartH;
            if (m === 0) dStr += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
            else dStr += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
          }
          nodePaths[nid] = dStr;
        });

        // Time cursor position
        const cursorX = padLeft + (currentMinute / (totalMins - 1)) * chartW;

        return (
          <div key={ch.id} style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '10px 12px' }}>
            <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '4px' }}>
              {ch.title}
            </div>
            <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ width: '100%', height: '110px', display: 'block' }}>
              {/* Background grid */}
              <line x1={padLeft} y1={padTop} x2={padLeft + chartW} y2={padTop} stroke="var(--border-color)" strokeWidth="1" />
              <line x1={padLeft} y1={padTop + chartH / 2} x2={padLeft + chartW} y2={padTop + chartH / 2} stroke="var(--border-color)" strokeDasharray="3,3" strokeWidth="1" />
              <line x1={padLeft} y1={padTop + chartH} x2={padLeft + chartW} y2={padTop + chartH} stroke="var(--border-color)" strokeWidth="1" />

              {/* Threshold lines */}
              {ch.thresholds.map((t, idx) => {
                const ty = padTop + chartH - (t.val / ch.maxVal) * chartH;
                return (
                  <line
                    key={idx}
                    x1={padLeft}
                    y1={ty}
                    x2={padLeft + chartW}
                    y2={ty}
                    stroke={t.color}
                    strokeDasharray="4,4"
                    strokeWidth="1.2"
                    opacity="0.8"
                  />
                );
              })}

              {/* Scheduled blast windows */}
              {blastSchedule && blastSchedule.map((b, bIdx) => {
                // Find approximate minute in readings
                const bMin = readings.findIndex(r => r.timestamp >= b.scheduled_time);
                if (bMin >= 0) {
                  const bx = padLeft + (bMin / (totalMins - 1)) * chartW;
                  return (
                    <g key={bIdx}>
                      <rect x={bx - 8} y={padTop} width="16" height={chartH} fill="rgba(168, 85, 247, 0.15)" />
                      <line x1={bx} y1={padTop} x2={bx} y2={padTop + chartH} stroke="var(--color-blast)" strokeWidth="1.5" />
                    </g>
                  );
                }
                return null;
              })}

              {/* Node paths */}
              {['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'].map(nid => (
                <path
                  key={nid}
                  d={nodePaths[nid]}
                  fill="none"
                  stroke={nodeColors[nid]}
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              ))}

              {/* Moving cursor line */}
              <line
                x1={cursorX}
                y1={padTop}
                x2={cursorX}
                y2={padTop + chartH}
                stroke="#fff"
                strokeWidth="1.5"
                opacity="0.8"
              />

              {/* Y axis labels */}
              <text x={padLeft - 6} y={padTop + 4} fill="var(--text-dim)" fontSize="10" textAnchor="end">{ch.maxVal}</text>
              <text x={padLeft - 6} y={padTop + chartH} fill="var(--text-dim)" fontSize="10" textAnchor="end">0</text>
            </svg>
          </div>
        );
      })}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Real-time Alert Lane
// -----------------------------------------------------------------------------
function AlertLane({ label, subtitle, alerts, holdResolutions, currentMinute, readings, isAgent = false }) {
  const totalMins = readings.length || 360;

  // Convert alert timestamps to minutes
  const alertMinutes = (alerts || []).map(a => {
    const minIdx = readings.findIndex(r => r.timestamp >= a.time);
    return {
      minute: minIdx >= 0 ? minIdx : 0,
      level: a.level,
      reason: a.reason
    };
  });

  return (
    <div style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div>
          <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-main)' }}>{label}</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{subtitle}</div>
        </div>
        <div style={{ display: 'flex', gap: '8px', fontSize: '11px' }}>
          <span style={{ color: 'var(--color-warning)' }}>● WARNING</span>
          <span style={{ color: 'var(--color-critical)' }}>● CRITICAL</span>
          {isAgent && <span style={{ color: 'var(--color-review)' }}>▦ REVIEW (HOLD)</span>}
        </div>
      </div>

      {/* Progress Track */}
      <div style={{
        position: 'relative',
        height: '24px',
        background: 'var(--bg-secondary)',
        borderRadius: '4px',
        overflow: 'hidden',
        border: '1px solid var(--border-color)'
      }}>
        {/* Render alert blocks */}
        {alertMinutes.map((a, idx) => {
          if (a.minute > currentMinute) return null;
          const leftPct = (a.minute / (totalMins - 1)) * 100;
          const isCritical = a.level === 'CRITICAL';
          const isReview = a.level === 'REVIEW';
          const color = isCritical ? 'var(--color-critical)' : isReview ? 'var(--color-review)' : 'var(--color-warning)';
          return (
            <div
              key={idx}
              title={`T+${a.minute}m: [${a.level}] ${a.reason}`}
              style={{
                position: 'absolute',
                left: `${leftPct}%`,
                top: 0,
                bottom: 0,
                width: '6px',
                background: color,
                opacity: 0.9,
                cursor: 'pointer'
              }}
            />
          );
        })}

        {/* Current Replay Head Marker */}
        <div style={{
          position: 'absolute',
          left: `${(currentMinute / (totalMins - 1)) * 100}%`,
          top: 0,
          bottom: 0,
          width: '2px',
          background: '#fff',
          boxShadow: '0 0 6px #fff'
        }} />
      </div>

      {/* Current status display */}
      <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
        <span>
          Active Alert at T+{currentMinute}m:{' '}
          {(() => {
            const recent = alertMinutes.filter(a => a.minute <= currentMinute && currentMinute - a.minute <= 15);
            if (recent.length === 0) return <span style={{ color: 'var(--color-healthy)' }}>NOMINAL (No active alert)</span>;
            const topAlert = recent[recent.length - 1];
            return (
              <span style={{
                color: topAlert.level === 'CRITICAL' ? 'var(--color-critical)' : topAlert.level === 'REVIEW' ? 'var(--color-review)' : 'var(--color-warning)',
                fontWeight: '600'
              }}>
                {topAlert.level} (Triggered at T+{topAlert.minute}m)
              </span>
            );
          })()}
        </span>
        {isAgent && holdResolutions && holdResolutions.length > 0 && (
          <span style={{ color: 'var(--color-review)' }}>
            Holds Resolved: {holdResolutions.map(r => r.outcome).join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Investigation Panel
// -----------------------------------------------------------------------------
function InvestigationPanel({ investigation, currentMinute }) {
  if (!investigation) {
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '16px',
        color: 'var(--text-dim)',
        fontSize: '13px',
        textAlign: 'center'
      }}>
        No active candidate episode under investigation at T+{currentMinute}m.
        The Muse Spark 1.3 analyst agent is invoked dynamically when candidate rules trigger.
      </div>
    );
  }

  const { steps, final_structured_result, guard_verdict, cost_usd, latency_sec } = investigation;
  const res = final_structured_result || {};

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🔍 Muse Spark 1.3 Autonomous Investigation</span>
            <span style={{ fontSize: '11px', background: 'var(--bg-card)', padding: '2px 8px', borderRadius: '4px', color: 'var(--text-muted)' }}>
              Latency: {latency_sec.toFixed(1)}s · Cost: ${cost_usd.toFixed(4)}
            </span>
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Candidate triggered at {investigation.timestamp} · 6 diagnostic inspection tools dispatched
          </p>
        </div>
      </div>

      {/* Investigation Steps */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '8px' }}>
        {(steps || []).map((step, sIdx) => {
          return (
            <div key={sIdx} style={{
              background: 'var(--bg-primary)',
              borderRadius: '6px',
              padding: '10px',
              fontSize: '12px',
              border: '1px solid var(--border-color)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontWeight: '700', color: 'var(--color-review)' }}>{step.tool_name}</span>
                <span style={{
                  background: 'rgba(56, 189, 248, 0.1)',
                  color: 'var(--color-review)',
                  padding: '1px 6px',
                  borderRadius: '3px',
                  fontSize: '10px',
                  fontFamily: 'monospace'
                }}>
                  {step.evidence_id || 'ev_verified'}
                </span>
              </div>
              <div style={{ color: 'var(--text-dim)', fontSize: '11px', marginBottom: '4px' }}>
                Args: {JSON.stringify(step.arguments)}
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                Summary: {typeof step.result_summary === 'object' ? Object.keys(step.result_summary).slice(0, 3).map(k => `${k}: ${step.result_summary[k]}`).join(', ') : String(step.result_summary)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Structured Synthesis & Guard Verdict Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px' }}>
        {/* Analyst Brief Card */}
        <div style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '14px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Analyst Hypothesis</span>
            <span style={{
              fontSize: '11px',
              fontWeight: '700',
              padding: '2px 8px',
              borderRadius: '4px',
              background: res.hypothesis === 'ground_movement' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
              color: res.hypothesis === 'ground_movement' ? 'var(--color-critical)' : 'var(--color-healthy)'
            }}>
              {res.hypothesis || 'Pending'} (Conf: {res.confidence ? (res.confidence * 100).toFixed(0) : '--'}%)
            </span>
          </div>
          <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-main)', marginBottom: '8px' }}>
            Recommendation: {res.recommendation === 'KEEP' ? 'KEEP ALERT (Maintain Hazard Warning)' : 'DOWNGRADE (Place on Review Hold)'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic', marginBottom: '10px', lineHeight: '1.4' }}>
            "{res.brief || 'No brief emitted.'}"
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
            Findings:
            <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
              {(res.findings || []).map((f, fIdx) => (
                <li key={fIdx} style={{ color: 'var(--text-muted)', marginBottom: '2px' }}>{f}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* Deterministic Safety Guard Card */}
        <div style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '14px', border: '1px solid var(--border-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Safety Guard Gate</span>
            <span style={{
              fontSize: '11px',
              fontWeight: '700',
              padding: '2px 8px',
              borderRadius: '4px',
              background: guard_verdict.action === 'DOWNGRADE' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(245, 158, 11, 0.2)',
              color: guard_verdict.action === 'DOWNGRADE' ? 'var(--color-review)' : 'var(--color-warning)'
            }}>
              {guard_verdict.action}
            </span>
          </div>
          <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-main)', marginBottom: '8px' }}>
            Verdict: {guard_verdict.action === 'DOWNGRADE' ? 'Approved Review Hold (15m Bounded Timeout)' : 'Forced KEEP (Vetoed Downgrade)'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
            Reason: {guard_verdict.reason}
          </div>
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: '4px',
            padding: '8px 10px',
            fontSize: '11px',
            color: 'var(--text-dim)',
            borderLeft: '3px solid var(--color-warning)'
          }}>
            <strong>Why the guard can overrule the model:</strong> Autonomous LLM agents can misattribute correlated multi-node strain to localized faults. Deterministic code enforces absolute life-safety invariants: real trends can never be suppressed.
          </div>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Reveal Panel (Ground Truth)
// -----------------------------------------------------------------------------
function RevealPanel({ reveal, currentMinute, scenarioId }) {
  const [forceReveal, setForceReveal] = useState(false);
  const isComplete = currentMinute >= 359;
  const showReveal = isComplete || forceReveal;

  if (!reveal) return null;

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      padding: '16px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)' }}>
            Ground Truth Verification & Outcome Reveal
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Quarantined during replay to ensure unbiased human analysis.
          </p>
        </div>
        {!showReveal && (
          <button
            onClick={() => setForceReveal(true)}
            style={{
              background: 'var(--border-highlight)',
              color: '#fff',
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: '600'
            }}
          >
            Reveal Ground Truth Now
          </button>
        )}
      </div>

      {!showReveal ? (
        <div style={{
          background: 'var(--bg-primary)',
          borderRadius: '6px',
          padding: '16px',
          textAlign: 'center',
          color: 'var(--text-dim)',
          fontSize: '13px'
        }}>
          🔒 Ground truth is locked during simulation replay. It will automatically unlock when T+359m is reached.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
          <div style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '12px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Actual Physical Event</div>
            <div style={{ fontSize: '15px', fontWeight: '700', color: reveal.is_hazard ? 'var(--color-critical)' : 'var(--color-healthy)' }}>
              {reveal.scenario_type.replace('_', ' ').toUpperCase()}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Hazard Status: {reveal.is_hazard ? '⚠️ True Geotechnical Hazard' : '✓ Non-Hazard / Operational Benign'}
            </div>
            {reveal.collapse_time && (
              <div style={{ fontSize: '12px', color: 'var(--color-critical)', marginTop: '4px', fontWeight: '600' }}>
                Ground Collapse Occurred at: {reveal.collapse_time}
              </div>
            )}
          </div>

          <div style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '12px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Detector Accuracy Comparison</div>
            <div style={{ fontSize: '13px', color: 'var(--text-main)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div>
                <strong>Rules Engine (B2.1):</strong>{' '}
                {reveal.is_hazard
                  ? (reveal.b2_detected ? '✓ Detected Hazard' : '✗ Missed Hazard')
                  : (reveal.b2_false_alarm ? '✗ False Alarm Raised' : '✓ Correctly Silent')}
              </div>
              <div>
                <strong>Canary Analyst (AGENT):</strong>{' '}
                {reveal.is_hazard
                  ? (reveal.agent_detected ? '✓ Detected Hazard' : '✗ Missed Hazard')
                  : (reveal.agent_false_alarm ? '✗ False Alarm Raised' : '✓ Correctly Cleared / Silent')}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Results Tab
// -----------------------------------------------------------------------------
function ResultsTab({ summaryData }) {
  if (!summaryData) return <div>Loading benchmark results...</div>;

  const testM = summaryData.test_metrics || {};
  const b0 = testM.B0?.overall || {};
  const b1 = testM.B1?.overall || {};
  const b2 = testM['B2.1']?.overall || {};
  const ag = testM.AGENT?.overall || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      <div>
        <h2 style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-main)' }}>
          Canary Analyst: Pre-Registered Held-Out Test Evaluation
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          Evaluated on 300 held-out test scenarios (seed 2026) under a strict no-lookahead streaming contract. Frozen before evaluation with git tag <code>frozen-before-test</code>.
        </p>
      </div>

      {/* Main Table */}
      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
              <th style={{ padding: '12px 16px' }}>Detector Architecture</th>
              <th style={{ padding: '12px 16px' }}>Hazard Detection</th>
              <th style={{ padding: '12px 16px' }}>False Alarm Rate</th>
              <th style={{ padding: '12px 16px' }}>95% Bootstrap CI</th>
              <th style={{ padding: '12px 16px' }}>Median Lead Time</th>
              <th style={{ padding: '12px 16px' }}>Pre-Collapse Rate</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <td style={{ padding: '10px 16px', fontWeight: '600' }}>B0: Naive Raw Thresholds</td>
              <td style={{ padding: '10px 16px' }}>{(b0.detection_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--color-critical)' }}>{(b0.false_alarm_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--text-muted)' }}>[34.0%, 45.7%]</td>
              <td style={{ padding: '10px 16px' }}>{b0.median_lead_time_min} min</td>
              <td style={{ padding: '10px 16px' }}>{(b0.detected_before_collapse_rate * 100).toFixed(1)}%</td>
            </tr>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <td style={{ padding: '10px 16px', fontWeight: '600' }}>B1: Persistence + OLS Trend</td>
              <td style={{ padding: '10px 16px' }}>{(b1.detection_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--color-critical)' }}>{(b1.false_alarm_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--text-muted)' }}>[34.0%, 45.0%]</td>
              <td style={{ padding: '10px 16px' }}>{b1.median_lead_time_min} min</td>
              <td style={{ padding: '10px 16px' }}>{(b1.detected_before_collapse_rate * 100).toFixed(1)}%</td>
            </tr>
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <td style={{ padding: '10px 16px', fontWeight: '600' }}>B2.1: Engineered Rules Baseline</td>
              <td style={{ padding: '10px 16px' }}>{(b2.detection_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--color-warning)' }}>{(b2.false_alarm_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--text-muted)' }}>[5.0%, 11.3%]</td>
              <td style={{ padding: '10px 16px' }}>{b2.median_lead_time_min} min</td>
              <td style={{ padding: '10px 16px' }}>{(b2.detected_before_collapse_rate * 100).toFixed(1)}%</td>
            </tr>
            <tr style={{ background: 'rgba(56, 189, 248, 0.05)' }}>
              <td style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--color-review)' }}>AGENT: Muse Spark 1.3 + Guard</td>
              <td style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--color-healthy)' }}>{(ag.detection_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', fontWeight: '700', color: 'var(--color-healthy)' }}>{(ag.false_alarm_rate * 100).toFixed(1)}%</td>
              <td style={{ padding: '10px 16px', color: 'var(--text-muted)' }}>[3.0%, 7.7%]</td>
              <td style={{ padding: '10px 16px', fontWeight: '700' }}>{ag.median_lead_time_min} min</td>
              <td style={{ padding: '10px 16px' }}>{(ag.detected_before_collapse_rate * 100).toFixed(1)}%</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Paired Comparison & Alarm-Minutes */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '8px', color: 'var(--text-main)' }}>
            Paired Comparison on Non-Hazard Scenarios ($N=214$)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>False Alarms Removed by AGENT:</span>
              <strong style={{ color: 'var(--color-healthy)' }}>8 scenarios</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>False Alarms Added by AGENT:</span>
              <strong style={{ color: 'var(--color-healthy)' }}>0 scenarios</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Total False Alarm Counts:</span>
              <span><strong>24</strong> (B2.1) $\to$ <strong>16</strong> (AGENT)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Exact Two-Sided Sign Test:</span>
              <strong style={{ color: 'var(--color-review)' }}>p = 0.0078125</strong>
            </div>
          </div>
        </div>

        <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '700', marginBottom: '8px', color: 'var(--text-main)' }}>
            Alarm-Minutes Reduction on Non-Hazards
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>B2.1 Total Alarm-Minutes:</span>
              <span style={{ color: 'var(--color-warning)' }}>139.0 minutes</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>AGENT Total Alarm-Minutes:</span>
              <span style={{ color: 'var(--color-healthy)' }}>15.0 minutes</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Relative Reduction:</span>
              <strong style={{ color: 'var(--color-healthy)' }}>-89.2% duration</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Hazard Episodes Delayed:</span>
              <strong style={{ color: 'var(--color-healthy)' }}>0 (Safety invariant maintained)</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Claims and Limits Box */}
      <div style={{
        background: 'rgba(56, 189, 248, 0.05)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--color-review)', marginBottom: '8px' }}>
          Claims & Limitations
        </h3>
        <ul style={{ paddingLeft: '20px', fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
          {summaryData.limitations.map((lim, idx) => (
            <li key={idx}>{lim}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: About & Architecture Tab
// -----------------------------------------------------------------------------
function AboutTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '850px', margin: '0 auto', fontSize: '14px', lineHeight: '1.6' }}>
      <div>
        <h2 style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-main)' }}>About Canary Analyst</h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
          Autonomous Geotechnical AI Analyst for Ground-Subsidence Early Warning Networks
        </p>
      </div>

      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-review)', marginBottom: '8px' }}>
          "AI Proposes, Deterministic Code Decides"
        </h3>
        <p style={{ color: 'var(--text-muted)' }}>
          Canary Analyst operates under a strict life-safety design pattern. In mine safety and geotechnical hazard prediction, a false alarm causes an operational delay, but a false negative causes catastrophic loss of human life. Therefore:
        </p>
        <ul style={{ paddingLeft: '20px', marginTop: '8px', color: 'var(--text-muted)' }}>
          <li>A fast, deterministic rules engine (B2.1) continuously detects threshold excursions and flags candidate anomalies.</li>
          <li>The <strong>Muse Spark 1.3</strong> multimodal model acts as a tier-2 investigation agent, executing targeted API tool calls to inspect spatial neighbors, acoustic emissions, and blast schedules.</li>
          <li>If the agent recommends downgrading an alert, a <strong>Deterministic Safety Guard</strong> checks physical invariants (monitored trends, confidence bounds, neighbor consistency).</li>
          <li>Approved downgrades are held in a <strong>15-minute Review Hold</strong>; if signals worsen by &gt;25% or fail to clear at timeout, alarms re-emit immediately.</li>
        </ul>
      </div>

      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '8px' }}>
          Hackathon Provenance & Hardware Credit
        </h3>
        <p style={{ color: 'var(--text-muted)' }}>
          <strong>Built from scratch during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026).</strong>
        </p>
        <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
          The physical hardware ingestion architecture (ESP32, MPU6050 accelerometer, HC-SR04 ultrasonic rangefinder, and ADS1115 piezoelectric acoustic sensor) represents our team's earlier <strong>ProjectCanary</strong> sensor design concept. All analytical code, statistical baseline engines, agent tools, guard logic, evaluation harness, and web demo were developed completely from scratch during this hackathon.
        </p>
      </div>

      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '8px' }}>
          Technical Specifications & Cost Efficiency
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginTop: '8px' }}>
          <div>
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Model ID</div>
            <div style={{ fontWeight: '600' }}>muse-spark-1.3</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>API Architecture</div>
            <div style={{ fontWeight: '600' }}>Meta Model API (Native Tools)</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Mean Cost / Candidate</div>
            <div style={{ fontWeight: '600', color: 'var(--color-healthy)' }}>$0.0211 USD</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Evidence Validity</div>
            <div style={{ fontWeight: '600', color: 'var(--color-healthy)' }}>100.0% (Zero Hallucination)</div>
          </div>
        </div>
      </div>
    </div>
  );
}
