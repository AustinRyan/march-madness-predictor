import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const SECTIONS = [
  {
    id: 'risk',
    title: 'Risk Tolerance',
    icon: '🎚️',
    content: `The risk slider controls how "contrarian" your bracket is — how much it deviates from what everyone else picks.

**Low risk (0.0–0.3):** Plays it safe. Picks mostly favorites. Your bracket will look similar to the majority of other brackets. Good if you want a solid score but don't need to win the pool outright.

**Medium risk (0.4–0.6):** Balanced. Picks a few strategic upsets where the model sees value the public doesn't. This is the sweet spot for most pools.

**High risk (0.7–1.0):** Maximum differentiation. Picks multiple upsets and contrarian Final Four teams. Your bracket will look very different from the field. Use this in large pools (1,000+ entries) where you need to be unique to win.

The higher the risk, the more the system weighs "equity" (how undervalued a team is) over raw win probability.`,
  },
  {
    id: 'pool-size',
    title: 'Pool Size',
    icon: '👥',
    content: `Pool size tells the system how many brackets you're competing against.

**Small pools (10–100):** You don't need many upsets. A solid, accurate bracket can win. Even at high risk settings, the system automatically dampens the contrarian picks because you only need to beat a handful of people.

**Medium pools (100–10,000):** You need some differentiation. The system scales up the equity weighting proportionally — at risk 0.5 in a 10,000-person pool, you'll see Illinois replace Florida in the Final Four and a few strategic upsets.

**Large pools (10,000+):** You MUST be different to win. At risk 0.5 in a million-person pool, the system goes full contrarian — Connecticut in the Final Four, non-1-seeds advancing deep. This is because picking chalk means splitting with thousands of identical brackets.

**How it works under the hood:** Pool size automatically adjusts your effective risk level. At risk 0.5, a pool of 50 gives you an effective risk of just 0.14 (very conservative), while a pool of 1 million gives you the full 0.50. Think of it this way: in a small office pool, you're competing against your coworkers — play it safe. In a massive public pool, you're competing against a million strangers who all picked Duke — be different.`,
  },
  {
    id: 'bracket',
    title: 'Reading the Bracket',
    icon: '📊',
    content: `Each game in the bracket shows:

**Win Probability (ML: 76%)** — The model's estimated chance that this team wins this specific game, based on 28 statistical features. This is NOT a seed-based estimate — it's computed from real team stats.

**Vegas Spread (+2.5)** — The Vegas betting line. A negative number means that team is favored (e.g., -6.5 means favored by 6.5 points). Shows next to ML probability for comparison.

**Color coding:**
- Green border = model-favored winner
- Gold/amber border = upset pick (lower seed wins)
- Purple glow = pick that differs between safe and equity brackets
- Pencil icon (✏️) = manually overridden pick

**SAFE vs EQUITY toggle** — Switch between the two bracket views to see which picks differ. The equity bracket is your pool-optimized bracket.`,
  },
  {
    id: 'upsets',
    title: 'Upset Alerts',
    icon: '⚠️',
    content: `Each game is scored on up to 11 upset conditions (9 statistical + 2 Vegas). A score of 3+ means "HIGH ALERT" — multiple factors suggest an upset is plausible.

**Why can a game be flagged HIGH ALERT but the model still picks the favorite?**

Because the upset detector and the ML model serve different purposes:
- The **model** picks the single most likely winner
- The **upset detector** flags games where an upset is *plausible enough to consider*

A game might have 5 upset flags (close KenPom rankings, tempo mismatch, Vegas line within 5 points) but the favorite still has a 58% win probability. The model correctly picks the favorite, but the upset detector tells you "this is a volatile game — if you're building a contrarian bracket, this is where to take your shot."

**R32+ alerts say "PROJECTED"** — These are based on who the model expects to play in later rounds, not guaranteed matchups.`,
  },
  {
    id: 'equity',
    title: 'Equity Scores',
    icon: '💰',
    content: `Equity measures how much the public is over- or under-valuing a team.

**Equity = Model's Win Probability ÷ Public Pick Percentage**

- **Equity > 1.0** = The model thinks this team is BETTER than the public believes. Picking them gives you an edge because fewer other brackets will have them.
- **Equity = 1.0** = Fairly priced. The model and public agree.
- **Equity < 1.0** = The public is MORE bullish than the model. Picking them doesn't differentiate your bracket.

**Example:** Illinois has a 4.4% championship probability from the model, but only 2.6% of the public picks them. Equity = 4.4/2.6 = **1.73**. That's a high-value pick — you get above-average win probability with below-average competition.

**Example:** Michigan has 8.3% model probability but 13.9% public pick rate. Equity = 8.3/13.9 = **0.52**. The market loves Michigan more than the model does — picking them means competing with a lot of other brackets.`,
  },
  {
    id: 'override',
    title: 'Manual Overrides',
    icon: '✏️',
    content: `You can manually change any pick in the bracket:

1. **Click the losing team** in any game (your cursor changes to a crosshair)
2. A confirmation dialog shows the ML probability and upset alert score
3. **Confirm** to apply the override
4. All downstream games automatically recalculate using the ML model

Overridden picks show a ✏️ icon and gold border. You can:
- **Undo individual overrides** from the override history panel
- **Reset all** to return to the model's original picks

**When to use overrides:** After reviewing the upset alerts, you might want to manually force an upset the model doesn't pick. For example, if BYU vs Texas has a 5/11 upset score but the model picks BYU, you could override to Texas and see how it cascades through the bracket.`,
  },
  {
    id: 'safe-vs-equity',
    title: 'Safe vs Equity Bracket',
    icon: '⚖️',
    content: `The system generates two brackets:

**Safe Bracket (risk=0.1)**
- Picks based almost entirely on ML win probability
- Minimal upsets — mostly chalk
- Good for accuracy but bad for pool differentiation
- All 4 one-seeds typically make the Final Four

**Equity Bracket (your risk level)**
- Blends ML probability with equity scores
- More upsets in later rounds (S16, E8, F4) where pool points are highest
- Designed to be DIFFERENT from what everyone else picks
- Final Four often includes 2-3 non-one-seeds

**The picks that differ between the two brackets are highlighted in purple.** These are your key decision points — the games where equity says "take the contrarian pick" but the safe model says "stick with the favorite."

In a small office pool, use the safe bracket. In a large public pool, use the equity bracket.`,
  },
  {
    id: 'disclaimer',
    title: 'Data Sources & Disclaimer',
    icon: 'ℹ️',
    content: `**Public pick percentages** are derived from BetMGM championship moneyline odds (March 15, 2026), not from ESPN bracket challenge data. Round-by-round picks (R64–F4) use historical seed-based patterns calibrated to typical ESPN bracket behavior.

**Vegas lines** are BetMGM opening lines for R64 games as of March 15. Lines may have moved since then.

**The ML model** was trained on 1,071 real tournament games from 2008–2025. It uses KenPom, Barttorvik, coaching records, and historical upset patterns — all from real data, no synthetic inputs.

**This tool is for informational purposes only.** It does not guarantee results and should not be used as the sole basis for gambling decisions. Past model performance does not predict future results. The tournament is inherently unpredictable — that's what makes it fun.`,
  },
];

function Section({ section, isOpen, onToggle }) {
  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ border: '1px solid rgba(255,255,255,0.06)' }}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors"
        style={{ backgroundColor: isOpen ? 'rgba(245,166,35,0.04)' : '#0f1629' }}
      >
        <span className="text-base">{section.icon}</span>
        <span className="font-mono text-sm font-bold text-white flex-1">{section.title}</span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="text-slate-500 text-xs"
        >
          ▾
        </motion.span>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-2" style={{ backgroundColor: '#0a0e1a' }}>
              {section.content.split('\n\n').map((para, i) => (
                <p key={i} className="font-mono text-xs text-slate-400 leading-relaxed mb-3 last:mb-0"
                   dangerouslySetInnerHTML={{
                     __html: para
                       .replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-200">$1</strong>')
                       .replace(/\n/g, '<br/>')
                   }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function HelpPanel({ isOpen, onClose }) {
  const [openSections, setOpenSections] = useState(new Set(['risk']));

  const toggleSection = (id) => {
    setOpenSections(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-start justify-center pt-16 pb-8 px-4"
          style={{ backgroundColor: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.95, y: 20 }}
            className="rounded-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto"
            style={{
              backgroundColor: '#151d38',
              border: '1px solid rgba(245,166,35,0.2)',
              boxShadow: '0 0 60px rgba(0,0,0,0.5)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 rounded-t-xl"
              style={{ backgroundColor: '#151d38', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <div>
                <h2 className="font-mono font-black text-lg text-white">How It Works</h2>
                <p className="font-mono text-xs text-slate-500 mt-0.5">
                  Everything you need to know about this bracket tool
                </p>
              </div>
              <button onClick={onClose}
                className="font-mono text-sm text-slate-500 hover:text-white p-2 transition-colors">
                ✕
              </button>
            </div>

            {/* Sections */}
            <div className="p-4 space-y-2">
              {SECTIONS.map(section => (
                <Section
                  key={section.id}
                  section={section}
                  isOpen={openSections.has(section.id)}
                  onToggle={() => toggleSection(section.id)}
                />
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
