import { motion } from 'framer-motion';

export default function LiveHeader({ data }) {
  const progress = data?.progress || { completed: 0, total: 32, pct: 0 };
  const upsets = data?.upsets || [];
  const lastUpdated = data?.last_updated;

  return (
    <section className="px-4 py-12 max-w-5xl mx-auto text-center">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <p className="font-mono text-xs tracking-[0.4em] text-slate-500 uppercase mb-3">
          Live Tournament Tracker
        </p>
        <h2
          className="font-mono font-black text-3xl text-white mb-6"
          style={{ textShadow: '0 0 20px rgba(34,197,94,0.2)' }}
        >
          {data?.current_round_label || 'Round of 64'}
        </h2>

        {/* Progress bar */}
        <div className="max-w-md mx-auto mb-6">
          <div className="flex justify-between mb-2">
            <span className="font-mono text-xs text-slate-400">
              {progress.completed}/{progress.total} games complete
            </span>
            <span className="font-mono text-xs text-slate-500">
              {progress.pct}%
            </span>
          </div>
          <div
            className="w-full rounded-full overflow-hidden"
            style={{ height: 6, backgroundColor: 'rgba(255,255,255,0.06)' }}
          >
            <motion.div
              className="h-full rounded-full"
              style={{ backgroundColor: '#22c55e' }}
              initial={{ width: 0 }}
              animate={{ width: `${progress.pct}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
            />
          </div>
        </div>

        {/* Stats row */}
        <div className="flex items-center justify-center gap-6 flex-wrap">
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-lg"
            style={{
              backgroundColor: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
            }}
          >
            <span className="font-mono font-bold text-sm" style={{ color: '#ef4444' }}>
              {upsets.length}
            </span>
            <span className="font-mono text-xs text-slate-400">Upsets So Far</span>
          </div>
          {lastUpdated && (
            <span className="font-mono text-xs text-slate-600">
              Updated: {new Date(lastUpdated).toLocaleString()}
            </span>
          )}
        </div>
      </motion.div>
    </section>
  );
}
