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
        padding: '12px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>🐤</span>
            <div>
              <h1 style={{ fontSize: '18px', fontWeight: '700', letterSpacing: '-0.3px' }}>Canary Analyst</h1>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>AI Subsidence Network Investigation System</p>
            </div>
          </div>
          <span style={{
            background: activeTab === 'real' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            color: activeTab === 'real' ? '#fbbf24' : '#f87171',
            border: activeTab === 'real' ? '1px solid rgba(234, 179, 8, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            padding: '3px 10px',
            fontSize: '11px',
            fontWeight: '600',
            letterSpacing: '0.5px'
          }}>
            {activeTab === 'real' ? 'REAL PROTOTYPE BENCH RECORDING, not mine data' : 'SIMULATED DATA, not real mine data'}
          </span>
        </div>

        <nav style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('replay')}
            style={{
              padding: '6px 12px',
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
              padding: '6px 12px',
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
            onClick={() => setActiveTab('real')}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              fontWeight: '600',
              background: activeTab === 'real' ? 'var(--bg-card-hover)' : 'transparent',
              color: activeTab === 'real' ? 'var(--text-main)' : 'var(--text-muted)',
              border: activeTab === 'real' ? '1px solid var(--border-highlight)' : '1px solid transparent'
            }}
          >
            Real Recording
          </button>
          <button
            onClick={() => setActiveTab('about')}
            style={{
              padding: '6px 12px',
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
      <main style={{ flex: 1, padding: '16px 20px', maxWidth: '1400px', width: '100%', margin: '0 auto' }}>
        {activeTab === 'replay' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* 6. Small "How to read this" 3-line box */}
            <div style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '10px 14px',
              fontSize: '12px',
              color: 'var(--text-muted)',
              lineHeight: '1.5'
            }}>
              <div>• <strong>Charts show live sensor data</strong> across 4 surface nodes (tilt, vibration, distance) over 6 hours.</div>
              <div>• <strong>Top lane is the rules engine</strong> (B2.1 baseline); <strong>bottom lane is rules + Muse Spark + guard</strong>.</div>
              <div>• <strong>The true event and outcome are revealed at the end</strong> of the replay (or via the Reveal button).</div>
            </div>

            {/* 1. Neutral Scenario Picker Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
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
                      padding: '10px 12px',
                      cursor: 'pointer',
                      transition: 'border-color 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                      <span style={{ fontSize: '13px', fontWeight: '700', color: isSelected ? 'var(--color-review)' : 'var(--text-main)' }}>
                        {scen.title}
                      </span>
                      {isSelected && <span style={{ fontSize: '11px', color: 'var(--color-healthy)' }}>● ACTIVE</span>}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      {scen.subtitle || 'Monitoring chunk, 4 nodes, 6 hours'}
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
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              flexWrap: 'wrap'
            }}>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  style={{
                    background: isPlaying ? 'var(--color-warning)' : 'var(--color-healthy)',
                    color: '#000',
                    fontWeight: '700',
                    padding: '6px 14px',
                    fontSize: '12px'
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
                    padding: '6px 10px',
                    fontSize: '12px'
                  }}
                >
                  ⏮ RESET
                </button>
              </div>

              {/* Speeds */}
              <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Speed:</span>
                {[1, 5, 20].map(s => (
                  <button
                    key={s}
                    onClick={() => setPlaySpeed(s)}
                    style={{
                      background: playSpeed === s ? 'var(--border-highlight)' : 'var(--bg-card)',
                      color: playSpeed === s ? 'var(--text-main)' : 'var(--text-muted)',
                      border: '1px solid var(--border-color)',
                      padding: '3px 7px',
                      fontSize: '11px',
                      fontWeight: '600'
                    }}
                  >
                    {s}x
                  </button>
                ))}
              </div>

              {/* Scrubber slider */}
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '10px', minWidth: '180px' }}>
                <input
                  type="range"
                  min="0"
                  max="359"
                  value={currentMinute}
                  onChange={e => setCurrentMinute(parseInt(e.target.value))}
                  style={{ flex: 1, accentColor: 'var(--color-review)', cursor: 'pointer' }}
                />
                <span style={{ fontSize: '12px', fontFamily: 'monospace', minWidth: '85px', color: 'var(--text-main)' }}>
                  T+{currentMinute}m / 360m
                </span>
              </div>

              {/* Timestamp display */}
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                {currentReading ? currentReading.timestamp : '--:--:--Z'}
              </div>
            </div>

            {/* Stacked Charts & Alert Lanes Grid */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
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
                padding: '14px'
              }}>
                <h3 style={{ fontSize: '13px', fontWeight: '700', marginBottom: '10px', color: 'var(--text-main)' }}>
                  Real-Time Detection & Alert Timeline (0 to 360 min)
                </h3>
                <AlertLane
                  label="Deterministic Rules Baseline (B2.1)"
                  subtitle="Persistent 3/5 thresholding + lag-1 autocorrelation adjusted trend"
                  alerts={b2Alerts}
                  currentMinute={currentMinute}
                  readings={readings}
                />
                <div style={{ height: '12px' }}></div>
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

            {/* 4. Investigation Panel */}
            <InvestigationPanel
              investigation={latestInvestigation}
              currentMinute={currentMinute}
            />

            {/* 5. Reveal Panel */}
            <RevealPanel
              reveal={scenarioData ? scenarioData.reveal : null}
              currentMinute={currentMinute}
              scenarioData={scenarioData}
            />
          </div>
        )}

        {activeTab === 'results' && <ResultsTab summaryData={summaryData} />}

        {activeTab === 'real' && <RealRecordingTab />}

        {activeTab === 'about' && <AboutTab />}
      </main>

      {/* Footer */}
      <footer style={{
        background: 'var(--bg-secondary)',
        borderTop: '1px solid var(--border-color)',
        padding: '12px 20px',
        fontSize: '12px',
        color: 'var(--text-muted)',
        display: 'flex',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '8px'
      }}>
        <div>Canary Analyst — Meta Global AI Developer Hackathon 2026</div>
        <div>Operational Notice: The system advises and recommends; human site authority decides evacuation.</div>
      </footer>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Stacked Sensor Charts
// -----------------------------------------------------------------------------
function StackedCharts({ readings, currentMinute, blastSchedule }) {
  if (!readings || readings.length === 0) return null;

  const nodeColors = {
    NODE_01: 'var(--node1)',
    NODE_02: 'var(--node2)',
    NODE_03: 'var(--node3)',
    NODE_04: 'var(--node4)',
  };

  const baseDist = {};
  const firstNodes = readings[0].nodes;
  for (const nid in firstNodes) {
    baseDist[nid] = firstNodes[nid].distance;
  }

  const totalMins = readings.length;
  // Use viewBox 0 0 1000 110 so the plot area extends fully across the card width
  const svgWidth = 1000;
  const svgHeight = 110;
  const padLeft = 45;
  const padRight = 10;
  const padTop = 15;
  const padBottom = 20;

  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

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
      padding: '14px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <h3 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-main)' }}>
          Surface Sensor Telemetry Channels (4 Nodes)
        </h3>
        <div style={{ display: 'flex', gap: '14px', fontSize: '11px', flexWrap: 'wrap' }}>
          {['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'].map(nid => (
            <div key={nid} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: nodeColors[nid] }}></span>
              <span style={{ color: 'var(--text-muted)' }}>{nid}</span>
            </div>
          ))}
          {blastSchedule && blastSchedule.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ width: '9px', height: '9px', borderRadius: '2px', background: 'var(--color-blast)' }}></span>
              <span style={{ color: 'var(--color-blast)' }}>Scheduled Blast</span>
            </div>
          )}
        </div>
      </div>

      {channels.map(ch => {
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

        const cursorX = padLeft + (currentMinute / (totalMins - 1)) * chartW;

        return (
          <div key={ch.id} style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '10px 12px' }}>
            <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '4px' }}>
              {ch.title}
            </div>
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              preserveAspectRatio="none"
              style={{ width: '100%', height: '110px', display: 'block' }}
            >
              <line x1={padLeft} y1={padTop} x2={padLeft + chartW} y2={padTop} stroke="var(--border-color)" strokeWidth="1" />
              <line x1={padLeft} y1={padTop + chartH / 2} x2={padLeft + chartW} y2={padTop + chartH / 2} stroke="var(--border-color)" strokeDasharray="3,3" strokeWidth="1" />
              <line x1={padLeft} y1={padTop + chartH} x2={padLeft + chartW} y2={padTop + chartH} stroke="var(--border-color)" strokeWidth="1" />

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

              {blastSchedule && blastSchedule.map((b, bIdx) => {
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

              <line
                x1={cursorX}
                y1={padTop}
                x2={cursorX}
                y2={padTop + chartH}
                stroke="#fff"
                strokeWidth="1.5"
                opacity="0.8"
              />

              <text x={padLeft - 6} y={padTop + 4} fill="var(--text-dim)" fontSize="10" textAnchor="end">{ch.maxVal}</text>
              <text x={padLeft - 6} y={padTop + chartH} fill="var(--text-dim)" fontSize="10" textAnchor="end">0</text>
            </svg>
            {/* 5. Short caption under each chart */}
            <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '3px', textAlign: 'right' }}>
              Lines show change from each node's baseline.
            </div>
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
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

      <div style={{
        position: 'relative',
        height: '24px',
        background: 'var(--bg-secondary)',
        borderRadius: '4px',
        overflow: 'hidden',
        border: '1px solid var(--border-color)'
      }}>
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

      <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '4px' }}>
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
        padding: '14px',
        color: 'var(--text-dim)',
        fontSize: '12px',
        textAlign: 'center'
      }}>
        No active candidate episode under investigation at T+{currentMinute}m.
        The Muse Spark 1.3 analyst agent is invoked dynamically when candidate rules trigger.
      </div>
    );
  }

  const { steps, final_structured_result, guard_verdict, cost_usd, latency_sec } = investigation;
  const res = final_structured_result || {};
  const isVetoed = guard_verdict.action !== 'DOWNGRADE' && (guard_verdict.failed_conditions && guard_verdict.failed_conditions.length > 0);

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
          <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span>🔍 Muse Spark 1.3 Autonomous Investigation</span>
            <span style={{ fontSize: '11px', background: 'var(--bg-card)', padding: '2px 8px', borderRadius: '4px', color: 'var(--text-muted)' }}>
              Latency: {latency_sec.toFixed(1)}s · Cost: ${cost_usd.toFixed(4)}
            </span>
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Candidate triggered at {investigation.timestamp} · Diagnostic inspection tools dispatched
          </p>
        </div>
      </div>

      {/* Investigation Steps with Real Compact Summaries */}
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
              <div style={{ color: 'var(--text-muted)', fontSize: '11px', fontFamily: 'monospace' }}>
                Summary: {step.result_summary || 'Completed'}
              </div>
            </div>
          );
        })}
      </div>

      {/* Structured Synthesis & Guard Verdict Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' }}>
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
            Recommendation: {res.recommendation === 'KEEP' ? 'KEEP ALERT (Maintain Hazard Warning)' : 'DOWNGRADE (Propose Review Hold)'}
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
              background: guard_verdict.action === 'DOWNGRADE' ? 'rgba(56, 189, 248, 0.2)' : isVetoed ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
              color: guard_verdict.action === 'DOWNGRADE' ? 'var(--color-review)' : isVetoed ? 'var(--color-critical)' : 'var(--color-warning)'
            }}>
              {guard_verdict.action === 'DOWNGRADE' ? 'APPROVED' : isVetoed ? 'VETOED (FORCED KEEP)' : 'CONFIRMED KEEP'}
            </span>
          </div>
          
          <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-main)', marginBottom: '6px' }}>
            {guard_verdict.action === 'DOWNGRADE'
              ? 'Verdict: Approved Review Hold (15-min bounded observation)'
              : isVetoed
              ? 'Verdict: Downgrade Vetoed by Deterministic Gate'
              : 'Verdict: Alert Maintained (Analyst Recommended KEEP)'}
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
            <strong>Gate Outcome:</strong> {guard_verdict.reason}
          </div>

          {isVetoed && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '4px',
              padding: '6px 10px',
              marginBottom: '10px',
              fontSize: '11px',
              color: '#f87171'
            }}>
              <strong>Failed Gate:</strong> {guard_verdict.failed_conditions.join('; ')}
            </div>
          )}

          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: '4px',
            padding: '8px 10px',
            fontSize: '11px',
            color: 'var(--text-dim)',
            borderLeft: '3px solid var(--color-warning)',
            lineHeight: '1.4'
          }}>
            The model proposes, deterministic checks recomputed from tool data decide. If the evidence cannot be verified, the alert stays. The system recommends; a human site authority decides.
          </div>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Component: Reveal Panel (Ground Truth)
// -----------------------------------------------------------------------------
function RevealPanel({ reveal, currentMinute, scenarioData }) {
  const [forceReveal, setForceReveal] = useState(false);
  const isComplete = currentMinute >= 359;
  const showReveal = isComplete || forceReveal;

  if (!reveal) return null;

  let b2LeadTimeMin = null;
  let agLeadTimeMin = null;

  if (reveal.is_hazard && reveal.collapse_time && scenarioData) {
    const tCollapse = new Date(reveal.collapse_time).getTime();

    if (scenarioData.b2_alerts && scenarioData.b2_alerts.length > 0) {
      const tB2Alert = new Date(scenarioData.b2_alerts[0].time).getTime();
      b2LeadTimeMin = Math.round((tCollapse - tB2Alert) / 60000);
    }

    if (scenarioData.agent_alerts && scenarioData.agent_alerts.length > 0) {
      const tAgAlert = new Date(scenarioData.agent_alerts[0].time).getTime();
      agLeadTimeMin = Math.round((tCollapse - tAgAlert) / 60000);
    }
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      padding: '16px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
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
                Ground Collapse Time: {reveal.collapse_time}
              </div>
            )}
            {b2LeadTimeMin !== null && (
              <div style={{ fontSize: '12px', color: 'var(--text-main)', marginTop: '4px' }}>
                Lead Time (Collapse − First Alert): <strong>{agLeadTimeMin} min</strong> (B2.1: {b2LeadTimeMin} min)
              </div>
            )}
          </div>

          <div style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '12px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Detector Accuracy Comparison</div>
            <div style={{ fontSize: '13px', color: 'var(--text-main)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div>
                <strong>Rules Engine (B2.1):</strong>{' '}
                {reveal.is_hazard
                  ? (reveal.b2_detected ? `✓ Detected Hazard (${b2LeadTimeMin}m lead time)` : '✗ Missed Hazard')
                  : (reveal.b2_false_alarm ? '✗ False Alarm Raised' : '✓ Correctly Silent')}
              </div>
              <div>
                <strong>Canary Analyst (AGENT):</strong>{' '}
                {reveal.is_hazard
                  ? (reveal.agent_detected ? `✓ Detected Hazard (${agLeadTimeMin}m lead time)` : '✗ Missed Hazard')
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
  const [showBreakdown, setShowBreakdown] = useState(false);

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

      {/* Primary Key Findings Header Box */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '16px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px'
      }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Paired Comparison (Exact Sign Test)</div>
          <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--color-healthy)', marginTop: '2px' }}>
            -8 FA / +0 FA
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Of 214 non-hazard scenarios the agent removed 8 false alarms and added 0 (exact sign test p = 0.0078)
          </div>
        </div>

        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Hazard Detection & Safety</div>
          <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--color-healthy)', marginTop: '2px' }}>
            86 of 86 hazards <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: '400' }}>(100.0%)</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            <strong>0 hazard scenarios ever held</strong> (all 110 stream hazard candidates recommended KEEP)
          </div>
        </div>

        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>False-Alarm Scenarios</div>
          <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--color-healthy)', marginTop: '2px' }}>
            24 to 16 of 300 <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: '400' }}>(8.0% to 5.3%)</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '2px' }}>
            Note: 95% intervals overlap ([5.0, 11.3] and [3.0, 7.7])
          </div>
        </div>
      </div>

      {/* Baseline vs Agent Attribution Note */}
      <div style={{
        background: 'var(--bg-primary)',
        borderLeft: '4px solid var(--color-review)',
        padding: '12px 16px',
        borderRadius: '0 6px 6px 0',
        fontSize: '13px',
        lineHeight: '1.5',
        color: 'var(--text-main)'
      }}>
        Most of the false-alarm reduction (40.0% to 8.0%) comes from the frozen rules baseline B2.1, whose 90-minute projection window was chosen after a sweep on dev data (80/90/100 gave 10.7/6.7/11.2% false alarms); the agent adds a further 8 removals on top, each one checked by the guard.
      </div>

      {/* Main Table with Footnote on Pre-Collapse Rate */}
      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
              <th style={{ padding: '12px 16px' }}>Detector Architecture</th>
              <th style={{ padding: '12px 16px' }}>Hazard Detection</th>
              <th style={{ padding: '12px 16px' }}>False Alarm Rate</th>
              <th style={{ padding: '12px 16px' }}>95% Bootstrap CI</th>
              <th style={{ padding: '12px 16px' }}>Median Lead Time</th>
              <th style={{ padding: '12px 16px' }}>Pre-Collapse Rate *</th>
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
        {/* Footnote defining Pre-Collapse Rate */}
        <div style={{ padding: '8px 16px', fontSize: '11px', color: 'var(--text-dim)', borderTop: '1px solid var(--border-color)', background: 'var(--bg-primary)' }}>
          * <strong>Pre-Collapse Rate</strong>: share of creep scenarios warned before the simulated collapse (lead_time &gt; 0).
        </div>
      </div>

      {/* Model Sensitivity Card */}
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: '8px',
        padding: '16px',
        border: '1px solid var(--border-color)'
      }}>
        <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '8px' }}>
          Model Sensitivity (Held-Out Test Set, N=300)
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
          False-alarm scenarios of 300: 16 (1.3), 17 (1.2), 15 (1.1); hazard detection 86 of 86 for all; same frozen pipeline; the 1.2 figure carries a caveat (see README).
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <div style={{ background: 'var(--bg-card)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Muse Spark 1.3 (Headline)</div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: 'var(--color-healthy)', marginTop: '2px' }}>16 / 300 FA (5.3%)</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Hazard Det: 86 / 86 (100%)</div>
          </div>
          <div style={{ background: 'var(--bg-card)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Muse Spark 1.2 *</div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: 'var(--color-healthy)', marginTop: '2px' }}>17 / 300 FA (5.7%)</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Hazard Det: 86 / 86 (100%)</div>
          </div>
          <div style={{ background: 'var(--bg-card)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Muse Spark 1.1</div>
            <div style={{ fontSize: '16px', fontWeight: '700', color: 'var(--color-healthy)', marginTop: '2px' }}>15 / 300 FA (5.0%)</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Hazard Det: 86 / 86 (100%)</div>
          </div>
        </div>
      </div>

      {/* Post-Hoc Breakdown Collapsible */}
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: '8px',
        padding: '16px',
        border: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
            Post-hoc breakdown by scenario type (descriptive, not a test)
          </h3>
          <button
            onClick={() => setShowBreakdown(!showBreakdown)}
            style={{
              padding: '4px 10px',
              fontSize: '12px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '4px',
              color: 'var(--text-main)',
              cursor: 'pointer'
            }}
          >
            {showBreakdown ? 'Hide Breakdown' : 'Show Breakdown'}
          </button>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px', marginBottom: showBreakdown ? '12px' : 0 }}>
          These breakdowns were computed after the test run and played no part in any design choice. 8 approved downgrades created 8 REVIEW holds, all cleared, none on a hazard scenario.
        </p>

        {showBreakdown && (
          <div style={{ overflowX: 'auto', marginTop: '12px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                  <th style={{ padding: '8px 12px' }}>Scenario Type (214 non-hazard)</th>
                  <th style={{ padding: '8px 12px' }}>B2.1 False Alarms</th>
                  <th style={{ padding: '8px 12px' }}>Agent False Alarms</th>
                  <th style={{ padding: '8px 12px' }}>Removed</th>
                  <th style={{ padding: '8px 12px' }}>Added</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '6px 12px', fontWeight: '600' }}>blast (N=43)</td>
                  <td style={{ padding: '6px 12px' }}>4</td>
                  <td style={{ padding: '6px 12px' }}>1</td>
                  <td style={{ padding: '6px 12px', color: 'var(--color-healthy)' }}>3</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '6px 12px', fontWeight: '600' }}>machinery_impact (N=43)</td>
                  <td style={{ padding: '6px 12px' }}>1</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                  <td style={{ padding: '6px 12px', color: 'var(--color-healthy)' }}>1</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '6px 12px', fontWeight: '600' }}>rain_tilt (N=43)</td>
                  <td style={{ padding: '6px 12px' }}>4</td>
                  <td style={{ padding: '6px 12px' }}>1</td>
                  <td style={{ padding: '6px 12px', color: 'var(--color-healthy)' }}>3</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '6px 12px', fontWeight: '600' }}>sensor_fault (N=43)</td>
                  <td style={{ padding: '6px 12px' }}>12</td>
                  <td style={{ padding: '6px 12px' }}>12</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '6px 12px', fontWeight: '600' }}>stuck_sensor (N=42)</td>
                  <td style={{ padding: '6px 12px' }}>2</td>
                  <td style={{ padding: '6px 12px' }}>1</td>
                  <td style={{ padding: '6px 12px', color: 'var(--color-healthy)' }}>1</td>
                  <td style={{ padding: '6px 12px' }}>0</td>
                </tr>
                <tr style={{ background: 'var(--bg-card)', fontWeight: '700' }}>
                  <td style={{ padding: '8px 12px' }}>Total (N=214)</td>
                  <td style={{ padding: '8px 12px' }}>23</td>
                  <td style={{ padding: '8px 12px' }}>15</td>
                  <td style={{ padding: '8px 12px', color: 'var(--color-healthy)' }}>8</td>
                  <td style={{ padding: '8px 12px' }}>0</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
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
          <li style={{ fontWeight: '600', color: 'var(--text-main)' }}>
            12 of 43 silent sensor faults still alarm, results are on simulated data, thresholds are demonstration values.
          </li>
          {summaryData.limitations.map((lim, idx) => (
            <li key={idx} style={{ color: 'var(--text-muted)' }}>
              {lim}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function AboutTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '850px', margin: '0 auto', fontSize: '14px', lineHeight: '1.6' }}>
      <div>
        <h2 style={{ fontSize: '22px', fontWeight: '700', color: 'var(--text-main)' }}>About Canary Analyst</h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
          Autonomous Geotechnical AI Analyst for Ground-Subsidence Early Warning Networks
        </p>
      </div>

      {/* Headline Findings Summary */}
      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-healthy)', marginBottom: '8px' }}>
          Core Benchmark Evidence & Verification
        </h3>
        <ul style={{ paddingLeft: '20px', marginTop: '8px', color: 'var(--text-muted)' }}>
          <li><strong>Paired Result:</strong> Of 214 non-hazard scenarios the agent removed 8 false alarms and added 0 (exact sign test p = 0.0078).</li>
          <li><strong>Hazard Detection:</strong> 86 of 86 hazards detected and 0 hazard scenarios ever held.</li>
          <li><strong>False-Alarm Scenarios:</strong> 24 to 16 of 300 (8.0% to 5.3%), with the note that the 95% intervals overlap ([5.0, 11.3] and [3.0, 7.7]).</li>
          <li>Most of the false-alarm reduction (40.0% to 8.0%) comes from the frozen rules baseline B2.1, whose 90-minute projection window was chosen after a sweep on dev data (80/90/100 gave 10.7/6.7/11.2% false alarms); the agent adds a further 8 removals on top, each one checked by the guard.</li>
          <li><strong>Known Limits:</strong> 12 of 43 silent sensor faults still alarm, results are on simulated data, thresholds are demonstration values.</li>
        </ul>
      </div>

      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-review)', marginBottom: '8px' }}>
          &quot;AI Proposes, Deterministic Code Decides&quot;
        </h3>
        <p style={{ color: 'var(--text-muted)' }}>
          Canary Analyst operates under a strict life-safety design pattern. In mine safety and geotechnical hazard prediction, a false alarm causes an operational delay, but a false negative causes catastrophic loss of human life. Therefore:
        </p>
        <ul style={{ paddingLeft: '20px', marginTop: '8px', color: 'var(--text-muted)' }}>
          <li>A fast, deterministic rules engine (B2.1) continuously detects threshold excursions and flags candidate anomalies.</li>
          <li>The <strong>Muse Spark 1.3</strong> foundation model acts as an autonomous <strong>text-and-tools investigation agent</strong>, executing targeted API tool calls to inspect spatial neighbors, acoustic emissions, and blast schedules.</li>
          <li>If the agent recommends downgrading an alert, a <strong>Deterministic Safety Guard</strong> checks physical invariants (monitored trends, confidence bounds, neighbor consistency).</li>
          <li>Approved downgrades are held in a <strong>15-minute Review Hold</strong>; if signals worsen by &gt;25% or fail to clear at timeout, alarms re-emit immediately.</li>
        </ul>
      </div>

      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '8px' }}>
          Hackathon Provenance & Hardware Credit
        </h3>
        <p style={{ color: 'var(--text-muted)' }}>
          <strong>Built from scratch during the Meta Global AI Developer Hackathon (Oct 27 - Nov 4, 2026).</strong>
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
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Agent Mode</div>
            <div style={{ fontWeight: '600' }}>text-and-tools investigation agent</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Mean Cost / Candidate</div>
            <div style={{ fontWeight: '600', color: 'var(--color-healthy)' }}>.0215 USD</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Evidence Verification</div>
            <div style={{ fontWeight: '600', color: 'var(--color-healthy)' }}>100% of cited evidence IDs matched real tool outputs (714 of 714)</div>
          </div>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '12px' }}>
          We did not compare against non-Meta models, so we make no claim that Muse Spark beats them.
        </p>
      </div>

      <div style={{ background: 'var(--bg-secondary)', borderRadius: '8px', padding: '16px', border: '1px solid var(--border-color)' }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '8px' }}>
          Audit Notes & Corrections
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
          <strong>Cache Key Collision & Test Rerun:</strong> The original cache key in <code>agent/analyst.py</code> did not include a dataset split name. Because scenario IDs are shared between the dev and test splits, 16 test candidates were initially served from dev-split cache entries. An audit identified this and re-ran all 16 candidates live on held-out test data in <code>results/test_rerun16/</code>. All 16 reran live as KEEP; 15 kept the same label (ground_movement) and 1 (SCENARIO_0009_slow_creep_002) changed from unclear (0.55) to ground_movement (0.90); detection and scenario-level results are unchanged.
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>
          <strong>Candidate-Level Numbers Corrected:</strong> Published headline candidate numbers originally included 9 exploratory dev entries from the shared cache (142 candidates, .99 USD, 761 evidence IDs). Filtered strictly to the 133 test stream candidates with the live test rerun data, verified candidate metrics are: 133 candidate episodes, 107 of 110 hazard candidates labelled <code>ground_movement</code> (97.3%), 714 of 714 valid evidence IDs (100.0%), and .86 USD total cost (.0215 / candidate).
        </p>
      </div>
    </div>
  );
}


function RealRecordingTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('./demo/real_session.json')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(json => {
        setData(json);
        setLoading(false);
      })
      .catch(err => {
        fetch('./real_session.json')
          .then(res => res.json())
          .then(json => {
            setData(json);
            setLoading(false);
          })
          .catch(e => {
            setError(e.message);
            setLoading(false);
          });
      });
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading real prototype recording data...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-critical)' }}>
        Error loading real session data: {error || 'No data found'}
      </div>
    );
  }

  const series = data.minute_series || [];
  const totalMins = series.length;
  const nodes = ['NODE_01', 'NODE_02'];
  const nodeColors = {
    NODE_01: '#38bdf8',
    NODE_02: '#34d399',
  };

  const svgWidth = 800;
  const svgHeight = 110;
  const padLeft = 45;
  const padRight = 20;
  const padTop = 15;
  const padBottom = 20;
  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  const baselineX = padLeft + (29 / Math.max(1, totalMins - 1)) * chartW;
  const alertMinuteIdx = series.findIndex(s => s.timestamp_ist === '13:56');
  const alertX = alertMinuteIdx >= 0 ? padLeft + (alertMinuteIdx / Math.max(1, totalMins - 1)) * chartW : baselineX;

  const channels = [
    {
      id: 'distance',
      title: 'Distance (cm) — HC-SR04 Ultrasonic Range',
      unit: 'cm',
      minVal: 0,
      maxVal: 50,
      getVal: (nR) => nR.distance,
      thresholds: []
    },
    {
      id: 'tilt_mag',
      title: 'Tilt Magnitude (deg) — MPU6050 Accelerometer',
      unit: 'deg',
      minVal: 0,
      maxVal: 0.5,
      getVal: (nR) => nR.tilt_mag,
      thresholds: []
    },
    {
      id: 'vibration',
      title: 'Vibration (g) — Peak Acceleration',
      unit: 'g',
      minVal: 0,
      maxVal: 0.2,
      getVal: (nR) => nR.vibration,
      thresholds: [{ val: 0.1, label: 'Excursion ~0.13g', color: 'var(--color-warning)' }]
    },
    {
      id: 'piezo_peak',
      title: 'Acoustic / Piezo Peak (V) — ADS1115 ADC',
      unit: 'V',
      minVal: 0,
      maxVal: 0.6,
      getVal: (nR) => nR.piezo_peak,
      thresholds: [{ val: 0.1, label: 'Acoustic Threshold', color: 'var(--color-critical)' }]
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* 1. Header & Mandatory Disclaimer Banner */}
      <div style={{
        background: 'rgba(234, 179, 8, 0.08)',
        border: '1px solid rgba(234, 179, 8, 0.35)',
        borderRadius: '8px',
        padding: '16px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '20px' }}>⚠️</span>
          <span style={{ fontSize: '14px', fontWeight: '700', color: '#fbbf24', letterSpacing: '0.3px' }}>
            PROTOTYPE RECORDING DISCLAIMER & METHODOLOGY NOTE
          </span>
        </div>
        <p style={{ fontSize: '13px', lineHeight: '1.6', color: 'var(--text-main)', margin: 0, fontWeight: '500' }}>
          {data.disclaimer}
        </p>
        <p style={{ fontSize: '12px', lineHeight: '1.5', color: 'var(--text-muted)', margin: 0 }}>
          {data.fail_closed_note}
        </p>
      </div>

      {/* 2. Session Info Bar */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '12px 18px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '24px',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Session ID: </span>
          <strong style={{ fontSize: '13px', color: 'var(--text-main)' }}>{data.session_id}</strong>
          <span style={{ margin: '0 8px', color: 'var(--border-color)' }}>|</span>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Date: </span>
          <strong style={{ fontSize: '13px', color: 'var(--text-main)' }}>{data.recorded_date}</strong>
          <span style={{ margin: '0 8px', color: 'var(--border-color)' }}>|</span>
          <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Duration: </span>
          <strong style={{ fontSize: '13px', color: 'var(--text-main)' }}>{data.duration_minutes} minutes ({series[0]?.timestamp_ist} – {series[series.length - 1]?.timestamp_ist} IST)</strong>
        </div>
        <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: nodeColors.NODE_01 }}></span>
            <span style={{ fontWeight: '600' }}>NODE_01 (x=0.00 m)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: nodeColors.NODE_02 }}></span>
            <span style={{ fontWeight: '600' }}>NODE_02 (x=0.43 m)</span>
          </div>
        </div>
      </div>

      {/* 3. Sensor Telemetry Charts (4 Channels) */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
              Prototype Telemetry Time Series (37 Minutes, Resampled 1-min)
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-dim)', margin: '2px 0 0 0' }}>
              Shaded region denotes the 30-minute detector baseline window (13:27 – 13:56 IST). Alert evaluated at end of baseline.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px', fontSize: '11px', alignItems: 'center' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '12px', height: '8px', background: 'rgba(56, 189, 248, 0.1)', border: '1px dashed var(--color-review)' }}></span>
              Baseline (30m)
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '12px', height: '2px', background: 'var(--color-critical)' }}></span>
              13:56 Alert
            </span>
          </div>
        </div>

        {channels.map(ch => {
          const paths = {};
          nodes.forEach(nid => {
            let dStr = '';
            series.forEach((s, idx) => {
              const nR = s.nodes[nid];
              if (!nR) return;
              const val = ch.getVal(nR);
              const x = padLeft + (idx / Math.max(1, totalMins - 1)) * chartW;
              const clamped = Math.max(ch.minVal, Math.min(val, ch.maxVal));
              const y = padTop + chartH - ((clamped - ch.minVal) / (ch.maxVal - ch.minVal)) * chartH;
              if (dStr === '') dStr += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
              else dStr += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
            });
            paths[nid] = dStr;
          });

          return (
            <div key={ch.id} style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '10px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '4px' }}>
                <span>{ch.title}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Range: [{ch.minVal} – {ch.maxVal} {ch.unit}]</span>
              </div>
              <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} preserveAspectRatio="none" style={{ width: '100%', height: '105px', display: 'block' }}>
                {/* Baseline 30-min shading */}
                <rect
                  x={padLeft}
                  y={padTop}
                  width={baselineX - padLeft}
                  height={chartH}
                  fill="rgba(56, 189, 248, 0.04)"
                />
                <line
                  x1={baselineX}
                  y1={padTop}
                  x2={baselineX}
                  y2={padTop + chartH}
                  stroke="var(--color-review)"
                  strokeDasharray="3,3"
                  strokeWidth="1.5"
                />

                {/* Horizontal reference grid lines */}
                <line x1={padLeft} y1={padTop} x2={padLeft + chartW} y2={padTop} stroke="var(--border-color)" strokeWidth="1" />
                <line x1={padLeft} y1={padTop + chartH / 2} x2={padLeft + chartW} y2={padTop + chartH / 2} stroke="var(--border-color)" strokeDasharray="3,3" strokeWidth="1" />
                <line x1={padLeft} y1={padTop + chartH} x2={padLeft + chartW} y2={padTop + chartH} stroke="var(--border-color)" strokeWidth="1" />

                {/* Optional channel thresholds */}
                {ch.thresholds.map((t, idx) => {
                  const ty = padTop + chartH - ((t.val - ch.minVal) / (ch.maxVal - ch.minVal)) * chartH;
                  return (
                    <g key={idx}>
                      <line x1={padLeft} y1={ty} x2={padLeft + chartW} y2={ty} stroke={t.color} strokeDasharray="4,2" strokeWidth="1" />
                      <text x={padLeft + 4} y={ty - 3} fill={t.color} fontSize="9" fontFamily="monospace">{t.label}</text>
                    </g>
                  );
                })}

                {/* Node curves */}
                {nodes.map(nid => (
                  <path
                    key={nid}
                    d={paths[nid] || ''}
                    fill="none"
                    stroke={nodeColors[nid]}
                    strokeWidth="2"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                ))}

                {/* Alert vertical marker at 13:56 IST */}
                <line
                  x1={alertX}
                  y1={padTop}
                  x2={alertX}
                  y2={padTop + chartH}
                  stroke="var(--color-critical)"
                  strokeWidth="2"
                />
                <text x={alertX + 3} y={padTop + 10} fill="var(--color-critical)" fontSize="9" fontWeight="700">13:56 ALERT</text>

                {/* Y-axis labels */}
                <text x={padLeft - 6} y={padTop + 8} fill="var(--text-dim)" fontSize="10" textAnchor="end" fontFamily="monospace">{ch.maxVal}</text>
                <text x={padLeft - 6} y={padTop + chartH / 2 + 3} fill="var(--text-dim)" fontSize="10" textAnchor="end" fontFamily="monospace">{((ch.maxVal + ch.minVal) / 2).toFixed(1)}</text>
                <text x={padLeft - 6} y={padTop + chartH} fill="var(--text-dim)" fontSize="10" textAnchor="end" fontFamily="monospace">{ch.minVal}</text>

                {/* X-axis time ticks */}
                {series.map((s, idx) => {
                  if (idx % 5 === 0 || idx === totalMins - 1) {
                    const x = padLeft + (idx / Math.max(1, totalMins - 1)) * chartW;
                    return (
                      <g key={idx}>
                        <line x1={x} y1={padTop + chartH} x2={x} y2={padTop + chartH + 4} stroke="var(--border-color)" strokeWidth="1" />
                        <text x={x} y={padTop + chartH + 14} fill="var(--text-dim)" fontSize="9" textAnchor="middle" fontFamily="monospace">
                          {s.timestamp_ist}
                        </text>
                      </g>
                    );
                  }
                  return null;
                })}
              </svg>
            </div>
          );
        })}
      </div>

      {/* 4. Unlabelled Physical Disturbances Cards */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
          Observed Unlabelled Disturbances in Prototype Session
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-dim)', margin: 0 }}>
          Recordings capture bench hardware tests with deliberate manual adjustments and physical moves. No ground truth labels were supplied.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px', marginTop: '6px' }}>
          {(data.unlabelled_disturbances || []).map((ev, idx) => (
            <div key={idx} style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              padding: '12px 14px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--color-review)' }}>
                  {ev.event}
                </span>
                <span style={{ fontSize: '11px', fontFamily: 'monospace', background: 'rgba(56, 189, 248, 0.1)', color: 'var(--color-review)', padding: '2px 6px', borderRadius: '4px' }}>
                  {ev.time_ist} IST ({ev.time_utc})
                </span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                <strong>Node:</strong> {ev.node_id} | <strong>Channel:</strong> {ev.channel}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-main)', lineHeight: '1.4' }}>
                {ev.details}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', borderTop: '1px dashed var(--border-color)', paddingTop: '6px', marginTop: '2px' }}>
                {ev.impact}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Baseline Engine Alerts vs Agent Investigation */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
        {/* Baseline Detection Card */}
        <div style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-critical)', margin: 0 }}>
            Detector Baseline Alarms at 13:56 IST
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-dim)', margin: 0 }}>
            Evaluated at the conclusion of the 30-minute baseline window (07:57 – 08:26 UTC).
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
            {['b0', 'b1', 'b2'].map(bKey => {
              const alertList = data.alerts[bKey] || [];
              const hasAlert = alertList.length > 0;
              const al = hasAlert ? alertList[0] : null;
              return (
                <div key={bKey} style={{
                  background: 'var(--bg-primary)',
                  border: hasAlert ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid var(--border-color)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <div style={{ fontWeight: '700', fontSize: '13px' }}>
                      {bKey.toUpperCase()}: {bKey === 'b0' ? 'Threshold Only' : bKey === 'b1' ? 'Persistence + Trend' : 'Engineered Multi-Gate Rules'}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                      {hasAlert ? `Reason: ${al.reason} (${al.node_ids.join(', ')})` : 'No alert triggered'}
                    </div>
                  </div>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: '700',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    background: hasAlert ? 'rgba(239, 68, 68, 0.15)' : 'rgba(52, 211, 153, 0.1)',
                    color: hasAlert ? 'var(--color-critical)' : 'var(--color-healthy)'
                  }}>
                    {hasAlert ? al.level : 'NORMAL'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Agent Decision Card */}
        <div style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-review)', margin: 0 }}>
              Agent Investigation (Muse Spark 1.3)
            </h3>
            <span style={{
              fontSize: '12px',
              fontWeight: '700',
              padding: '3px 10px',
              borderRadius: '6px',
              background: 'rgba(52, 211, 153, 0.15)',
              color: 'var(--color-healthy)',
              border: '1px solid rgba(52, 211, 153, 0.3)'
            }}>
              RECOMMENDATION: {data.agent_decision?.recommendation || 'KEEP'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', background: 'var(--bg-primary)', padding: '10px', borderRadius: '6px' }}>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>HYPOTHESIS</div>
              <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-main)', textTransform: 'uppercase' }}>
                {data.agent_decision?.hypothesis || 'unclear'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>CONFIDENCE</div>
              <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-main)' }}>
                {((data.agent_decision?.confidence || 0) * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>TOOL CALLS</div>
              <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-main)' }}>
                {data.agent_decision?.tool_calls || 6} (6/6 executed)
              </div>
            </div>
          </div>

          <div style={{ background: 'var(--bg-primary)', padding: '10px 12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-dim)', marginBottom: '4px' }}>
              ANALYST BRIEF & DISPOSITION
            </div>
            <p style={{ fontSize: '12px', lineHeight: '1.5', color: 'var(--text-main)', margin: 0 }}>
              "{data.agent_decision?.brief}"
            </p>
          </div>

          <div style={{ background: 'var(--bg-primary)', padding: '10px 12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-dim)', marginBottom: '4px' }}>
              SAFETY GUARD RESULT
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-main)' }}>
                Guard Action: <strong>{data.agent_decision?.guard_action}</strong> ({data.agent_decision?.guard_reason})
              </span>
              <span style={{ fontSize: '11px', color: 'var(--color-healthy)', fontWeight: '600' }}>
                FAIL-CLOSED SAFE
              </span>
            </div>
          </div>

          <div style={{
            fontSize: '11px',
            color: 'var(--text-dim)',
            lineHeight: '1.4',
            borderTop: '1px dashed var(--border-color)',
            paddingTop: '8px'
          }}>
            Note: The agent's neighbour comparison used the first 30 minutes of the session as its reference, which already included the NODE_02 step at 13:38 IST, so its 'neighbour stable' finding is not reliable here.
          </div>
        </div>
      </div>

      {/* 6. Baseline Window Explanation (Step 5 Analysis) */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
          Investigation Finding Analysis: Spatial Neighbor Baseline Explanation
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0, lineHeight: '1.5' }}>
          <strong>Observation:</strong> {data.step5_explanation?.finding}
        </p>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0, lineHeight: '1.5' }}>
          <strong>Physical Cause:</strong> {data.step5_explanation?.cause}
        </p>
        <div style={{
          marginTop: '4px',
          padding: '8px 12px',
          background: 'rgba(56, 189, 248, 0.08)',
          borderLeft: '3px solid var(--color-review)',
          fontSize: '12px',
          color: 'var(--text-main)'
        }}>
          <strong>Verdict:</strong> {data.step5_explanation?.verdict}
        </div>
      </div>
    </div>
  );
}
