import { useState } from 'react';
import { motion } from 'framer-motion';

const ROUND_ORDER = ['R64', 'R32', 'S16', 'E8', 'F4', 'Championship'];
const ROUND_LABELS = {
  R64: 'Round of 64',
  R32: 'Round of 32',
  S16: 'Sweet 16',
  E8: 'Elite 8',
  F4: 'Final Four',
  Championship: 'Championship',
};

function seedColor(seed) {
  if (seed <= 2) return '#10b981';
  if (seed <= 5) return '#22d3ee';
  if (seed <= 8) return '#94a3b8';
  if (seed <= 11) return '#f59e0b';
  return '#ef4444';
}

function GameRow({ game, index }) {
  const isHighAlert = game.upset_score >= 3 || game.is_upset === 'HIGH_ALERT';
  const isUpset = game.is_upset === true || game.is_upset === 'UPSET';
  const winnerIsA = game.winner === game.team_a;
  const winnerIsB = game.winner === game.team_b;

  let rowBorder = 'transparent';
  if (isHighAlert) rowBorder = 'rgba(239,68,68,0.5)';
  else if (isUpset) rowBorder = 'rgba(245,166,35,0.35)';

  const probA = game.ml_prob_a != null ? (game.ml_prob_a * 100).toFixed(1) : '—';
  const probB = game.ml_prob_a != null ? ((1 - game.ml_prob_a) * 100).toFixed(1) : '—';

  return (
    <motion.tr
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.012, duration: 0.25 }}
      style={{ borderLeft: `3px solid ${rowBorder}` }}
    >
      {/* Region */}
      <td
        className="px-3 py-2.5 font-mono text-xs text-slate-500 whitespace-nowrap"
        style={{ width: 90 }}
      >
        {game.region ?? '—'}
      </td>

      {/* Team A */}
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className="font-mono text-xs font-bold tabular-nums"
            style={{ color: seedColor(game.seed_a), minWidth: 22 }}
          >
            [{game.seed_a}]
          </span>
          <span
            className={`font-mono text-sm ${winnerIsA ? 'font-bold text-white' : 'text-slate-400'}`}
          >
            {game.team_a}
          </span>
          {winnerIsA && (
            <span className="font-mono text-xs text-emerald-400">✓ WIN</span>
          )}
        </div>
      </td>

      {/* Team B */}
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className="font-mono text-xs font-bold tabular-nums"
            style={{ color: seedColor(game.seed_b), minWidth: 22 }}
          >
            [{game.seed_b}]
          </span>
          <span
            className={`font-mono text-sm ${winnerIsB ? 'font-bold text-white' : 'text-slate-400'}`}
          >
            {game.team_b}
          </span>
          {winnerIsB && (
            <span className="font-mono text-xs text-emerald-400">✓ WIN</span>
          )}
        </div>
      </td>

      {/* ML Prob */}
      <td className="px-3 py-2.5 text-right">
        <div className="flex flex-col items-end gap-0.5">
          <span className="font-mono text-xs tabular-nums" style={{ color: '#f5a623' }}>
            {probA}%
          </span>
          <span className="font-mono text-xs tabular-nums text-slate-500">
            {probB}%
          </span>
        </div>
      </td>

      {/* Flag */}
      <td className="px-3 py-2.5 text-center" style={{ width: 110 }}>
        {isHighAlert ? (
          <span
            className="font-mono text-xs px-2 py-0.5 rounded"
            style={{
              color: '#ef4444',
              backgroundColor: 'rgba(239,68,68,0.12)',
              border: '1px solid rgba(239,68,68,0.3)',
            }}
          >
            HIGH ALERT
          </span>
        ) : isUpset ? (
          <span
            className="font-mono text-xs px-2 py-0.5 rounded"
            style={{
              color: '#f5a623',
              backgroundColor: 'rgba(245,166,35,0.1)',
              border: '1px solid rgba(245,166,35,0.25)',
            }}
          >
            UPSET
          </span>
        ) : (
          <span className="font-mono text-xs text-slate-600">—</span>
        )}
      </td>
    </motion.tr>
  );
}

function RoundTable({ round, games }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className="mb-6 rounded-xl overflow-hidden"
      style={{
        backgroundColor: '#151d38',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between px-5 py-3.5 transition-colors hover:bg-white/5"
        style={{ borderBottom: collapsed ? 'none' : '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-3">
          <span
            className="font-mono font-bold text-sm tracking-widest"
            style={{ color: '#f5a623' }}
          >
            {round}
          </span>
          <span className="font-mono text-sm text-slate-400">
            {ROUND_LABELS[round]}
          </span>
          <span
            className="font-mono text-xs px-2 py-0.5 rounded-full"
            style={{
              color: '#94a3b8',
              backgroundColor: 'rgba(255,255,255,0.05)',
            }}
          >
            {games.length} game{games.length !== 1 ? 's' : ''}
          </span>
        </div>
        <span className="font-mono text-xs text-slate-500">
          {collapsed ? '▼ EXPAND' : '▲ COLLAPSE'}
        </span>
      </button>

      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <th className="px-3 py-2 text-left font-mono text-xs tracking-widest text-slate-600 uppercase">
                  Region
                </th>
                <th className="px-3 py-2 text-left font-mono text-xs tracking-widest text-slate-600 uppercase">
                  Team A
                </th>
                <th className="px-3 py-2 text-left font-mono text-xs tracking-widest text-slate-600 uppercase">
                  Team B
                </th>
                <th className="px-3 py-2 text-right font-mono text-xs tracking-widest text-slate-600 uppercase">
                  ML Prob
                </th>
                <th className="px-3 py-2 text-center font-mono text-xs tracking-widest text-slate-600 uppercase">
                  Flag
                </th>
              </tr>
            </thead>
            <tbody>
              {games.map((game, i) => (
                <GameRow
                  key={`${round}-${i}`}
                  game={game}
                  index={i}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function BracketView({ picks }) {
  if (!picks || picks.length === 0) {
    return (
      <div className="text-center py-20 font-mono text-slate-500">
        No bracket data available.
      </div>
    );
  }

  // Group by round
  const byRound = {};
  for (const pick of picks) {
    const r = pick.round || 'Unknown';
    if (!byRound[r]) byRound[r] = [];
    byRound[r].push(pick);
  }

  const sortedRounds = ROUND_ORDER.filter((r) => byRound[r]).concat(
    Object.keys(byRound).filter((r) => !ROUND_ORDER.includes(r))
  );

  const totalGames = picks.length;
  const upsets = picks.filter((p) => p.is_upset === true || p.is_upset === 'UPSET').length;
  const highAlerts = picks.filter(
    (p) => p.upset_score >= 3 || p.is_upset === 'HIGH_ALERT'
  ).length;

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      {/* Section header */}
      <div className="flex items-center gap-4 mb-8">
        <div
          className="h-8 w-1 rounded-full"
          style={{ backgroundColor: '#f5a623' }}
        />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          BRACKET PREDICTIONS
        </h2>
      </div>

      {/* Summary bar */}
      <div
        className="grid grid-cols-3 gap-px mb-8 rounded-lg overflow-hidden"
        style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}
      >
        {[
          { label: 'TOTAL GAMES', value: totalGames, color: '#f5a623' },
          { label: 'UPSETS PICKED', value: upsets, color: '#f59e0b' },
          { label: 'HIGH ALERTS', value: highAlerts, color: '#ef4444' },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="flex flex-col items-center py-4"
            style={{ backgroundColor: '#151d38' }}
          >
            <span className="font-mono font-bold text-xl" style={{ color }}>
              {value}
            </span>
            <span className="font-mono text-xs tracking-widest text-slate-500 mt-1">
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 mb-6 flex-wrap">
        {[
          { color: '#10b981', label: 'Favorite wins' },
          { color: '#f5a623', label: 'Upset pick' },
          { color: '#ef4444', label: 'High alert' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: color, opacity: 0.7 }}
            />
            <span className="font-mono text-xs text-slate-400">{label}</span>
          </div>
        ))}
      </div>

      {/* Round tables */}
      {sortedRounds.map((round) => (
        <RoundTable key={round} round={round} games={byRound[round]} />
      ))}
    </section>
  );
}
