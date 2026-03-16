import { motion } from 'framer-motion';

const FLAG_LABELS = {
  low_seed_quality: 'Low Seed Quality',
  coaching_edge: 'Coaching Edge',
  tempo_mismatch: 'Tempo Mismatch',
  recent_form: 'Recent Form',
  three_point_reliance: '3PT Reliance',
  experience_factor: 'Experience Factor',
  fatigue_risk: 'Fatigue Risk',
  historical_seed_upset: 'Historical Seed Upset',
  kenpom_discrepancy: 'KenPom Discrepancy',
  vegas_line_shift: 'Vegas Line Shift',
  momentum: 'Momentum',
  neutral_site: 'Neutral Site',
};

function getFlagLabel(flag) {
  return FLAG_LABELS[flag] ?? flag.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function ScoreBar({ score, max = 5 }) {
  const pct = Math.min(score / max, 1) * 100;
  const color = score >= 3 ? '#ef4444' : score >= 2 ? '#f5a623' : '#94a3b8';
  return (
    <div
      className="relative rounded-full overflow-hidden"
      style={{ height: 4, backgroundColor: 'rgba(255,255,255,0.06)', width: '100%' }}
    >
      <div
        className="absolute left-0 top-0 h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

function AlertCard({ alert, index }) {
  const isHighAlert = alert.upset_score >= 3;
  const flags = alert.triggered_flags || alert.flags || [];

  const borderColor = isHighAlert
    ? 'rgba(239,68,68,0.6)'
    : 'rgba(245,166,35,0.25)';
  const headerColor = isHighAlert ? '#ef4444' : '#f5a623';
  const bgGlow = isHighAlert
    ? 'rgba(239,68,68,0.04)'
    : 'rgba(245,166,35,0.02)';

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      className="rounded-xl p-5 space-y-4"
      style={{
        backgroundColor: `color-mix(in srgb, #151d38 95%, ${bgGlow})`,
        border: `1px solid ${borderColor}`,
        background: `linear-gradient(135deg, #151d38 60%, ${bgGlow} 100%)`,
      }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          {isHighAlert && (
            <div className="flex items-center gap-2 mb-2">
              <motion.span
                className="font-mono text-xs font-bold tracking-widest px-2 py-0.5 rounded"
                style={{
                  color: '#ef4444',
                  backgroundColor: 'rgba(239,68,68,0.12)',
                  border: '1px solid rgba(239,68,68,0.3)',
                }}
                animate={{ opacity: [1, 0.5, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                ⚠ HIGH ALERT
              </motion.span>
            </div>
          )}
          <div className="flex items-center gap-3">
            <span
              className="font-mono text-xs"
              style={{ color: 'rgba(148,163,184,0.6)' }}
            >
              {alert.seed_underdog != null ? `[${alert.seed_underdog}]` : ''}
            </span>
            <span className="font-mono font-bold text-base text-white">
              {alert.underdog ?? alert.team_b ?? '—'}
            </span>
            <span className="font-mono text-xs text-slate-500">def.</span>
            <span className="font-mono text-xs text-slate-500">
              [{alert.seed_favorite ?? alert.seed_a ?? '?'}]
            </span>
            <span className="font-mono text-sm text-slate-400">
              {alert.favorite ?? alert.team_a ?? '—'}
            </span>
          </div>
          {alert.region && (
            <p className="font-mono text-xs text-slate-600 mt-1">
              {alert.region} · {alert.round ?? 'R64'}
            </p>
          )}
        </div>

        {/* Score badge */}
        <div className="flex flex-col items-center shrink-0">
          <span
            className="font-mono font-black text-2xl leading-none"
            style={{ color: headerColor }}
          >
            {typeof alert.upset_score === 'number'
              ? alert.upset_score.toFixed(1)
              : alert.upset_score ?? '—'}
          </span>
          <span className="font-mono text-xs text-slate-600 mt-0.5 tracking-widest">
            SCORE
          </span>
        </div>
      </div>

      {/* Score bar */}
      <ScoreBar score={alert.upset_score} />

      {/* Probabilities */}
      {(alert.ml_prob != null || alert.upset_probability != null) && (
        <div
          className="grid grid-cols-2 gap-px rounded-lg overflow-hidden"
          style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}
        >
          <div
            className="flex flex-col items-center py-2"
            style={{ backgroundColor: '#0f1629' }}
          >
            <span className="font-mono text-xs text-slate-500 uppercase tracking-widest">
              ML Upset Prob
            </span>
            <span
              className="font-mono font-bold text-sm mt-0.5"
              style={{ color: headerColor }}
            >
              {alert.ml_prob != null
                ? `${(alert.ml_prob * 100).toFixed(1)}%`
                : alert.upset_probability != null
                ? `${(alert.upset_probability * 100).toFixed(1)}%`
                : '—'}
            </span>
          </div>
          <div
            className="flex flex-col items-center py-2"
            style={{ backgroundColor: '#0f1629' }}
          >
            <span className="font-mono text-xs text-slate-500 uppercase tracking-widest">
              Historical Rate
            </span>
            <span className="font-mono font-bold text-sm text-slate-300 mt-0.5">
              {alert.historical_rate != null
                ? `${(alert.historical_rate * 100).toFixed(1)}%`
                : '—'}
            </span>
          </div>
        </div>
      )}

      {/* Triggered flags */}
      {flags.length > 0 && (
        <div>
          <p className="font-mono text-xs text-slate-600 uppercase tracking-widest mb-2">
            Triggered Factors
          </p>
          <div className="flex flex-wrap gap-2">
            {flags.map((flag) => (
              <span
                key={flag}
                className="font-mono text-xs px-2 py-0.5 rounded"
                style={{
                  color: isHighAlert ? '#fca5a5' : '#fbbf24',
                  backgroundColor: isHighAlert
                    ? 'rgba(239,68,68,0.08)'
                    : 'rgba(245,166,35,0.08)',
                  border: isHighAlert
                    ? '1px solid rgba(239,68,68,0.2)'
                    : '1px solid rgba(245,166,35,0.15)',
                }}
              >
                {getFlagLabel(flag)}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

export default function UpsetAlerts({ alerts }) {
  if (!alerts || alerts.length === 0) {
    return (
      <section className="px-4 py-8 max-w-5xl mx-auto">
        <div className="flex items-center gap-4 mb-8">
          <div
            className="h-8 w-1 rounded-full"
            style={{ backgroundColor: '#ef4444' }}
          />
          <h2 className="font-mono font-black text-2xl text-white tracking-tight">
            UPSET ALERTS
          </h2>
        </div>
        <div className="text-center py-16 font-mono text-slate-500">
          No upset alerts found.
        </div>
      </section>
    );
  }

  const sorted = [...alerts].sort(
    (a, b) => (b.upset_score ?? 0) - (a.upset_score ?? 0)
  );
  const highCount = sorted.filter((a) => a.upset_score >= 3).length;
  const watchCount = sorted.filter(
    (a) => a.upset_score >= 2 && a.upset_score < 3
  ).length;

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      {/* Section header */}
      <div className="flex items-center gap-4 mb-6">
        <div
          className="h-8 w-1 rounded-full"
          style={{ backgroundColor: '#ef4444' }}
        />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          UPSET ALERTS
        </h2>
        <span
          className="font-mono text-xs px-3 py-1 rounded-full"
          style={{
            color: '#ef4444',
            backgroundColor: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.25)',
          }}
        >
          {sorted.length} ALERTS
        </span>
      </div>

      {/* Summary pills */}
      <div className="flex gap-3 mb-8 flex-wrap">
        <div
          className="flex items-center gap-2 px-4 py-2 rounded-lg"
          style={{
            backgroundColor: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
          }}
        >
          <span className="font-mono font-bold text-sm" style={{ color: '#ef4444' }}>
            {highCount}
          </span>
          <span className="font-mono text-xs text-slate-400">HIGH ALERT (≥3.0)</span>
        </div>
        <div
          className="flex items-center gap-2 px-4 py-2 rounded-lg"
          style={{
            backgroundColor: 'rgba(245,166,35,0.08)',
            border: '1px solid rgba(245,166,35,0.2)',
          }}
        >
          <span className="font-mono font-bold text-sm" style={{ color: '#f5a623' }}>
            {watchCount}
          </span>
          <span className="font-mono text-xs text-slate-400">WATCH (2.0–2.9)</span>
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sorted.map((alert, i) => (
          <AlertCard key={i} alert={alert} index={i} />
        ))}
      </div>
    </section>
  );
}
