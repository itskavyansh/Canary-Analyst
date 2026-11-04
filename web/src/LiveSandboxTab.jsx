import React, { useState, useEffect, useRef } from 'react';
import { SANDBOX_URL } from './sandboxConfig';

export function LiveSandboxTab() {
  const [serverStatus, setServerStatus] = useState('checking'); // 'checking', 'ready', 'waking', 'unavailable'
  const [serverMessage, setServerMessage] = useState('');
  
  // Controls state (defaults must alarm: tilt 25, sudden rise 0, NODE_01)
  const [preset, setPreset] = useState('single_node_move');
  const [node, setNode] = useState('NODE_01');
  const [onsetMinute, setOnsetMinute] = useState(35);
  const [riseMinutes, setRiseMinutes] = useState(0); // 0, 10, 30
  const [tiltDeg, setTiltDeg] = useState(25);
  const [vibrationG, setVibrationG] = useState(0.0);
  const [distanceCm, setDistanceCm] = useState(0.0);
  const [durationMinutes, setDurationMinutes] = useState(90);

  // Run execution and results
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  const [runResult, setRunResult] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobData, setJobData] = useState(null);

  const pollIntervalRef = useRef(null);

  const cleanBaseUrl = (SANDBOX_URL || '').replace(/\/+$/, '');

  // Ping health on mount with waking retry
  useEffect(() => {
    let isMounted = true;
    let elapsed = 0;
    let timerId = null;

    const checkHealth = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);
        const res = await fetch(`${cleanBaseUrl}/api/sandbox/health`, { signal: controller.signal });
        clearTimeout(timeoutId);
        if (res.ok) {
          await res.json();
          if (isMounted) {
            setServerStatus('ready');
            setServerMessage('');
          }
          return true;
        }
      } catch (err) {
        // failed or aborted
      }

      elapsed += 5;
      if (elapsed >= 90) {
        if (isMounted) {
          setServerStatus('unavailable');
          setServerMessage('Sandbox server unavailable, the other tabs use stored replays');
        }
        return false;
      } else {
        if (isMounted) {
          setServerStatus('waking');
          setServerMessage('Waking the sandbox server, this can take up to a minute on the free tier');
        }
        timerId = setTimeout(checkHealth, 5000);
        return false;
      }
    };

    checkHealth();

    return () => {
      isMounted = false;
      if (timerId) clearTimeout(timerId);
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [cleanBaseUrl]);

  const handleRandomise = () => {
    const presets = [
      'single_node_move',
      'common_mode_tilt',
      'vibration_pulse_all_nodes',
      'single_node_spike',
      'silent_sensor_fault'
    ];
    const nodes = ['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'];
    const rises = [0, 10, 30];

    const p = presets[Math.floor(Math.random() * presets.length)];
    const n = nodes[Math.floor(Math.random() * nodes.length)];
    const r = rises[Math.floor(Math.random() * rises.length)];
    const onset = Math.floor(35 + Math.random() * 45); // 35 to 80
    const dur = Math.floor(60 + Math.random() * 61); // 60 to 120
    const tilt = parseFloat((Math.random() * 45).toFixed(1));
    const vib = parseFloat((Math.random() * 5.0).toFixed(2));
    const dist = parseFloat((Math.random() * 20.0).toFixed(1));

    setPreset(p);
    setNode(n);
    setRiseMinutes(r);
    setOnsetMinute(onset);
    setDurationMinutes(dur);
    setTiltDeg(tilt);
    setVibrationG(vib);
    setDistanceCm(dist);
  };

  const handleRun = async () => {
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    setJobStatus(null);
    setJobData(null);
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    const payload = {
      preset,
      node,
      onset_minute: Number(onsetMinute),
      rise_minutes: Number(riseMinutes),
      tilt_deg: Number(tiltDeg),
      vibration_g: Number(vibrationG),
      distance_cm: Number(distanceCm),
      duration_minutes: Number(durationMinutes)
    };

    try {
      const res = await fetch(`${cleanBaseUrl}/api/sandbox/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.status === 429) {
        const errJson = await res.json().catch(() => ({}));
        setIsRunning(false);
        setRunError(errJson.error || 'Rate limit or concurrency limit exceeded. Please wait a moment.');
        return;
      }

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        setIsRunning(false);
        setRunError(errJson.error || `Server returned error status ${res.status}`);
        return;
      }

      const data = await res.json();
      setRunResult(data);

      if (data.job_id) {
        setJobStatus('queued');
        const jobId = data.job_id;

        // Poll /api/sandbox/job/{id} every 2 seconds
        pollIntervalRef.current = setInterval(async () => {
          try {
            const jRes = await fetch(`${cleanBaseUrl}/api/sandbox/job/${jobId}`);
            if (jRes.status === 429) {
              setJobStatus('error');
              setRunError('Too many requests while polling. Please try again.');
              clearInterval(pollIntervalRef.current);
              setIsRunning(false);
              return;
            }
            if (!jRes.ok) {
              setJobStatus('error');
              setRunError(`Error fetching job status (HTTP ${jRes.status})`);
              clearInterval(pollIntervalRef.current);
              setIsRunning(false);
              return;
            }
            const jData = await jRes.json();
            setJobStatus(jData.status);
            setJobData(jData);

            if (jData.status === 'done' || jData.status === 'error' || jData.status === 'unavailable' || jData.status === 'daily budget reached') {
              clearInterval(pollIntervalRef.current);
              setIsRunning(false);
            }
          } catch (pollErr) {
            setJobStatus('error');
            setRunError(`Network error while polling agent job: ${pollErr.message}`);
            clearInterval(pollIntervalRef.current);
            setIsRunning(false);
          }
        }, 2000);
      } else {
        setIsRunning(false);
      }
    } catch (err) {
      setIsRunning(false);
      setRunError(`Failed to connect to sandbox backend: ${err.message}`);
    }
  };

  // Node colors for charts
  const nodeColors = {
    NODE_01: 'var(--node1)',
    NODE_02: 'var(--node2)',
    NODE_03: 'var(--node3)',
    NODE_04: 'var(--node4)',
  };

  const svgWidth = 900;
  const svgHeight = 110;
  const padLeft = 45;
  const padRight = 15;
  const padTop = 15;
  const padBottom = 20;
  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  const seriesChannels = [
    {
      id: 'tilt_x',
      title: 'Tilt X (deg) (Warning 15 deg, Critical 22.5 deg)',
      unit: 'deg',
      minVal: -10,
      maxVal: 45,
      thresholds: [
        { val: 15, label: 'Warn 15 deg', color: 'var(--color-warning)' },
        { val: 22.5, label: 'Crit 22.5 deg', color: 'var(--color-critical)' }
      ]
    },
    {
      id: 'vibration',
      title: 'Vibration Peak (g) (Warning 1.0 g, Critical 1.5 g)',
      unit: 'g',
      minVal: 0,
      maxVal: 5,
      thresholds: [
        { val: 1.0, label: 'Warn 1.0 g', color: 'var(--color-warning)' },
        { val: 1.5, label: 'Crit 1.5 g', color: 'var(--color-critical)' }
      ]
    },
    {
      id: 'distance',
      title: 'Ultrasonic Distance (cm) (Warning delta 2.0 cm, Critical 3.0 cm)',
      unit: 'cm',
      minVal: 10,
      maxVal: 40,
      thresholds: []
    }
  ];

  const seriesData = runResult?.series || null;
  const totalMins = runResult?.inputs?.duration_minutes || durationMinutes || 90;
  const baselineX = padLeft + (Math.min(30, totalMins) / Math.max(1, totalMins)) * chartW;
  const b2Alerts = runResult?.b2_alerts || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* 7. Fixed Text Box */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '14px 18px',
        fontSize: '13px',
        lineHeight: '1.6',
        color: 'var(--text-main)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{ fontSize: '16px' }}>🔬</span>
          <strong style={{ fontSize: '14px', color: 'var(--color-review)' }}>Interactive Pipeline Sandbox</strong>
        </div>
        Live sandbox. Each run builds a new synthetic scenario from your inputs, runs the frozen detector, and, if it alarms, calls Muse Spark 1.3 live with the same frozen prompt, tools and guard as the benchmark. This is a single run on synthetic data, not a benchmark result. Thresholds are demonstration values. The system only recommends; humans decide on evacuation.
      </div>

      {/* 4. Health and Server Status Banner */}
      {serverStatus === 'waking' && (
        <div style={{
          background: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '13px',
          color: '#fbbf24'
        }}>
          <span>⏳</span>
          <span>{serverMessage}</span>
        </div>
      )}

      {serverStatus === 'unavailable' && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '13px',
          color: '#f87171'
        }}>
          <span>❌</span>
          <span>{serverMessage}</span>
        </div>
      )}

      {/* 3. Scenario Design Controls Card */}
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '18px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
            Scenario Configuration & Sensor Inputs
          </h3>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={handleRandomise}
              disabled={isRunning}
              style={{
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '6px 14px',
                fontSize: '12px',
                fontWeight: '600',
                cursor: isRunning ? 'not-allowed' : 'pointer'
              }}
            >
              🎲 Randomise
            </button>
            <button
              onClick={handleRun}
              disabled={isRunning || serverStatus === 'waking' || serverStatus === 'unavailable'}
              style={{
                background: isRunning ? 'var(--bg-card)' : 'var(--color-review)',
                color: isRunning ? 'var(--text-dim)' : '#fff',
                border: 'none',
                borderRadius: '6px',
                padding: '6px 18px',
                fontSize: '13px',
                fontWeight: '700',
                cursor: (isRunning || serverStatus === 'waking' || serverStatus === 'unavailable') ? 'not-allowed' : 'pointer'
              }}
            >
              {isRunning ? '⏳ Running...' : '▶ Run Scenario'}
            </button>
          </div>
        </div>

        {/* Inputs Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
          {/* Preset Picker */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>
              Scenario Preset
            </label>
            <select
              value={preset}
              onChange={e => setPreset(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 10px',
                background: 'var(--bg-primary)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            >
              <option value="single_node_move">Single node move (isolated ground shear)</option>
              <option value="common_mode_tilt">Common mode tilt (rain-like drift across all nodes)</option>
              <option value="vibration_pulse_all_nodes">Vibration pulse (blast-like shockwave)</option>
              <option value="single_node_spike">Single node spike (machinery-like vibration)</option>
              <option value="silent_sensor_fault">Silent sensor fault (stuck rail values, flags ok)</option>
              <option value="random">Random (procedural preset & parameters)</option>
            </select>
          </div>

          {/* Node Picker */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>
              Target Node
            </label>
            <select
              value={node}
              onChange={e => setNode(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 10px',
                background: 'var(--bg-primary)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            >
              <option value="NODE_01">NODE_01 (0, 0 m)</option>
              <option value="NODE_02">NODE_02 (20, 0 m)</option>
              <option value="NODE_03">NODE_03 (20, 20 m)</option>
              <option value="NODE_04">NODE_04 (0, 20 m)</option>
            </select>
          </div>

          {/* Onset Minute */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-dim)', textTransform: 'uppercase' }}>Onset Minute</span>
              <span style={{ color: 'var(--text-main)', fontFamily: 'monospace' }}>T+{onsetMinute}m</span>
            </div>
            <input
              type="range"
              min="35"
              max="80"
              value={onsetMinute}
              onChange={e => setOnsetMinute(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-review)' }}
            />
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Range: 35 to 80 min (after 30m baseline)</div>
          </div>

          {/* Rise Duration */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>
              Rise Profile
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              {[
                { val: 0, label: 'Sudden (0m)' },
                { val: 10, label: '10 min' },
                { val: 30, label: '30 min' }
              ].map(opt => (
                <button
                  key={opt.val}
                  type="button"
                  onClick={() => setRiseMinutes(opt.val)}
                  style={{
                    flex: 1,
                    padding: '6px 8px',
                    fontSize: '11px',
                    fontWeight: '600',
                    background: riseMinutes === opt.val ? 'var(--border-highlight)' : 'var(--bg-primary)',
                    color: riseMinutes === opt.val ? '#fff' : 'var(--text-muted)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '5px'
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tilt Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-dim)', textTransform: 'uppercase' }}>Tilt Magnitude</span>
              <span style={{ color: 'var(--text-main)', fontFamily: 'monospace', fontWeight: '700' }}>{tiltDeg}°</span>
            </div>
            <input
              type="range"
              min="0"
              max="45"
              step="0.5"
              value={tiltDeg}
              onChange={e => setTiltDeg(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-review)' }}
            />
            <div style={{ fontSize: '11px', color: 'var(--color-warning)', marginTop: '2px' }}>
              Demonstration threshold: Warning 15°, Critical 22.5°
            </div>
          </div>

          {/* Vibration Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-dim)', textTransform: 'uppercase' }}>Peak Vibration</span>
              <span style={{ color: 'var(--text-main)', fontFamily: 'monospace', fontWeight: '700' }}>{vibrationG} g</span>
            </div>
            <input
              type="range"
              min="0"
              max="5"
              step="0.1"
              value={vibrationG}
              onChange={e => setVibrationG(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-review)' }}
            />
            <div style={{ fontSize: '11px', color: 'var(--color-warning)', marginTop: '2px' }}>
              Demonstration threshold: Warning 1.0 g, Critical 1.5 g
            </div>
          </div>

          {/* Distance Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-dim)', textTransform: 'uppercase' }}>Distance Step</span>
              <span style={{ color: 'var(--text-main)', fontFamily: 'monospace', fontWeight: '700' }}>{distanceCm} cm</span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              step="0.5"
              value={distanceCm}
              onChange={e => setDistanceCm(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-review)' }}
            />
            <div style={{ fontSize: '11px', color: 'var(--color-warning)', marginTop: '2px' }}>
              Demonstration threshold: Warning delta 2.0 cm, Critical 3.0 cm
            </div>
          </div>

          {/* Duration Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-dim)', textTransform: 'uppercase' }}>Scenario Duration</span>
              <span style={{ color: 'var(--text-main)', fontFamily: 'monospace', fontWeight: '700' }}>{durationMinutes} min</span>
            </div>
            <input
              type="range"
              min="60"
              max="120"
              step="5"
              value={durationMinutes}
              onChange={e => setDurationMinutes(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--color-review)' }}
            />
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>Range: 60 to 120 minutes (default 90)</div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {runError && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          color: '#f87171',
          fontSize: '13px'
        }}>
          <strong>Execution Notice:</strong> {runError}
        </div>
      )}

      {/* 5. Telemetry Time Series Charts */}
      {seriesData && (
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
              <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
                Synthesized Telemetry Series (Downsampled to 120 Points)
              </h3>
              <p style={{ fontSize: '11px', color: 'var(--text-dim)', margin: '2px 0 0 0' }}>
                Shaded area denotes 30-minute detector baseline window. Vertical markers indicate B2.1 alerts.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '12px', fontSize: '11px' }}>
              {['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'].map(nid => (
                <div key={nid} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: nodeColors[nid] }}></span>
                  <span style={{ color: 'var(--text-muted)' }}>{nid}</span>
                </div>
              ))}
            </div>
          </div>

          {seriesChannels.map(ch => {
            const nodes = ['NODE_01', 'NODE_02', 'NODE_03', 'NODE_04'];
            const paths = {};

            nodes.forEach(nid => {
              const pts = (seriesData[nid] && seriesData[nid][ch.id]) || [];
              let dStr = '';
              pts.forEach((p, idx) => {
                const x = padLeft + (idx / Math.max(1, pts.length - 1)) * chartW;
                const val = p.value;
                const clamped = Math.max(ch.minVal, Math.min(val, ch.maxVal));
                const y = padTop + chartH - ((clamped - ch.minVal) / (ch.maxVal - ch.minVal)) * chartH;
                if (idx === 0) dStr += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
                else dStr += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
              });
              paths[nid] = dStr;
            });

            return (
              <div key={ch.id} style={{ background: 'var(--bg-primary)', borderRadius: '6px', padding: '10px 12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  <span>{ch.title}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Range: [{ch.minVal} to {ch.maxVal} {ch.unit}]</span>
                </div>
                <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} preserveAspectRatio="none" style={{ width: '100%', height: '100px', display: 'block' }}>
                  {/* Baseline 30-min window shading */}
                  <rect
                    x={padLeft}
                    y={padTop}
                    width={Math.max(0, baselineX - padLeft)}
                    height={chartH}
                    fill="rgba(56, 189, 248, 0.05)"
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

                  {/* Horizontal grid */}
                  <line x1={padLeft} y1={padTop} x2={padLeft + chartW} y2={padTop} stroke="var(--border-color)" strokeWidth="1" />
                  <line x1={padLeft} y1={padTop + chartH / 2} x2={padLeft + chartW} y2={padTop + chartH / 2} stroke="var(--border-color)" strokeDasharray="3,3" strokeWidth="1" />
                  <line x1={padLeft} y1={padTop + chartH} x2={padLeft + chartW} y2={padTop + chartH} stroke="var(--border-color)" strokeWidth="1" />

                  {/* Threshold lines */}
                  {ch.thresholds.map((t, idx) => {
                    const ty = padTop + chartH - ((t.val - ch.minVal) / (ch.maxVal - ch.minVal)) * chartH;
                    return (
                      <g key={idx}>
                        <line x1={padLeft} y1={ty} x2={padLeft + chartW} y2={ty} stroke={t.color} strokeDasharray="4,2" strokeWidth="1" />
                        <text x={padLeft + 4} y={ty - 3} fill={t.color} fontSize="9" fontFamily="monospace">{t.label}</text>
                      </g>
                    );
                  })}

                  {/* Alert vertical markers */}
                  {b2Alerts.map((a, aIdx) => {
                    const aDt = new Date(a.time);
                    const startDt = new Date(runResult.series?.NODE_01?.tilt_x?.[0]?.timestamp || a.time);
                    const diffMins = Math.max(0, (aDt - startDt) / (1000 * 60));
                    const ax = padLeft + (diffMins / Math.max(1, totalMins)) * chartW;
                    return (
                      <line
                        key={aIdx}
                        x1={ax}
                        y1={padTop}
                        x2={ax}
                        y2={padTop + chartH}
                        stroke={a.level === 'CRITICAL' ? 'var(--color-critical)' : 'var(--color-warning)'}
                        strokeWidth="2"
                      />
                    );
                  })}

                  {/* Curves */}
                  {nodes.map(nid => (
                    <path
                      key={nid}
                      d={paths[nid] || ''}
                      fill="none"
                      stroke={nodeColors[nid]}
                      strokeWidth="2"
                      strokeLinejoin="round"
                    />
                  ))}
                </svg>
              </div>
            );
          })}
        </div>
      )}

      {/* 5. B2.1 Alert List or No Alert Card */}
      {runResult && (
        <div style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '16px'
        }}>
          <h3 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-main)', marginBottom: '8px' }}>
            Detector Outcome (Baseline B2.1)
          </h3>
          {b2Alerts.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--color-warning)', fontWeight: '600' }}>
                {b2Alerts.length} alert event(s) raised by deterministic baseline:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px' }}>
                {b2Alerts.map((a, idx) => (
                  <div key={idx} style={{
                    background: 'var(--bg-primary)',
                    borderRadius: '6px',
                    padding: '10px',
                    border: a.level === 'CRITICAL' ? '1px solid var(--color-critical)' : '1px solid var(--color-warning)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: '700',
                        color: a.level === 'CRITICAL' ? 'var(--color-critical)' : 'var(--color-warning)'
                      }}>
                        {a.level}
                      </span>
                      <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-dim)' }}>
                        {a.time}
                      </span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-main)', fontWeight: '600' }}>
                      Nodes: {a.node_ids.join(', ')}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      Reason: {a.reason}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{
              background: 'rgba(52, 211, 153, 0.08)',
              border: '1px solid rgba(52, 211, 153, 0.25)',
              borderRadius: '6px',
              padding: '12px 14px',
              color: 'var(--color-healthy)',
              fontSize: '13px'
            }}>
              No alert. This input stays below the demonstration thresholds or is not sustained, so the detector stays quiet and the agent is not called.
            </div>
          )}
        </div>
      )}

      {/* 6. Agent Investigation Progress & Result Card */}
      {isRunning && runResult?.job_id && (
        <div style={{
          background: 'rgba(56, 189, 248, 0.08)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: '8px',
          padding: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ fontSize: '20px' }}>🔍</span>
          <div>
            <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--color-review)' }}>
              The agent is investigating, usually 15 to 35 seconds
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
              Dispatching diagnostic tools and evaluating deterministic Safety Guard gates...
            </div>
          </div>
        </div>
      )}

      {jobData && jobData.candidates && jobData.candidates.length > 0 && (
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
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
              Autonomous Agent Investigation (Muse Spark 1.3)
            </h3>
            <div style={{ display: 'flex', gap: '10px', fontSize: '11px' }}>
              <span style={{ background: 'var(--bg-card)', padding: '3px 8px', borderRadius: '4px', color: 'var(--text-muted)' }}>
                Latency: {jobData.seconds ? Number(jobData.seconds).toFixed(1) : '0.0'}s
              </span>
              <span style={{ background: 'var(--bg-card)', padding: '3px 8px', borderRadius: '4px', color: 'var(--color-healthy)' }}>
                Cost: ${jobData.cost ? Number(jobData.cost).toFixed(4) : '0.0000'}
              </span>
            </div>
          </div>

          {jobData.candidates.map((cand, idx) => {
            const isAllEvidenceValid = cand.evidence_validity
              ? Object.values(cand.evidence_validity).every(v => v === true)
              : true;

            return (
              <div key={idx} style={{
                background: 'var(--bg-primary)',
                borderRadius: '6px',
                padding: '14px',
                border: '1px solid var(--border-color)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}>
                {/* Header Metrics */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Recommendation</div>
                    <div style={{
                      fontSize: '14px',
                      fontWeight: '800',
                      color: cand.recommendation === 'DOWNGRADE' ? 'var(--color-review)' : 'var(--color-critical)'
                    }}>
                      {cand.recommendation}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Hypothesis</div>
                    <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-main)' }}>
                      {cand.hypothesis}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Confidence</div>
                    <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-main)' }}>
                      {(Number(cand.confidence || 0) * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Guard Action</div>
                    <div style={{
                      fontSize: '13px',
                      fontWeight: '700',
                      color: cand.guard_action === 'DOWNGRADE' ? 'var(--color-review)' : 'var(--color-warning)'
                    }}>
                      {cand.guard_action}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Review Hold</div>
                    <div style={{ fontSize: '13px', fontWeight: '700', color: cand.hold_created ? 'var(--color-review)' : 'var(--text-muted)' }}>
                      {cand.hold_created ? 'Created (15m)' : 'Not created'}
                    </div>
                  </div>
                </div>

                {/* Brief */}
                <div style={{ background: 'var(--bg-secondary)', padding: '10px 12px', borderRadius: '6px' }}>
                  <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-dim)', marginBottom: '4px' }}>
                    GEOTECHNICAL BRIEF
                  </div>
                  <p style={{ fontSize: '13px', lineHeight: '1.5', color: 'var(--text-main)', margin: 0 }}>
                    &quot;{cand.brief}&quot;
                  </p>
                </div>

                {/* Findings */}
                {cand.findings && cand.findings.length > 0 && (
                  <div>
                    <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-dim)', marginBottom: '4px' }}>
                      KEY EVIDENCE FINDINGS
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                      {cand.findings.map((f, fIdx) => (
                        <li key={fIdx}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Tools & Evidence Integrity */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', fontSize: '11px', borderTop: '1px dashed var(--border-color)', paddingTop: '8px' }}>
                  <div style={{ color: 'var(--text-dim)' }}>
                    Tools executed: <strong>{(cand.tool_names || []).join(', ') || 'none'}</strong>
                  </div>
                  <div style={{ color: isAllEvidenceValid ? 'var(--color-healthy)' : 'var(--color-critical)', fontWeight: '600' }}>
                    Evidence IDs: {cand.cited_evidence_ids?.length || 0} cited ({isAllEvidenceValid ? 'all valid tool outputs' : 'contains unverified IDs'})
                  </div>
                </div>

                {/* Guard Failed Conditions if any */}
                {cand.failed_conditions && cand.failed_conditions.length > 0 && (
                  <div style={{ background: 'rgba(239, 68, 68, 0.08)', borderRadius: '4px', padding: '6px 10px', fontSize: '11px', color: '#f87171' }}>
                    <strong>Guard Failed Conditions:</strong> {cand.failed_conditions.join('; ')}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
