import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const FLAG_INFO = {
  rank_within_15: {
    label: 'KenPom Close',
    description: 'KenPom rankings are within 15 spots — the underdog is much closer in quality than the seeding suggests.',
  },
  tempo_mismatch_8: {
    label: 'Tempo Mismatch',
    description: 'Teams differ by 8+ possessions per game in tempo. Stylistic mismatches can neutralize a favorite\'s strengths and create chaos.',
  },
  favorite_fading: {
    label: 'Favorite Fading',
    description: 'The favorite has a high positive Luck rating (>0.04), meaning they overperformed during the season and are likely to regress toward their true level.',
  },
  dog_coach_above_avg: {
    label: 'Coaching Edge',
    description: 'The underdog\'s coach has an above-average tournament PAKE (Performance Against KenPom Expectations), indicating they consistently outperform expectations in March.',
  },
  dog_luck_negative: {
    label: 'Underdog Due',
    description: 'The underdog has a negative Luck rating, meaning they underperformed during the season relative to their true talent. They\'re due for positive regression.',
  },
  style_clash_3pt: {
    label: '3PT Style Clash',
    description: 'The underdog has a top-30 defensive rating AND the favorite has a top-30 offensive rating — a high-stakes style clash where elite defense can neutralize elite offense.',
  },
  hist_upset_rate_30: {
    label: 'Historical Upset',
    description: 'This exact seed matchup has been upset more than 30% of the time historically in this round (e.g., 5 vs 12 seeds upset ~35% of the time in R64).',
  },
  elo_close: {
    label: 'AdjEM Close',
    description: 'The Adjusted Efficiency Margin gap between teams is less than 8 points — statistically a toss-up game where the underdog has a real shot.',
  },
  fav_soft_losses: {
    label: 'Soft Favorite',
    description: 'The favorite\'s Wins Above Bubble (WAB) rank is worse than 20th, meaning their resume includes soft wins against weaker competition.',
  },
  vegas_close_line: {
    label: 'Vegas Close Line',
    description: 'Vegas has the spread at 5.5 points or less — the betting market sees this as a competitive game.',
  },
  vegas_upset_likely: {
    label: 'Vegas Upset Signal',
    description: 'Vegas implied probability gives the underdog a greater than 25% chance of winning outright.',
  },
};

const FLAG_LABELS = Object.fromEntries(
  Object.entries(FLAG_INFO).map(([k, v]) => [k, v.label])
);

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
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            {/* Round badge */}
            <span className="font-mono text-xs px-2 py-0.5 rounded"
              style={{
                color: '#94a3b8',
                backgroundColor: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
              }}>
              {alert.round_name ?? `R${alert.round ?? 64}`}
            </span>
            {isHighAlert && (
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
            )}
            {alert.is_projected && (
              <span className="font-mono text-xs text-slate-600" title="Based on projected matchup — actual opponent may differ">
                PROJECTED
              </span>
            )}
          </div>
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

function TriggerLegend() {
  const [open, setOpen] = useState(true);
  const entries = Object.entries(FLAG_INFO);
  const baseEntries = entries.filter(([k]) => !k.startsWith('vegas_'));
  const vegasEntries = entries.filter(([k]) => k.startsWith('vegas_'));

  return (
    <div className="mt-8">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 font-mono text-xs tracking-widest uppercase transition-colors"
        style={{ color: open ? '#ef4444' : '#475569' }}
      >
        <span
          className="inline-flex items-center justify-center w-5 h-5 rounded-md text-xs"
          style={{
            backgroundColor: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          {open ? '−' : '?'}
        </span>
        What do these triggers mean?
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div
              className="mt-4 rounded-xl p-6 space-y-5"
              style={{
                backgroundColor: '#0f1629',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <div className="space-y-1 mb-4">
                <p className="font-mono text-xs text-slate-400 leading-relaxed">
                  Each game is checked against up to 11 upset conditions. The more triggers that fire, the higher the upset score.
                  Games with 3+ triggers are flagged as <span style={{ color: '#ef4444' }}>HIGH ALERT</span>. Games with 2 triggers are on <span style={{ color: '#f5a623' }}>WATCH</span>.
                </p>
              </div>

              <p className="font-mono text-xs text-slate-600 uppercase tracking-widest">
                Base Triggers (always evaluated)
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {baseEntries.map(([key, { label, description }]) => (
                  <div
                    key={key}
                    className="rounded-lg p-3 space-y-1"
                    style={{
                      backgroundColor: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.04)',
                    }}
                  >
                    <span
                      className="font-mono text-xs font-bold px-2 py-0.5 rounded inline-block"
                      style={{
                        color: '#fbbf24',
                        backgroundColor: 'rgba(245,166,35,0.08)',
                        border: '1px solid rgba(245,166,35,0.15)',
                      }}
                    >
                      {label}
                    </span>
                    <p className="font-mono text-xs text-slate-500 leading-relaxed">
                      {description}
                    </p>
                  </div>
                ))}
              </div>

              {vegasEntries.length > 0 && (
                <>
                  <p className="font-mono text-xs text-slate-600 uppercase tracking-widest pt-2">
                    Vegas Triggers (when betting lines available)
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {vegasEntries.map(([key, { label, description }]) => (
                      <div
                        key={key}
                        className="rounded-lg p-3 space-y-1"
                        style={{
                          backgroundColor: 'rgba(255,255,255,0.02)',
                          border: '1px solid rgba(255,255,255,0.04)',
                        }}
                      >
                        <span
                          className="font-mono text-xs font-bold px-2 py-0.5 rounded inline-block"
                          style={{
                            color: '#a78bfa',
                            backgroundColor: 'rgba(167,139,250,0.08)',
                            border: '1px solid rgba(167,139,250,0.15)',
                          }}
                        >
                          {label}
                        </span>
                        <p className="font-mono text-xs text-slate-500 leading-relaxed">
                          {description}
                        </p>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function UpsetAlerts({ alerts }) {
  const [roundFilter, setRoundFilter] = useState('ALL');

  // alerts can be {items, roundSummary} or raw array
  const items = alerts?.items ?? alerts ?? [];
  const roundSummary = alerts?.roundSummary ?? {};

  if (!items || items.length === 0) {
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

  const filtered = roundFilter === 'ALL'
    ? items
    : items.filter(a => a.round === parseInt(roundFilter));

  const sorted = [...filtered].sort(
    (a, b) => (a.round ?? 64) - (b.round ?? 64) || (b.upset_score ?? 0) - (a.upset_score ?? 0)
  );
  const highCount = sorted.filter((a) => a.upset_score >= 3).length;
  const watchCount = sorted.filter(
    (a) => a.upset_score >= 2 && a.upset_score < 3
  ).length;

  const roundTabs = ['ALL', '64', '32', '16', '8', '4'];
  const roundLabels = { ALL: 'ALL', '64': 'R64', '32': 'R32', '16': 'S16', '8': 'E8', '4': 'F4' };

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      {/* Section header */}
      <div className="flex items-center gap-4 mb-4">
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
          {items.length} ALERTS
        </span>
      </div>

      {/* Round filter tabs */}
      <div className="flex gap-1 p-1 rounded-lg mb-4 flex-wrap" style={{ backgroundColor: '#151d38' }}>
        {roundTabs.map(rd => {
          const key = rd === 'ALL' ? null : `R${rd}`;
          const summary = key ? roundSummary[key] : null;
          const count = rd === 'ALL' ? items.length : items.filter(a => a.round === parseInt(rd)).length;
          const highN = summary?.high ?? 0;
          return (
            <button key={rd} onClick={() => setRoundFilter(rd)}
              className="font-mono text-xs px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5"
              style={{
                backgroundColor: roundFilter === rd ? 'rgba(239,68,68,0.12)' : 'transparent',
                color: roundFilter === rd ? '#ef4444' : '#475569',
                border: roundFilter === rd ? '1px solid rgba(239,68,68,0.3)' : '1px solid transparent',
              }}
            >
              {roundLabels[rd]}
              <span className="text-slate-600">({count})</span>
              {highN > 0 && rd !== 'ALL' && (
                <span style={{ color: '#ef4444', fontSize: 9 }}>{highN}!</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Per-round summary row */}
      {Object.keys(roundSummary).length > 0 && roundFilter === 'ALL' && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {Object.entries(roundSummary).map(([rd, s]) => (
            <div key={rd} className="font-mono text-xs px-3 py-1.5 rounded-lg"
              style={{ backgroundColor: '#0f1629', border: '1px solid rgba(255,255,255,0.04)' }}>
              <span className="text-slate-500">{rd}:</span>{' '}
              {s.high > 0 && <span style={{ color: '#ef4444' }}>{s.high} high</span>}
              {s.high > 0 && s.watch > 0 && <span className="text-slate-600"> · </span>}
              {s.watch > 0 && <span style={{ color: '#f5a623' }}>{s.watch} watch</span>}
              {s.high === 0 && s.watch === 0 && <span className="text-slate-600">clear</span>}
            </div>
          ))}
        </div>
      )}

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

      {/* Trigger explanations */}
      <TriggerLegend />

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sorted.map((alert, i) => (
          <AlertCard key={i} alert={alert} index={i} />
        ))}
      </div>
    </section>
  );
}
