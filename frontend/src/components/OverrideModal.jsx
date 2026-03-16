import { motion } from 'framer-motion';

export default function OverrideModal({ game, onConfirm, onCancel, alerts }) {
  if (!game) return null;

  const { team_a, team_b, seed_a, seed_b, ml_prob_a, winner, clickedTeam } = game;
  const isUpset = (clickedTeam === team_b && seed_a < seed_b) ||
                  (clickedTeam === team_a && seed_a > seed_b);
  const clickedSeed = clickedTeam === team_a ? seed_a : seed_b;
  const defeatedTeam = clickedTeam === team_a ? team_b : team_a;
  const defeatedSeed = clickedTeam === team_a ? seed_b : seed_a;
  const winProb = clickedTeam === team_a ? ml_prob_a : (1 - (ml_prob_a ?? 0.5));

  // Find upset alert for this matchup (alerts may be {items: [...]} or array)
  const alertItems = Array.isArray(alerts) ? alerts : alerts?.items ?? [];
  const alert = alertItems.find(a =>
    (a.favorite === team_a && a.underdog === team_b) ||
    (a.favorite === team_b && a.underdog === team_a)
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onCancel}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="rounded-xl p-6 max-w-md w-full"
        style={{
          backgroundColor: '#151d38',
          border: '1px solid rgba(245,166,35,0.3)',
          boxShadow: '0 0 40px rgba(0,0,0,0.5)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">✏️</span>
          <h3 className="font-mono font-bold text-white text-sm">
            Manual Override
          </h3>
        </div>

        {/* Matchup */}
        <div className="rounded-lg p-4 mb-4" style={{ backgroundColor: '#0f1629' }}>
          <p className="font-mono text-xs text-slate-500 mb-2">
            Pick <span style={{ color: '#f5a623' }}>({clickedSeed}) {clickedTeam}</span> to
            {isUpset ? ' upset' : ' beat'} ({defeatedSeed}) {defeatedTeam}?
          </p>
          <div className="flex items-center justify-between mt-3">
            <div>
              <span className="font-mono text-xs text-slate-500">ML Win Prob</span>
              <p className="font-mono font-bold text-sm" style={{
                color: winProb > 0.5 ? '#10b981' : winProb > 0.35 ? '#f5a623' : '#ef4444'
              }}>
                {(winProb * 100).toFixed(1)}%
              </p>
            </div>
            {alert && (
              <div className="text-right">
                <span className="font-mono text-xs text-slate-500">Upset Alert</span>
                <p className="font-mono font-bold text-sm" style={{
                  color: alert.upset_score >= 3 ? '#ef4444' : '#f5a623'
                }}>
                  {alert.upset_score}/9 flags
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Warning */}
        <p className="font-mono text-xs text-slate-400 mb-5 leading-relaxed">
          This will recalculate all downstream games using ML probabilities from this point forward.
        </p>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={() => onConfirm(game)}
            className="flex-1 font-mono text-xs font-bold py-2.5 rounded-lg transition-all"
            style={{
              backgroundColor: 'rgba(245,166,35,0.15)',
              color: '#f5a623',
              border: '1px solid rgba(245,166,35,0.4)',
            }}
          >
            Confirm Override
          </button>
          <button
            onClick={onCancel}
            className="flex-1 font-mono text-xs py-2.5 rounded-lg transition-all text-slate-400"
            style={{
              backgroundColor: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            Cancel
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
