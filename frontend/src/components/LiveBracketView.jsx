import { motion } from 'framer-motion';

const ROUND_SHORT = { 64: 'R64', 32: 'R32', 16: 'S16', 8: 'E8', 4: 'F4', 2: 'Final' };
const REGIONS = ['East', 'South', 'West', 'Midwest'];

function GameSlot({ game }) {
  if (!game) return null;
  const isUpset = game.status === 'final' && game.winner &&
    ((game.winner === game.team_a && game.seed_a > game.seed_b) ||
     (game.winner === game.team_b && game.seed_b > game.seed_a));
  const isLive = game.status === 'in_progress';

  const teamAWon = game.winner === game.team_a;
  const teamBWon = game.winner === game.team_b;

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        border: isUpset ? '1px solid rgba(239,68,68,0.3)' :
                isLive ? '1px solid rgba(34,197,94,0.3)' :
                '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Team A */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{
          backgroundColor: teamAWon
            ? (isUpset && game.seed_a > game.seed_b ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.08)')
            : '#0f1629',
        }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-500 w-5 text-right">{game.seed_a}</span>
          <span className={`font-mono text-xs ${teamAWon ? 'font-bold text-white' : game.status === 'final' ? 'text-slate-500' : 'text-slate-300'}`}>
            {game.team_a}
          </span>
        </div>
        {game.score_a != null && (
          <span className={`font-mono text-xs ${teamAWon ? 'font-bold text-white' : 'text-slate-500'}`}>
            {game.score_a}
          </span>
        )}
      </div>
      {/* Team B */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{
          backgroundColor: teamBWon
            ? (isUpset && game.seed_b > game.seed_a ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.08)')
            : '#0f1629',
          borderTop: '1px solid rgba(255,255,255,0.04)',
        }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-500 w-5 text-right">{game.seed_b}</span>
          <span className={`font-mono text-xs ${teamBWon ? 'font-bold text-white' : game.status === 'final' ? 'text-slate-500' : 'text-slate-300'}`}>
            {game.team_b}
          </span>
        </div>
        {game.score_b != null && (
          <span className={`font-mono text-xs ${teamBWon ? 'font-bold text-white' : 'text-slate-500'}`}>
            {game.score_b}
          </span>
        )}
      </div>
      {/* Status indicator */}
      {isLive && (
        <motion.div
          className="px-3 py-0.5 text-center"
          style={{ backgroundColor: 'rgba(34,197,94,0.06)' }}
          animate={{ opacity: [1, 0.4, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        >
          <span className="font-mono text-xs" style={{ color: '#22c55e' }}>LIVE</span>
        </motion.div>
      )}
      {game.status === 'upcoming' && (
        <div className="px-3 py-0.5 text-center" style={{ backgroundColor: 'rgba(255,255,255,0.02)' }}>
          <span className="font-mono text-xs text-slate-600">UPCOMING</span>
        </div>
      )}
    </div>
  );
}

function RegionBracket({ region, rounds }) {
  const roundNums = [64, 32, 16, 8];
  const regionRounds = {};

  for (const rd of roundNums) {
    const rdKey = String(rd);
    const games = (rounds[rdKey] || []).filter(g => g.region === region);
    if (games.length > 0) regionRounds[rd] = games;
  }

  if (Object.keys(regionRounds).length === 0) return null;

  return (
    <div
      className="rounded-xl p-4 space-y-4"
      style={{ backgroundColor: '#0f1629', border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <h3 className="font-mono font-bold text-sm text-white tracking-wider">{region}</h3>

      {roundNums.map(rd => {
        const games = regionRounds[rd];
        if (!games || games.length === 0) return null;
        return (
          <div key={rd}>
            <p className="font-mono text-xs text-slate-500 mb-2 tracking-widest">
              {ROUND_SHORT[rd]}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {games.map((g, i) => (
                <GameSlot key={`${g.team_a}-${g.team_b}-${i}`} game={g} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function LiveBracketView({ rounds }) {
  if (!rounds) return null;

  const ffGames = (rounds['4'] || []);
  const champGame = (rounds['2'] || []);

  return (
    <section className="px-4 py-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <div className="h-8 w-1 rounded-full" style={{ backgroundColor: '#3b82f6' }} />
        <h2 className="font-mono font-black text-2xl text-white tracking-tight">
          LIVE BRACKET
        </h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {REGIONS.map(region => (
          <motion.div
            key={region}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: REGIONS.indexOf(region) * 0.1 }}
          >
            <RegionBracket region={region} rounds={rounds} />
          </motion.div>
        ))}
      </div>

      {ffGames.length > 0 && (
        <div className="mt-6">
          <p className="font-mono text-xs text-slate-500 mb-3 tracking-widest text-center">FINAL FOUR</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg mx-auto">
            {ffGames.map((g, i) => <GameSlot key={i} game={g} />)}
          </div>
        </div>
      )}

      {champGame.length > 0 && (
        <div className="mt-4">
          <p className="font-mono text-xs text-slate-500 mb-3 tracking-widest text-center">CHAMPIONSHIP</p>
          <div className="max-w-xs mx-auto">
            {champGame.map((g, i) => <GameSlot key={i} game={g} />)}
          </div>
        </div>
      )}
    </section>
  );
}
