import { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

import { useSimulation, useUpsetAlerts, useOverride } from './hooks/useApi';
import Hero from './components/Hero';
import SimLoading from './components/SimLoading';
import BracketView from './components/BracketView';
import InteractiveBracket from './components/InteractiveBracket';
import OverrideModal from './components/OverrideModal';
import OverrideHistory from './components/OverrideHistory';
import UpsetAlerts from './components/UpsetAlerts';
import FinalFour from './components/FinalFour';
import EquityDashboard from './components/EquityDashboard';
import BenchmarkPanel from './components/BenchmarkPanel';
import HelpPanel from './components/HelpPanel';

function SectionDivider() {
  return (
    <div
      className="w-full h-px mx-auto max-w-5xl"
      style={{
        background:
          'linear-gradient(90deg, transparent, rgba(245,166,35,0.15), transparent)',
      }}
    />
  );
}

function ErrorBanner({ message, onDismiss }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      className="fixed top-6 left-1/2 -translate-x-1/2 z-50 max-w-xl w-full px-4"
    >
      <div
        className="rounded-xl px-5 py-4 flex items-start justify-between gap-4 shadow-xl"
        style={{
          backgroundColor: '#1a0a0a',
          border: '1px solid rgba(239,68,68,0.4)',
        }}
      >
        <div>
          <p className="font-mono font-bold text-sm text-red-400 mb-1">
            Simulation Error
          </p>
          <p className="font-mono text-xs text-slate-400">{message}</p>
        </div>
        <button
          onClick={onDismiss}
          className="font-mono text-xs text-slate-500 hover:text-white mt-0.5 shrink-0"
        >
          ✕
        </button>
      </div>
    </motion.div>
  );
}

function NavBar({ hasResults, onScrollTo, onOpenHelp }) {
  const sections = hasResults
    ? [
        { id: 'bracket', label: 'Bracket' },
        { id: 'upsets', label: 'Upset Alerts' },
        { id: 'final-four', label: 'Final Four' },
        { id: 'equity', label: 'Equity Map' },
        { id: 'benchmark', label: 'Benchmark' },
      ]
    : [];

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-6 py-3"
      style={{
        backgroundColor: 'rgba(10,14,26,0.92)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}
    >
      <span
        className="font-mono font-black text-sm tracking-widest"
        style={{ color: '#f5a623' }}
      >
        MM·AI
      </span>
      {sections.length > 0 && (
        <div className="hidden sm:flex items-center gap-6">
          {sections.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => onScrollTo(id)}
              className="font-mono text-xs tracking-wider text-slate-400 hover:text-white transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-4">
        <button
          onClick={onOpenHelp}
          className="font-mono text-xs tracking-wider text-slate-400 hover:text-white transition-colors px-2 py-1 rounded"
          style={{ border: '1px solid rgba(255,255,255,0.08)' }}
        >
          ? Help
        </button>
        <span className="font-mono text-xs text-slate-600">2026</span>
      </div>
    </nav>
  );
}

export default function App() {
  const { data: simData, loading, error, runSimulation } = useSimulation();
  const { alerts, fetchAlerts } = useUpsetAlerts();
  const { applyOverride, loading: overrideLoading } = useOverride();
  const [dismissed, setDismissed] = useState(false);
  const resultsRef = useRef(null);
  const [overridePicks, setOverridePicks] = useState(null);
  const [overrideHistory, setOverrideHistory] = useState([]);
  const [pendingOverride, setPendingOverride] = useState(null);
  const [helpOpen, setHelpOpen] = useState(false);

  // When simulation completes, fetch upset alerts and scroll to results
  useEffect(() => {
    if (simData) {
      fetchAlerts();
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 300);
    }
  }, [simData, fetchAlerts]);

  // Reset error dismissal when a new error occurs
  useEffect(() => {
    if (error) setDismissed(false);
  }, [error]);

  const handleRunSimulation = (params) => {
    runSimulation(params);
  };

  const scrollTo = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  // Override: user clicks a losing team in the bracket
  const handleOverridePick = (gameWithClickedTeam) => {
    setPendingOverride(gameWithClickedTeam);
  };

  const handleConfirmOverride = async (game) => {
    const currentPicks = overridePicks || equityBracket?.picks || [];
    const result = await applyOverride({
      round: game.round,
      team_a: game.team_a,
      team_b: game.team_b,
      new_winner: game.clickedTeam,
      region: game.region,
      current_picks: currentPicks,
    });
    if (result) {
      setOverridePicks(result.picks);
      setOverrideHistory(prev => [...prev, {
        round: game.round,
        region: game.region,
        team_a: game.team_a,
        team_b: game.team_b,
        original_winner: game.winner,
        new_winner: game.clickedTeam,
        cascade_count: result.total_changes - 1,
        cascaded_changes: result.changes?.filter(c => c.type === 'cascade') || [],
      }]);
    }
    setPendingOverride(null);
  };

  const handleUndoOverride = (index) => {
    // Remove this override and all subsequent ones, then replay from original
    setOverrideHistory(prev => prev.filter((_, i) => i !== index));
    // Reset to original picks — ideally would replay remaining overrides
    // but for simplicity, reset to model picks
    setOverridePicks(null);
  };

  const handleResetAll = () => {
    setOverridePicks(null);
    setOverrideHistory([]);
  };

  // Extract data from simulation response
  // API returns: { safe_bracket: {picks, final_four, champion, ...},
  //               equity_bracket: {...}, comparison: {...}, simulation: {...} }
  const safeBracket = simData?.safe_bracket;
  const equityBracket = simData?.equity_bracket;
  const picks = equityBracket?.picks ?? safeBracket?.picks ?? [];
  const champion = equityBracket?.champion ?? safeBracket?.champion ?? null;
  const simulation = simData?.simulation ?? null;
  const comparison = simData?.comparison ?? null;
  const inlineAlerts = alerts;

  // Transform final_four from {East: "Duke", ...} to array format for FinalFour component
  const ffRaw = equityBracket?.final_four ?? safeBracket?.final_four ?? null;
  const allTeams = simulation?.all_teams ?? simulation?.top_contenders ?? [];
  const finalFour = ffRaw
    ? Object.entries(ffRaw).map(([region, team]) => {
        const stats = allTeams.find((t) => t.team_name === team) ?? {};
        return {
          team: team,
          region: region,
          seed: stats.seed ?? null,
          champ_pct: stats.champ_pct ?? 0,
          sim_win_rate: stats.R4_pct ?? 0,
          equity_score: null,
        };
      })
    : [];

  const hasResults = !!simData;

  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: '#0a0e1a' }}
    >
      <NavBar hasResults={hasResults} onScrollTo={scrollTo} onOpenHelp={() => setHelpOpen(true)} />
      <HelpPanel isOpen={helpOpen} onClose={() => setHelpOpen(false)} />

      {/* Error toast */}
      <AnimatePresence>
        {error && !dismissed && (
          <ErrorBanner message={error} onDismiss={() => setDismissed(true)} />
        )}
      </AnimatePresence>

      {/* Override confirmation modal */}
      <AnimatePresence>
        {pendingOverride && (
          <OverrideModal
            game={pendingOverride}
            onConfirm={handleConfirmOverride}
            onCancel={() => setPendingOverride(null)}
            alerts={alerts}
          />
        )}
      </AnimatePresence>

      {/* Hero — always visible */}
      <div className="pt-12">
        <Hero onRunSimulation={handleRunSimulation} loading={loading} />
      </div>

      {/* Loading overlay */}
      <AnimatePresence>
        {loading && (
          <motion.div
            className="fixed inset-0 z-30"
            style={{ backgroundColor: '#0a0e1a' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <SimLoading />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {hasResults && !loading && (
          <motion.div
            ref={resultsRef}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            {/* Results header */}
            <div
              className="w-full py-8 px-4 text-center"
              style={{
                backgroundColor: '#0f1629',
                borderTop: '1px solid rgba(245,166,35,0.15)',
                borderBottom: '1px solid rgba(245,166,35,0.08)',
              }}
            >
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <p className="font-mono text-xs tracking-[0.4em] text-slate-500 uppercase mb-2">
                  Simulation Complete — 50,000 runs
                </p>
                <h2
                  className="font-mono font-black text-2xl text-white"
                  style={{ textShadow: '0 0 20px rgba(245,166,35,0.2)' }}
                >
                  2026 BRACKET ANALYSIS
                </h2>
              </motion.div>
            </div>

            {/* Final Four */}
            <motion.div
              id="final-four"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1, duration: 0.5 }}
            >
              <FinalFour finalFour={finalFour} champion={champion} />
            </motion.div>

            <SectionDivider />

            {/* Bracket — Interactive + Stats table with tab toggle */}
            <motion.div
              id="bracket"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
            >
              <OverrideHistory
                overrides={overrideHistory}
                onUndoOverride={handleUndoOverride}
                onResetAll={handleResetAll}
              />
              <InteractiveBracket
                safePicks={safeBracket?.picks ?? []}
                equityPicks={equityBracket?.picks ?? []}
                overridePicks={overridePicks}
                champion={overridePicks
                  ? overridePicks.find(p => p.round === 2)?.winner
                  : equityBracket?.champion ?? safeBracket?.champion}
                diffs={comparison?.differences ?? []}
                allTeams={allTeams}
                onOverridePick={handleOverridePick}
                alerts={inlineAlerts}
              />
              <div className="px-4 max-w-5xl mx-auto mt-4 mb-2">
                <details className="group">
                  <summary className="font-mono text-xs text-slate-500 cursor-pointer hover:text-slate-300 transition-colors">
                    Show game-by-game stats table
                  </summary>
                  <div className="mt-4">
                    <BracketView picks={picks} />
                  </div>
                </details>
              </div>
            </motion.div>

            <SectionDivider />

            {/* Upset Alerts */}
            <motion.div
              id="upsets"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.5 }}
            >
              <UpsetAlerts alerts={inlineAlerts} />
            </motion.div>

            <SectionDivider />

            {/* Equity Dashboard */}
            <motion.div
              id="equity"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.5 }}
            >
              <EquityDashboard picks={picks} />
            </motion.div>

            <SectionDivider />

            {/* Benchmark Panel */}
            <motion.div
              id="benchmark"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.5 }}
            >
              <BenchmarkPanel />
            </motion.div>

            {/* Footer */}
            <footer
              className="text-center py-12 px-4 mt-8"
              style={{
                borderTop: '1px solid rgba(255,255,255,0.04)',
              }}
            >
              <p className="font-mono text-xs text-slate-600">
                2026 March Madness AI — Monte Carlo · XGBoost · KenPom · Vegas Lines
              </p>
              <p className="font-mono text-xs text-slate-700 mt-2">
                For informational use only. Not financial or gambling advice.
              </p>
            </footer>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
