import { motion } from 'framer-motion';

export default function OverrideHistory({ overrides, onUndoOverride, onResetAll }) {
  if (!overrides || overrides.length === 0) return null;

  return (
    <div className="px-4 max-w-[1440px] mx-auto mb-6">
      <div
        className="rounded-xl p-4"
        style={{
          backgroundColor: '#151d38',
          border: '1px solid rgba(245,166,35,0.15)',
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span>✏️</span>
            <span className="font-mono text-xs font-bold text-white">
              Manual Overrides ({overrides.length})
            </span>
          </div>
          <button
            onClick={onResetAll}
            className="font-mono text-xs px-3 py-1 rounded-md transition-all text-slate-400 hover:text-white"
            style={{
              backgroundColor: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.2)',
            }}
          >
            Reset All to Model
          </button>
        </div>

        <div className="space-y-2">
          {overrides.map((ov, i) => (
            <motion.div
              key={`${ov.round}-${ov.team_a}-${ov.team_b}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center justify-between gap-3 rounded-lg px-3 py-2"
              style={{ backgroundColor: '#0f1629' }}
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <span
                  className="font-mono text-xs px-1.5 py-0.5 rounded shrink-0"
                  style={{
                    backgroundColor: 'rgba(245,166,35,0.1)',
                    color: '#f5a623',
                    border: '1px solid rgba(245,166,35,0.2)',
                  }}
                >
                  R{ov.round}
                </span>
                <span className="font-mono text-xs text-slate-400 truncate">
                  <span className="text-slate-500 line-through">{ov.original_winner}</span>
                  {' → '}
                  <span style={{ color: '#f5a623' }}>{ov.new_winner}</span>
                </span>
                {ov.region && (
                  <span className="font-mono text-xs text-slate-600 shrink-0">
                    [{ov.region}]
                  </span>
                )}
              </div>

              {/* Cascade count */}
              {ov.cascade_count > 0 && (
                <span className="font-mono text-xs text-slate-500 shrink-0">
                  +{ov.cascade_count} changed
                </span>
              )}

              <button
                onClick={() => onUndoOverride(i)}
                className="font-mono text-xs text-slate-500 hover:text-red-400 shrink-0 transition-colors"
                title="Undo this override"
              >
                ✕
              </button>
            </motion.div>
          ))}
        </div>

        {/* Cascade summary */}
        {overrides.some(o => o.cascaded_changes?.length > 0) && (
          <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
            <p className="font-mono text-xs text-slate-500 mb-2">Cascade effects:</p>
            {overrides.flatMap(o => o.cascaded_changes || []).map((ch, i) => (
              <div key={i} className="font-mono text-xs text-slate-600 ml-4">
                R{ch.round} [{ch.region}]: {ch.old_winner} → <span style={{ color: '#f5a623' }}>{ch.new_winner}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
