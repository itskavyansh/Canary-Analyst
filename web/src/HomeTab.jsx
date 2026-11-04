import React from 'react';

export function HomeTab({ setActiveTab }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', maxWidth: '1000px', margin: '0 auto', padding: '8px 0 24px 0' }}>
      {/* a. Hero */}
      <section style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: '36px 32px',
        display: 'flex',
        flexDirection: 'column',
        gap: '18px'
      }}>
        <h1 style={{
          fontSize: '28px',
          fontWeight: '800',
          letterSpacing: '-0.5px',
          color: 'var(--text-main)',
          lineHeight: '1.25',
          margin: 0
        }}>
          An AI analyst for ground-subsidence early warning
        </h1>
        <p style={{
          fontSize: '15px',
          lineHeight: '1.65',
          color: 'var(--text-muted)',
          margin: 0
        }}>
          Underground mines can collapse during mining and even years after mining stops. Surface sensors watch for ground movement, but alerts can also come from rain, nearby blasts or faulty sensors, and too many false alarms teach people to ignore the system. Canary Analyst investigates each alert with Muse Spark 1.3 and lets a deterministic safety guard decide what the AI is allowed to change.
        </p>
        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', marginTop: '6px' }}>
          <button
            onClick={() => setActiveTab('sandbox')}
            style={{
              background: 'var(--color-review)',
              color: '#0b1320',
              fontWeight: '700',
              fontSize: '14px',
              padding: '10px 20px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer'
            }}
          >
            Try the Live Sandbox
          </button>
          <button
            onClick={() => setActiveTab('results')}
            style={{
              background: 'var(--bg-card)',
              color: 'var(--text-main)',
              fontWeight: '600',
              fontSize: '14px',
              padding: '10px 20px',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              cursor: 'pointer'
            }}
          >
            See the results
          </button>
        </div>
      </section>

      {/* b. How it works */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
          How it works
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
          {/* Card 1 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
              1. Detect
            </h3>
            <p style={{ fontSize: '13px', lineHeight: '1.55', color: 'var(--text-muted)', margin: 0 }}>
              A frozen rules engine watches four sensor nodes and flags candidate anomalies.
            </p>
          </div>

          {/* Card 2 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-review)', margin: 0 }}>
              2. Investigate
            </h3>
            <p style={{ fontSize: '13px', lineHeight: '1.55', color: 'var(--text-muted)', margin: 0 }}>
              Muse Spark 1.3 calls five tools (neighbour comparison, node history, blast schedule, sensor health, time to threshold) and recommends KEEP or DOWNGRADE.
            </p>
          </div>

          {/* Card 3 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--color-healthy)', margin: 0 }}>
              3. Verify
            </h3>
            <p style={{ fontSize: '13px', lineHeight: '1.55', color: 'var(--text-muted)', margin: 0 }}>
              A deterministic guard can veto any downgrade. Approved downgrades become 15 minute review holds. The system only recommends; humans decide on evacuation.
            </p>
          </div>
        </div>
      </section>

      {/* c. Results at a glance */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
          Results at a glance
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          {/* Tile 1 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
            <div style={{ fontSize: '22px', fontWeight: '800', color: 'var(--color-healthy)' }}>
              24 to 16 of 300
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              false-alarm scenarios (8.0% to 5.3%)
            </div>
          </div>

          {/* Tile 2 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
            <div style={{ fontSize: '22px', fontWeight: '800', color: 'var(--text-main)' }}>
              86 of 86
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              simulated hazards detected
            </div>
          </div>

          {/* Tile 3 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
            <div style={{ fontSize: '22px', fontWeight: '800', color: 'var(--color-review)' }}>
              0
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              hazards ever held by the guard
            </div>
          </div>

          {/* Tile 4 */}
          <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px'
          }}>
            <div style={{ fontSize: '22px', fontWeight: '800', color: 'var(--color-healthy)' }}>
              714 of 714
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              cited evidence IDs matched real tool outputs
            </div>
          </div>
        </div>

        <p style={{ fontSize: '12px', color: 'var(--text-dim)', margin: '4px 0 0 0' }}>
          Held-out test of 300 simulated scenarios, run once after freezing. Simulated data, not real mine data.
        </p>
      </section>

      {/* d. Where this comes from */}
      <section style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        <h2 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-main)', margin: 0 }}>
          Where this comes from
        </h2>
        <p style={{ fontSize: '13px', lineHeight: '1.55', color: 'var(--text-muted)', margin: 0 }}>
          Built on the sensor concept of ProjectCanary, an earlier hardware project. The analyst, detector, guard, benchmark and this demo were built during the Meta Global AI Developer Hackathon.
        </p>
      </section>

      {/* e. Limits */}
      <section style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        <h2 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--color-warning)', margin: 0 }}>
          Limits
        </h2>
        <p style={{ fontSize: '13px', lineHeight: '1.55', color: 'var(--text-muted)', margin: 0 }}>
          12 of 43 silent sensor faults still alarm. Results are on simulated data. Thresholds are demonstration values.
        </p>
      </section>
    </div>
  );
}

