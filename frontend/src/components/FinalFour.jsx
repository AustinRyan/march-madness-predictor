import { motion } from 'framer-motion';

const REGION_COLORS = {
  East: '#3b82f6',
  West: '#8b5cf6',
  South: '#10b981',
  Midwest: '#f59e0b',
};

function regionColor(region) {
  return REGION_COLORS[region] ?? '#94a3b8';
}

function TeamCard({ team, region, isChampion, champPct, simWinRate, equityScore, delay }) {
  const rc = regionColor(region);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.4, ease: 'easeOut' }}
      className="relative rounded-xl p-6 flex flex-col items-center text-center overflow-hidden"
      style={{
        backgroundColor: isChampion ? 'rgba(245,166,35,0.06)' : '#151d38',
        border: isChampion
          ? '1px solid rgba(245,166,35,0.5)'
          : '1px solid rgba(255,255,255,0.06)',
        boxShadow: isChampion
          ? '0 0 40px rgba(245,166,35,0.15), 0 0 80px rgba(245,166,35,0.08)'
          : 'none',
      }}
    >
      {isChampion && (
        <motion.div
          className="absolute top-0 left-0 right-0 h-0.5"
          style={{ backgroundColor: '#f5a623' }}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}

      {/* Region badge */}
      <div
        className="font-mono text-xs tracking-widest px-3 py-1 rounded-full mb-4"
        style={{
          color: rc,
          backgroundColor: `${rc}18`,
          border: `1px solid ${rc}40`,
        }}
      >
        {region?.toUpperCase() ?? 'UNKNOWN'}
      </div>

      {/* Champion crown */}
      {isChampion && (
        <motion.div
          className="mb-3"
          animate={{ y: [0, -3, 0] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        >
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <path
              d="M4 22 L8 10 L16 16 L24 6 L28 10 L28 22 Z"
              fill="rgba(245,166,35,0.8)"
              stroke="#f5a623"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <rect x="4" y="22" width="24" height="3" rx="1.5" fill="#f5a623" />
          </svg>
        </motion.div>
      )}

      {/* Team name */}
      <h3
        className={`font-mono font-black leading-tight mb-1 ${
          isChampion ? 'text-2xl' : 'text-lg'
        }`}
        style={{ color: isChampion ? '#f5a623' : '#ffffff' }}
      >
        {team ?? '—'}
      </h3>

      {isChampion && (
        <p className="font-mono text-xs tracking-[0.3em] text-slate-400 uppercase mb-4">
          Predicted Champion
        </p>
      )}

      {/* Stats */}
      <div className="w-full mt-4 space-y-2">
        {champPct != null && (
          <div className="flex justify-between items-center">
            <span className="font-mono text-xs text-slate-500 uppercase tracking-wider">
              Champ %
            </span>
            <span
              className="font-mono text-sm font-bold"
              style={{ color: isChampion ? '#f5a623' : '#ffffff' }}
            >
              {(champPct * 100).toFixed(1)}%
            </span>
          </div>
        )}
        {simWinRate != null && (
          <div className="flex justify-between items-center">
            <span className="font-mono text-xs text-slate-500 uppercase tracking-wider">
              Sim Win Rate
            </span>
            <span className="font-mono text-sm font-bold text-slate-200">
              {(simWinRate * 100).toFixed(1)}%
            </span>
          </div>
        )}
        {equityScore != null && (
          <div className="flex justify-between items-center">
            <span className="font-mono text-xs text-slate-500 uppercase tracking-wider">
              Equity Score
            </span>
            <span
              className="font-mono text-sm font-bold"
              style={{
                color:
                  equityScore > 1.2
                    ? '#10b981'
                    : equityScore > 0.8
                    ? '#f5a623'
                    : '#94a3b8',
              }}
            >
              {equityScore.toFixed(2)}x
            </span>
          </div>
        )}
      </div>

      {/* Win rate bar */}
      {simWinRate != null && (
        <div
          className="w-full mt-4 rounded-full overflow-hidden"
          style={{ height: 3, backgroundColor: 'rgba(255,255,255,0.06)' }}
        >
          <motion.div
            className="h-full rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(simWinRate * 100, 100)}%` }}
            transition={{ delay: delay + 0.3, duration: 0.8, ease: 'easeOut' }}
            style={{
              backgroundColor: isChampion ? '#f5a623' : regionColor(region),
            }}
          />
        </div>
      )}
    </motion.div>
  );
}

export default function FinalFour({ finalFour, champion }) {
  if (!finalFour || finalFour.length === 0) {
    return (
      <section className="px-4 py-8 max-w-5xl mx-auto">
        <div className="flex items-center gap-4 mb-8">
          <div className="h-8 w-1 rounded-full" style={{ backgroundColor: '#f5a623' }} />
          <h2 className="font-mono font-black text-2xl text-white tracking-tight">
            FINAL FOUR
          </h2>
        </div>
        <div className="text-center py-16 font-mono text-slate-500">
          No Final Four data available.
        </div>
      </section>
    );
  }

  // champion may come from API as object or may be embedded in finalFour
  const champTeam =
    champion?.team ?? champion?.name ?? (typeof champion === 'string' ? champion : null);
  const champObj =
    typeof champion === 'object' && champion !== null ? champion : null;

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      {/* Section header */}
      <div className="flex items-center gap-4 mb-10">
        <div className="h-8 w-1 rounded-full" style={{ backgroundColor: '#f5a623' }} />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          FINAL FOUR
        </h2>
        <span
          className="font-mono text-xs px-3 py-1 rounded-full"
          style={{
            color: '#f5a623',
            backgroundColor: 'rgba(245,166,35,0.1)',
            border: '1px solid rgba(245,166,35,0.25)',
          }}
        >
          2026 PREDICTIONS
        </span>
      </div>

      {/* Champion spotlight */}
      {champTeam && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-10 rounded-2xl p-8 text-center relative overflow-hidden"
          style={{
            backgroundColor: '#151d38',
            border: '1px solid rgba(245,166,35,0.3)',
          }}
        >
          {/* Background shimmer */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse at 50% 0%, rgba(245,166,35,0.08) 0%, transparent 60%)',
            }}
          />
          <div className="relative z-10">
            <p className="font-mono text-xs tracking-[0.4em] text-slate-500 uppercase mb-4">
              Predicted Champion
            </p>
            <motion.h2
              className="font-mono font-black text-5xl mb-4"
              style={{
                color: '#f5a623',
                textShadow: '0 0 40px rgba(245,166,35,0.5)',
              }}
              animate={{
                textShadow: [
                  '0 0 20px rgba(245,166,35,0.3)',
                  '0 0 50px rgba(245,166,35,0.7)',
                  '0 0 20px rgba(245,166,35,0.3)',
                ],
              }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            >
              {champTeam}
            </motion.h2>

            <div className="flex items-center justify-center gap-8 flex-wrap mt-4">
              {champObj?.champ_pct != null && (
                <div className="flex flex-col items-center">
                  <span
                    className="font-mono font-black text-3xl"
                    style={{ color: '#f5a623' }}
                  >
                    {(champObj.champ_pct * 100).toFixed(1)}%
                  </span>
                  <span className="font-mono text-xs text-slate-500 uppercase tracking-widest mt-1">
                    Championship Probability
                  </span>
                </div>
              )}
              {champObj?.sim_win_rate != null && (
                <div className="flex flex-col items-center">
                  <span className="font-mono font-black text-3xl text-white">
                    {(champObj.sim_win_rate * 100).toFixed(1)}%
                  </span>
                  <span className="font-mono text-xs text-slate-500 uppercase tracking-widest mt-1">
                    Sim Win Rate
                  </span>
                </div>
              )}
              {champObj?.equity_score != null && (
                <div className="flex flex-col items-center">
                  <span
                    className="font-mono font-black text-3xl"
                    style={{ color: '#10b981' }}
                  >
                    {champObj.equity_score.toFixed(2)}x
                  </span>
                  <span className="font-mono text-xs text-slate-500 uppercase tracking-widest mt-1">
                    Equity Score
                  </span>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* Final Four grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {finalFour.map((entry, i) => {
          const teamName = entry.team ?? entry.name ?? (typeof entry === 'string' ? entry : '—');
          const isChamp = champTeam && teamName === champTeam;
          return (
            <TeamCard
              key={i}
              team={teamName}
              region={entry.region}
              isChampion={isChamp}
              champPct={entry.champ_pct ?? entry.championship_probability}
              simWinRate={entry.sim_win_rate ?? entry.win_rate}
              equityScore={entry.equity_score}
              delay={i * 0.1}
            />
          );
        })}
      </div>
    </section>
  );
}
