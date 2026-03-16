import { useState, useMemo, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';

/*
 * InteractiveBracket — Full tournament bracket visualization
 *
 * Renders at a fixed internal coordinate system (1400×900) then
 * CSS-scales to fit the viewport width. This ensures the bracket
 * never overflows regardless of screen size.
 */

// ── Internal coordinate system ────────────────────────────────────
// Everything is laid out in this fixed space, then scaled via CSS transform
const INNER_W = 1400;
const INNER_H = 880;
const SLOT_W = 120;
const SLOT_H = 22;
const PAIR_GAP = 3;
const ROUND_GAP = 16;
const REGION_PAD = 6;

const COLORS = {
  gold: '#f5a623',
  green: '#10b981',
  dim: '#475569',
  upset: '#fbbf24',
  diff: 'rgba(139,92,246,0.7)',
  line: 'rgba(255,255,255,0.06)',
};

const BRACKET_SEEDS = [[1,16],[8,9],[5,12],[4,13],[6,11],[3,14],[7,10],[2,15]];

// ── Helpers ───────────────────────────────────────────────────────

function buildRegionTree(picks, region) {
  return {
    r64: picks.filter(p => p.region === region && p.round === 64),
    r32: picks.filter(p => p.region === region && p.round === 32),
    s16: picks.filter(p => p.region === region && p.round === 16),
    e8:  picks.filter(p => p.region === region && p.round === 8),
  };
}

function isDiffPick(game, diffs) {
  if (!diffs?.length) return false;
  return diffs.some(d => d.round === game.round && d.team_a === game.team_a && d.team_b === game.team_b);
}

function truncate(s, max = 11) {
  if (!s) return '—';
  return s.length > max ? s.slice(0, max - 1) + '.' : s;
}

// ── Team Slot ─────────────────────────────────────────────────────

function Slot({ x, y, seed, team, isWinner, isUpset, isDiff, isGlow, prob, delay, onClick }) {
  const bg = isWinner
    ? isUpset ? 'rgba(245,166,35,0.12)' : 'rgba(16,185,129,0.06)'
    : 'rgba(255,255,255,0.02)';
  const border = isDiff
    ? COLORS.diff
    : isUpset && isWinner ? 'rgba(245,166,35,0.35)'
    : isWinner ? 'rgba(16,185,129,0.2)'
    : 'rgba(255,255,255,0.04)';
  const textColor = isWinner ? '#fff' : '#64748b';
  const seedColor = isWinner
    ? isUpset ? COLORS.upset : COLORS.green
    : '#334155';

  return (
    <motion.g
      initial={{ opacity: 0 }}
      animate={{ opacity: isGlow === false ? 0.2 : 1 }}
      transition={{ delay, duration: 0.25 }}
      style={{ cursor: 'pointer' }}
      onClick={() => onClick?.(team)}
    >
      <rect
        x={x} y={y} width={SLOT_W} height={SLOT_H} rx={3}
        fill={bg} stroke={border} strokeWidth={isDiff ? 1.5 : 0.5}
      />
      {seed != null && (
        <text x={x + 4} y={y + SLOT_H / 2 + 1} dominantBaseline="middle"
          fill={seedColor} fontSize={8} fontFamily="monospace" fontWeight="700"
        >
          {seed}
        </text>
      )}
      <text x={x + 20} y={y + SLOT_H / 2 + 1} dominantBaseline="middle"
        fill={textColor} fontSize={9} fontFamily="monospace"
        fontWeight={isWinner ? '700' : '400'}
      >
        {truncate(team)}
      </text>
      {isWinner && prob != null && (
        <text x={x + SLOT_W - 4} y={y + SLOT_H / 2 + 1} dominantBaseline="middle"
          textAnchor="end" fill="#475569" fontSize={7} fontFamily="monospace"
        >
          {(prob * 100).toFixed(0)}%
        </text>
      )}
    </motion.g>
  );
}

// ── Region bracket (one quadrant) ─────────────────────────────────

function RegionSVG({ tree, ox, oy, side, diffs, highlightTeam, onTeamClick, baseDelay }) {
  const rounds = [tree.r64, tree.r32, tree.s16, tree.e8];
  const gamesPerRound = [8, 4, 2, 1];

  // Compute the total height for this region
  const pairH = SLOT_H * 2 + PAIR_GAP;
  const regionH = 8 * pairH + 7 * REGION_PAD;

  function slotX(ri) {
    if (side === 'left') return ox + ri * (SLOT_W + ROUND_GAP);
    return ox + (3 - ri) * (SLOT_W + ROUND_GAP);
  }

  function slotY(ri, gi) {
    const n = gamesPerRound[ri];
    const spacing = regionH / n;
    return oy + spacing * gi + (spacing - pairH) / 2;
  }

  const elements = [];
  const lines = [];

  // Draw connector lines
  for (let ri = 0; ri < 3; ri++) {
    const n = gamesPerRound[ri];
    for (let gi = 0; gi < n; gi += 2) {
      const topY = slotY(ri, gi) + SLOT_H + PAIR_GAP / 2;
      const botY = slotY(ri, gi + 1) + SLOT_H + PAIR_GAP / 2;
      const nextY = slotY(ri + 1, gi / 2) + SLOT_H + PAIR_GAP / 2;

      const fromX = side === 'left' ? slotX(ri) + SLOT_W : slotX(ri);
      const toX = side === 'left' ? slotX(ri + 1) : slotX(ri + 1) + SLOT_W;
      const midX = (fromX + toX) / 2;

      const d = `M${fromX},${topY} L${midX},${topY} L${midX},${botY} L${fromX},${botY} M${midX},${nextY} L${toX},${nextY}`;
      lines.push(
        <motion.path
          key={`line-${ri}-${gi}`}
          d={d} fill="none" stroke={COLORS.line} strokeWidth={0.8}
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ delay: baseDelay + ri * 0.25, duration: 0.4 }}
        />
      );
    }
  }

  // Draw game slots
  rounds.forEach((games, ri) => {
    games.forEach((game, gi) => {
      const x = slotX(ri);
      const y = slotY(ri, gi);
      const winA = game.winner === game.team_a;
      const diff = isDiffPick(game, diffs);
      const delay = baseDelay + ri * 0.25 + gi * 0.03;

      const hlTeamGames = highlightTeam
        ? (game.team_a === highlightTeam || game.team_b === highlightTeam || game.winner === highlightTeam)
        : null;

      elements.push(
        <Slot key={`${ri}-${gi}-a`}
          x={x} y={y} seed={game.seed_a} team={game.team_a}
          isWinner={winA} isUpset={game.is_upset && winA} isDiff={diff && winA}
          isGlow={hlTeamGames} prob={winA ? game.ml_prob_a : null}
          delay={delay} onClick={onTeamClick}
        />,
        <Slot key={`${ri}-${gi}-b`}
          x={x} y={y + SLOT_H + PAIR_GAP} seed={game.seed_b} team={game.team_b}
          isWinner={!winA} isUpset={game.is_upset && !winA} isDiff={diff && !winA}
          isGlow={hlTeamGames} prob={!winA ? (1 - (game.ml_prob_a ?? 0.5)) : null}
          delay={delay + 0.02} onClick={onTeamClick}
        />
      );
    });
  });

  return <>{lines}{elements}</>;
}

// ── Center (Final Four + Championship) ────────────────────────────

function CenterSVG({ picks, champion, allTeams, diffs, highlightTeam, onTeamClick }) {
  const ff = picks.filter(p => p.round === 4);
  const champ = picks.filter(p => p.round === 2);
  const cx = INNER_W / 2;
  const cy = INNER_H / 2;

  const champStats = allTeams?.find(t => t.team_name === champion);
  const elements = [];

  // FF Game 1 (top)
  if (ff[0]) {
    const g = ff[0];
    const y = cy - 100;
    const diff = isDiffPick(g, diffs);
    const winA = g.winner === g.team_a;
    elements.push(
      <Slot key="ff1a" x={cx - SLOT_W/2} y={y} seed={g.seed_a} team={g.team_a}
        isWinner={winA} isUpset={false} isDiff={diff && winA} isGlow={null}
        prob={g.ml_prob_a} delay={1.5} onClick={onTeamClick} />,
      <Slot key="ff1b" x={cx - SLOT_W/2} y={y + SLOT_H + PAIR_GAP} seed={g.seed_b} team={g.team_b}
        isWinner={!winA} isUpset={false} isDiff={diff && !winA} isGlow={null}
        prob={1-(g.ml_prob_a??0.5)} delay={1.52} onClick={onTeamClick} />
    );
  }

  // Champion badge
  if (champion) {
    elements.push(
      <motion.g key="champ"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 2.0, duration: 0.5 }}
      >
        <rect x={cx - 70} y={cy - 22} width={140} height={44} rx={8}
          fill="rgba(245,166,35,0.08)" stroke="rgba(245,166,35,0.5)" strokeWidth={1} />
        <text x={cx} y={cy - 8} textAnchor="middle" fill="#475569" fontSize={7}
          fontFamily="monospace" letterSpacing="2">CHAMPION</text>
        <text x={cx} y={cy + 10} textAnchor="middle" fill={COLORS.gold} fontSize={13}
          fontFamily="monospace" fontWeight="900">{truncate(champion, 14)}</text>
        {champStats && (
          <text x={cx} y={cy + 20} textAnchor="middle" fill="#475569" fontSize={7}
            fontFamily="monospace">{(champStats.champ_pct * 100).toFixed(1)}% sim</text>
        )}
      </motion.g>
    );
  }

  // FF Game 2 (bottom)
  if (ff[1]) {
    const g = ff[1];
    const y = cy + 56;
    const diff = isDiffPick(g, diffs);
    const winA = g.winner === g.team_a;
    elements.push(
      <Slot key="ff2a" x={cx - SLOT_W/2} y={y} seed={g.seed_a} team={g.team_a}
        isWinner={winA} isUpset={false} isDiff={diff && winA} isGlow={null}
        prob={g.ml_prob_a} delay={1.5} onClick={onTeamClick} />,
      <Slot key="ff2b" x={cx - SLOT_W/2} y={y + SLOT_H + PAIR_GAP} seed={g.seed_b} team={g.team_b}
        isWinner={!winA} isUpset={false} isDiff={diff && !winA} isGlow={null}
        prob={1-(g.ml_prob_a??0.5)} delay={1.52} onClick={onTeamClick} />
    );
  }

  return <>{elements}</>;
}

// ── Mobile region view ────────────────────────────────────────────

function MobileRegionTabs({ selected, onChange }) {
  return (
    <div className="flex gap-1 p-1 rounded-lg" style={{ backgroundColor: '#151d38' }}>
      {['East', 'South', 'West', 'Midwest'].map(r => (
        <button key={r} onClick={() => onChange(r)}
          className="font-mono text-xs px-3 py-1.5 rounded-md transition-all"
          style={{
            backgroundColor: selected === r ? 'rgba(245,166,35,0.15)' : 'transparent',
            color: selected === r ? COLORS.gold : COLORS.dim,
            border: selected === r ? '1px solid rgba(245,166,35,0.3)' : '1px solid transparent',
          }}
        >{r}</button>
      ))}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────

export default function InteractiveBracket({ safePicks, equityPicks, champion, diffs, allTeams }) {
  const [mode, setMode] = useState('equity');
  const [highlightTeam, setHighlightTeam] = useState(null);
  const [mobileRegion, setMobileRegion] = useState('East');
  const [scale, setScale] = useState(1);
  const containerRef = useRef(null);

  const picks = mode === 'safe' ? safePicks : equityPicks;
  const currentChampion = mode === 'safe'
    ? safePicks?.find(p => p.round === 2)?.winner
    : champion;

  const trees = useMemo(() => {
    if (!picks?.length) return null;
    return {
      East: buildRegionTree(picks, 'East'),
      South: buildRegionTree(picks, 'South'),
      West: buildRegionTree(picks, 'West'),
      Midwest: buildRegionTree(picks, 'Midwest'),
    };
  }, [picks]);

  // Auto-scale to fit container width
  useEffect(() => {
    function updateScale() {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth - 32; // padding
        setScale(Math.min(w / INNER_W, 1));
      }
    }
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, []);

  const handleTeamClick = (team) => {
    setHighlightTeam(prev => prev === team ? null : team);
  };

  if (!picks?.length || !trees) {
    return (
      <div className="text-center py-16 font-mono text-slate-500">
        No bracket data. Run a simulation first.
      </div>
    );
  }

  const activeDiffs = mode === 'equity' ? diffs : [];

  // Region positions (internal coordinates)
  const regionW = 4 * SLOT_W + 3 * ROUND_GAP; // ~528
  const leftX = 10;
  const rightX = INNER_W - regionW - 10;
  const regionH = INNER_H / 2 - 20;

  return (
    <section className="py-6">
      {/* Header + controls */}
      <div className="px-4 max-w-[1440px] mx-auto mb-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="h-7 w-1 rounded-full" style={{ backgroundColor: COLORS.gold }} />
            <h2 className="font-mono font-black text-xl text-white tracking-tight">
              BRACKET VIEW
            </h2>
          </div>
          <div className="flex items-center gap-4">
            {/* Safe / Equity toggle */}
            <div className="flex gap-1 p-0.5 rounded-lg" style={{ backgroundColor: '#151d38' }}>
              {['safe', 'equity'].map(key => (
                <button key={key} onClick={() => setMode(key)}
                  className="font-mono text-xs px-3 py-1 rounded-md transition-all uppercase"
                  style={{
                    backgroundColor: mode === key ? 'rgba(245,166,35,0.15)' : 'transparent',
                    color: mode === key ? COLORS.gold : COLORS.dim,
                    border: mode === key ? '1px solid rgba(245,166,35,0.3)' : '1px solid transparent',
                  }}
                >{key}</button>
              ))}
            </div>
            {highlightTeam && (
              <span className="font-mono text-xs text-slate-400">
                <strong className="text-white">{highlightTeam}</strong>
                <button onClick={() => setHighlightTeam(null)}
                  className="ml-2 text-slate-600 hover:text-white">clear</button>
              </span>
            )}
          </div>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-5 mt-3">
          <Legend color={COLORS.green} label="Favorite" />
          <Legend color={COLORS.upset} label="Upset" />
          <Legend color={COLORS.diff} label="Differs" />
        </div>
      </div>

      {/* Desktop: scaled SVG bracket */}
      <div ref={containerRef} className="hidden md:block px-4 max-w-[1440px] mx-auto">
        <div style={{
          width: INNER_W * scale,
          height: INNER_H * scale,
          overflow: 'hidden',
        }}>
          <svg
            viewBox={`0 0 ${INNER_W} ${INNER_H}`}
            width={INNER_W * scale}
            height={INNER_H * scale}
            style={{ display: 'block' }}
          >
            {/* Region labels */}
            <text x={leftX + 2} y={14} fill={COLORS.gold} fontSize={10}
              fontFamily="monospace" fontWeight="900" letterSpacing="3">EAST</text>
            <text x={leftX + 2} y={INNER_H/2 + 14} fill={COLORS.gold} fontSize={10}
              fontFamily="monospace" fontWeight="900" letterSpacing="3">SOUTH</text>
            <text x={rightX + regionW - 2} y={14} fill={COLORS.gold} fontSize={10}
              fontFamily="monospace" fontWeight="900" letterSpacing="3" textAnchor="end">WEST</text>
            <text x={rightX + regionW - 2} y={INNER_H/2 + 14} fill={COLORS.gold} fontSize={10}
              fontFamily="monospace" fontWeight="900" letterSpacing="3" textAnchor="end">MIDWEST</text>

            {/* Left regions */}
            <RegionSVG tree={trees.East} ox={leftX} oy={20} side="left"
              diffs={activeDiffs} highlightTeam={highlightTeam}
              onTeamClick={handleTeamClick} baseDelay={0} />
            <RegionSVG tree={trees.South} ox={leftX} oy={INNER_H/2 + 20} side="left"
              diffs={activeDiffs} highlightTeam={highlightTeam}
              onTeamClick={handleTeamClick} baseDelay={0.1} />

            {/* Right regions */}
            <RegionSVG tree={trees.West} ox={rightX} oy={20} side="right"
              diffs={activeDiffs} highlightTeam={highlightTeam}
              onTeamClick={handleTeamClick} baseDelay={0.05} />
            <RegionSVG tree={trees.Midwest} ox={rightX} oy={INNER_H/2 + 20} side="right"
              diffs={activeDiffs} highlightTeam={highlightTeam}
              onTeamClick={handleTeamClick} baseDelay={0.15} />

            {/* Center: Final Four + Championship */}
            <CenterSVG picks={picks} champion={currentChampion}
              allTeams={allTeams} diffs={activeDiffs}
              highlightTeam={highlightTeam} onTeamClick={handleTeamClick} />
          </svg>
        </div>
      </div>

      {/* Mobile: single region */}
      <div className="md:hidden px-4">
        <div className="flex justify-center mb-3">
          <MobileRegionTabs selected={mobileRegion} onChange={setMobileRegion} />
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${regionW + 20} ${INNER_H / 2}`}
            width="100%" style={{ minWidth: 320 }}>
            <RegionSVG tree={trees[mobileRegion]} ox={10} oy={10} side="left"
              diffs={activeDiffs} highlightTeam={highlightTeam}
              onTeamClick={handleTeamClick} baseDelay={0} />
          </svg>
        </div>
      </div>
    </section>
  );
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="inline-block rounded-full" style={{ width: 7, height: 7, backgroundColor: color }} />
      <span className="font-mono text-xs" style={{ color: COLORS.dim }}>{label}</span>
    </span>
  );
}
