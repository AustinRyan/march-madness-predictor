import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const ROUND_LABELS = { 64: 'Round of 64', 32: 'Round of 32', 16: 'Sweet 16', 8: 'Elite 8', 4: 'Final Four', 2: 'Championship' };

function GameRow({ game }) {
  const isUpset = game.status === 'final' && game.winner &&
    ((game.winner === game.team_a && game.seed_a > game.seed_b) ||
     (game.winner === game.team_b && game.seed_b > game.seed_a));
  const isInProgress = game.status === 'in_progress';
  const isUpcoming = game.status === 'upcoming';

  return (
    <div
      className="flex items-center justify-between px-4 py-3 rounded-lg mb-1"
      style={{
        backgroundColor: isUpset ? 'rgba(239,68,68,0.06)' : 'rgba(255,255,255,0.02)',
        border: isUpset ? '1px solid rgba(239,68,68,0.2)' : '1px solid rgba(255,255,255,0.04)',
      }}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <span className="font-mono text-xs text-slate-600 w-16 shrink-0">{game.region}</span>

        <div className="flex items-center gap-1.5">
          <span className="font-mono text-xs text-slate-500">[{game.seed_a}]</span>
          <span className={`font-mono text-sm ${game.winner === game.team_a ? 'font-bold text-white' : 'text-slate-400'}`}>
            {game.team_a}
          </span>
        </div>

        <span className="font-mono text-xs text-slate-600">vs</span>

        <div className="flex items-center gap-1.5">
          <span className="font-mono text-xs text-slate-500">[{game.seed_b}]</span>
          <span className={`font-mono text-sm ${game.winner === game.team_b ? 'font-bold text-white' : 'text-slate-400'}`}>
            {game.team_b}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {game.status === 'final' && (
          <span className="font-mono text-sm text-slate-300">
            {game.score_a}-{game.score_b}{game.overtime ? ' OT' : ''}
          </span>
        )}
        {isInProgress && (
          <motion.span
            className="font-mono text-xs px-2 py-0.5 rounded"
            style={{ color: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)' }}
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            LIVE
          </motion.span>
        )}
        {isUpcoming && (
          <span className="font-mono text-xs text-slate-600">Upcoming</span>
        )}
        {isUpset && (
          <span className="font-mono text-xs px-2 py-0.5 rounded"
            style={{ color: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)' }}>
            UPSET
          </span>
        )}
      </div>
    </div>
  );
}

export default function LiveResultsTable({ rounds }) {
  const [openRound, setOpenRound] = useState('64');

  if (!rounds) return null;

  const roundKeys = ['64', '32', '16', '8', '4', '2'].filter(k => rounds[k] && rounds[k].length > 0);

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <div className="h-8 w-1 rounded-full" style={{ backgroundColor: '#22c55e' }} />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          RESULTS
        </h2>
      </div>

      {roundKeys.map(rd => {
        const games = rounds[rd] || [];
        const finalGames = games.filter(g => g.status === 'final');
        const upsetCount = games.filter(g =>
          g.status === 'final' && g.winner &&
          ((g.winner === g.team_a && g.seed_a > g.seed_b) ||
           (g.winner === g.team_b && g.seed_b > g.seed_a))
        ).length;

        return (
          <div key={rd} className="mb-4">
            <button
              onClick={() => setOpenRound(openRound === rd ? null : rd)}
              className="w-full flex items-center justify-between px-4 py-3 rounded-lg transition-colors"
              style={{
                backgroundColor: openRound === rd ? '#151d38' : '#0f1629',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <div className="flex items-center gap-3">
                <span className="font-mono font-bold text-sm text-white">
                  {ROUND_LABELS[parseInt(rd)] || `Round ${rd}`}
                </span>
                <span className="font-mono text-xs text-slate-500">
                  {finalGames.length}/{games.length} complete
                </span>
                {upsetCount > 0 && (
                  <span className="font-mono text-xs px-2 py-0.5 rounded"
                    style={{ color: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)' }}>
                    {upsetCount} upset{upsetCount !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <span className="font-mono text-xs text-slate-500">
                {openRound === rd ? '−' : '+'}
              </span>
            </button>

            <AnimatePresence>
              {openRound === rd && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="pt-2 space-y-1">
                    {games.map((game, i) => (
                      <GameRow key={`${game.team_a}-${game.team_b}-${i}`} game={game} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </section>
  );
}
