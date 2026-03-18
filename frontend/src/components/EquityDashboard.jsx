import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Label,
} from 'recharts';

function equityColor(equityScore) {
  if (equityScore == null) return '#475569';
  if (equityScore >= 1.5) return '#f5a623';
  if (equityScore >= 1.1) return '#f59e0b';
  if (equityScore >= 0.9) return '#22d3ee';
  if (equityScore >= 0.6) return '#64748b';
  return '#334155';
}

function equityOpacity(equityScore) {
  if (equityScore == null) return 0.3;
  return Math.min(0.4 + Math.abs(equityScore - 1) * 0.6, 1.0);
}

function CustomDot(props) {
  const { cx, cy, payload } = props;
  const size = payload.seed <= 4 ? 7 : payload.seed <= 8 ? 6 : 5;
  const color = equityColor(payload.equity_score);
  const opacity = equityOpacity(payload.equity_score);
  return (
    <circle
      cx={cx}
      cy={cy}
      r={size}
      fill={color}
      fillOpacity={opacity}
      stroke={color}
      strokeOpacity={opacity + 0.2}
      strokeWidth={1}
    />
  );
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  const equity = d.equity_score;
  const equityLabel =
    equity == null
      ? '—'
      : equity >= 1.5
      ? 'HIGH VALUE'
      : equity >= 1.1
      ? 'SLIGHT EDGE'
      : equity >= 0.9
      ? 'FAIR'
      : 'OVERVALUED';

  return (
    <div
      className="rounded-lg p-3 font-mono text-xs space-y-1.5"
      style={{
        backgroundColor: '#0f1629',
        border: '1px solid rgba(245,166,35,0.3)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className="font-bold text-sm"
          style={{ color: equityColor(equity) }}
        >
          [{d.seed}] {d.team}
        </span>
      </div>
      <div className="flex justify-between gap-6">
        <span className="text-slate-500">True Win Prob</span>
        <span className="text-white font-bold">
          {d.true_win_prob != null ? `${(d.true_win_prob * 100).toFixed(1)}%` : '—'}
        </span>
      </div>
      <div className="flex justify-between gap-6">
        <span className="text-slate-500">Public Pick %</span>
        <span className="text-white font-bold">
          {d.public_pick_pct != null
            ? `${(d.public_pick_pct * 100).toFixed(1)}%`
            : '—'}
        </span>
      </div>
      <div className="flex justify-between gap-6">
        <span className="text-slate-500">Equity Score</span>
        <span
          className="font-bold"
          style={{ color: equityColor(equity) }}
        >
          {equity != null ? equity.toFixed(2) : '—'}x
        </span>
      </div>
      <div className="flex justify-between gap-6">
        <span className="text-slate-500">Signal</span>
        <span
          className="font-bold"
          style={{ color: equityColor(equity) }}
        >
          {equityLabel}
        </span>
      </div>
    </div>
  );
}

function EquityLegend() {
  const items = [
    { color: '#f5a623', label: 'High Value (≥1.5x)' },
    { color: '#f59e0b', label: 'Slight Edge (1.1–1.5x)' },
    { color: '#22d3ee', label: 'Fair (0.9–1.1x)' },
    { color: '#64748b', label: 'Slight Overvalue (0.6–0.9x)' },
    { color: '#334155', label: 'Avoid (<0.6x)' },
  ];
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4">
      {items.map(({ color, label }) => (
        <div key={label} className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: color, opacity: 0.8 }}
          />
          <span className="font-mono text-xs text-slate-400">{label}</span>
        </div>
      ))}
    </div>
  );
}

export default function EquityDashboard({ picks }) {
  // Filter to R64 picks that have equity data enriched by the backend
  const r64 = (picks ?? []).filter(
    (p) =>
      p.round === 64 &&
      (p.true_win_prob_a != null || p.public_pick_pct_a != null)
  );

  // Build one data point per team per game
  const points = [];
  for (const p of r64) {
    if (p.team_a && p.true_win_prob_a != null) {
      points.push({
        team: p.team_a,
        seed: p.seed_a,
        true_win_prob: p.true_win_prob_a,
        public_pick_pct: p.public_pick_pct_a,
        equity_score: p.equity_score_a,
      });
    }
    if (p.team_b && p.true_win_prob_b != null) {
      points.push({
        team: p.team_b,
        seed: p.seed_b,
        true_win_prob: p.true_win_prob_b,
        public_pick_pct: p.public_pick_pct_b,
        equity_score: p.equity_score_b,
      });
    }
  }

  const hasData = points.length > 0;

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      {/* Section header */}
      <div className="flex items-center gap-4 mb-6">
        <div
          className="h-8 w-1 rounded-full"
          style={{ backgroundColor: '#22d3ee' }}
        />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          POOL EQUITY MAP
        </h2>
        <span
          className="font-mono text-xs px-3 py-1 rounded-full"
          style={{
            color: '#94a3b8',
            backgroundColor: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          R64 ONLY
        </span>
      </div>

      <p className="font-mono text-xs text-slate-500 mb-6 leading-relaxed">
        Teams above the diagonal are undervalued by the public — picking them generates
        positive equity in large pools. Gold dots = highest-value contrarian picks.
      </p>

      <div
        className="rounded-xl p-6"
        style={{
          backgroundColor: '#151d38',
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        {!hasData ? (
          <div className="flex items-center justify-center h-64 font-mono text-slate-500 text-sm">
            No R64 equity data with required fields (true_win_prob, public_pick_pct).
            <br />
            Ensure the simulation result includes these fields.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <ScatterChart margin={{ top: 20, right: 30, bottom: 40, left: 40 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical
                horizontal
              />
              <XAxis
                type="number"
                dataKey="true_win_prob"
                domain={[0, 1]}
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
                tick={{ fill: '#64748b', fontFamily: 'monospace', fontSize: 11 }}
                tickLine={{ stroke: '#334155' }}
                axisLine={{ stroke: '#334155' }}
              >
                <Label
                  value="True Win Probability (ML Model)"
                  position="insideBottom"
                  offset={-20}
                  style={{ fill: '#64748b', fontFamily: 'monospace', fontSize: 11 }}
                />
              </XAxis>
              <YAxis
                type="number"
                dataKey="public_pick_pct"
                domain={[0, 1]}
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
                tick={{ fill: '#64748b', fontFamily: 'monospace', fontSize: 11 }}
                tickLine={{ stroke: '#334155' }}
                axisLine={{ stroke: '#334155' }}
              >
                <Label
                  value="Public Pick %"
                  angle={-90}
                  position="insideLeft"
                  offset={10}
                  style={{ fill: '#64748b', fontFamily: 'monospace', fontSize: 11 }}
                />
              </YAxis>
              {/* Diagonal reference line: efficient market (public = true prob) */}
              <ReferenceLine
                segment={[
                  { x: 0, y: 0 },
                  { x: 1, y: 1 },
                ]}
                stroke="rgba(245,166,35,0.15)"
                strokeDasharray="6 4"
                label={{
                  value: 'Fair Value',
                  position: 'insideTopLeft',
                  style: {
                    fill: 'rgba(245,166,35,0.3)',
                    fontFamily: 'monospace',
                    fontSize: 10,
                  },
                }}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(245,166,35,0.2)' }} />
              <Scatter
                data={points}
                shape={<CustomDot />}
              />
            </ScatterChart>
          </ResponsiveContainer>
        )}
        <EquityLegend />
      </div>
    </section>
  );
}
