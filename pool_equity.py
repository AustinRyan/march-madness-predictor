"""
Pool Equity Module — March Madness Bracket Prediction System

Computes equity scores that identify where the public is wrong.
Equity = True Win Probability / Public Pick Percentage.

High equity (>1.0) = the public is undervaluing this team.
Low equity (<1.0) = the public is overvaluing this team.

True win probabilities come from the Monte Carlo simulation
(team-specific, not seed-based), giving differentiated equity
even when public picks use seed-based priors.

Round-weighted blending:
  R64/R32:         85% win probability + 15% equity
  S16/E8:          55% win probability + 45% equity
  F4/Championship: 40% win probability + 60% equity
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

# Round-weighted blending coefficients: (win_prob_weight, equity_weight)
ROUND_WEIGHTS = {
    64: (0.85, 0.15),   # R64
    32: (0.85, 0.15),   # R32
    16: (0.55, 0.45),   # Sweet 16
    8:  (0.55, 0.45),   # Elite 8
    4:  (0.40, 0.60),   # Final Four
    2:  (0.40, 0.60),   # Championship
}

# Map round numbers to public pick column names
ROUND_TO_PICK_COL = {
    64: "R64",
    32: "R32",
    16: "S16",
    8:  "E8",
    4:  "F4",
    2:  "FINALS",
}


def sim_results_to_win_probs(sim_results: pd.DataFrame) -> dict[str, dict[int, float]]:
    """Convert simulation team_results DataFrame into per-team win probability dicts.

    The simulation gives advancement rates (R64_pct = made R64, R32_pct = made R32, etc.).
    For equity scoring, round N's "win prob" is the probability of WINNING that round's game,
    which equals the rate of advancing to the NEXT round. For example:
      - Round 64 win prob = R32_pct (probability of advancing past R64 into R32)
      - Round 32 win prob = R16_pct (probability of advancing past R32 into S16)

    Returns {team_name: {64: prob, 32: prob, 16: prob, 8: prob, 4: prob, 2: prob}}
    """
    col_map = {
        64: "R32_pct", 32: "R16_pct", 16: "R8_pct",
        8: "R4_pct", 4: "champ_pct", 2: "champ_pct",
    }
    probs = {}
    for _, row in sim_results.iterrows():
        name = row["team_name"]
        probs[name] = {}
        for round_num, col in col_map.items():
            probs[name][round_num] = float(row.get(col, 0.0))
    return probs


def load_public_picks(picks_df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Load and validate public pick percentages.

    Returns:
        picks: DataFrame with team_name and pick % columns
        is_estimated: True if using seed-based priors
    """
    is_estimated = False
    if "SOURCE" in picks_df.columns:
        is_estimated = (picks_df["SOURCE"] == "ESTIMATED_SEED_PRIOR").any()
        if is_estimated:
            log.info("Public picks: seed-based priors (equity differentiation comes from ML simulation)")

    # Ensure pick columns are float (already cleaned in data_pipeline, but be safe)
    pick_cols = ["R64", "R32", "S16", "E8", "F4", "FINALS"]
    for col in pick_cols:
        if col in picks_df.columns:
            picks_df[col] = pd.to_numeric(
                picks_df[col].astype(str).str.replace("%", ""), errors="coerce"
            )

    return picks_df, is_estimated


def compute_equity_scores(
    team_name: str,
    seed: int,
    win_probabilities: dict[int, float],
    picks_df: pd.DataFrame,
    is_estimated: bool,
) -> dict[int, dict]:
    """Compute equity scores for a single team across all rounds.

    Args:
        team_name: Canonical team name
        seed: Tournament seed
        win_probabilities: {round_num: ml_win_probability} from model
        picks_df: Public pick percentages DataFrame
        is_estimated: Whether public picks are estimated

    Returns:
        {round_num: {
            "win_prob": float,
            "public_pick_pct": float,
            "raw_equity": float,
            "blended_score": float,
            "estimated": bool,
        }}
    """
    # Look up this team's public pick percentages
    team_row = picks_df[picks_df["team_name"] == team_name]
    if len(team_row) == 0:
        # Team not in picks data — use seed-based fallback
        team_picks = _seed_fallback_picks(seed)
        is_estimated = True
    else:
        team_picks = team_row.iloc[0]

    results = {}
    for round_num in [64, 32, 16, 8, 4, 2]:
        pick_col = ROUND_TO_PICK_COL[round_num]
        win_prob = win_probabilities.get(round_num, 0.0)

        # Get public pick % (convert from percentage to proportion)
        public_pct = _get_pick_pct(team_picks, pick_col)

        # Equity = true probability / public pick percentage
        # Clip public_pct to avoid division by zero
        public_pct_safe = max(public_pct, 0.001)
        raw_equity = win_prob / public_pct_safe

        # Round-weighted blending
        wp_weight, eq_weight = ROUND_WEIGHTS[round_num]
        blended = wp_weight * win_prob + eq_weight * _normalize_equity(raw_equity)

        results[round_num] = {
            "win_prob": win_prob,
            "public_pick_pct": public_pct,
            "raw_equity": raw_equity,
            "blended_score": blended,
            "estimated": is_estimated,
        }

    return results


def compute_all_equity(
    teams_df: pd.DataFrame,
    picks_df: pd.DataFrame,
    win_probs_by_team: dict[str, dict[int, float]] = None,
) -> pd.DataFrame:
    """Compute equity scores for all bracket teams across all rounds.

    Args:
        teams_df: current_teams_df from data pipeline
        picks_df: Public picks DataFrame
        win_probs_by_team: {team_name: {round_num: win_prob}}
                           If None, uses seed-based baseline probabilities.

    Returns:
        DataFrame with equity scores per team per round.
    """
    picks_clean, is_estimated = load_public_picks(picks_df.copy())

    rows = []
    for _, team in teams_df.iterrows():
        name = team["team_name"]
        seed = int(team["seed"])
        region = team["region"]

        # Get win probabilities — use provided or generate seed-based defaults
        if win_probs_by_team and name in win_probs_by_team:
            win_probs = win_probs_by_team[name]
        else:
            win_probs = _seed_based_win_probs(seed)

        equity = compute_equity_scores(name, seed, win_probs, picks_clean, is_estimated)

        for round_num, scores in equity.items():
            rows.append({
                "team_name": name,
                "seed": seed,
                "region": region,
                "round": round_num,
                "round_name": ROUND_TO_PICK_COL[round_num],
                "win_prob": scores["win_prob"],
                "public_pick_pct": scores["public_pick_pct"],
                "raw_equity": scores["raw_equity"],
                "blended_score": scores["blended_score"],
                "estimated": scores["estimated"],
            })

    df = pd.DataFrame(rows)

    log.info("Equity scores computed: %d teams × %d rounds = %d rows",
             len(teams_df), 6, len(df))
    return df


def get_high_equity_picks(
    equity_df: pd.DataFrame,
    round_num: int,
    min_equity: float = 1.5,
    min_win_prob: float = 0.10,
) -> pd.DataFrame:
    """Get teams with high equity scores for a given round.

    These are teams the public is undervaluing relative to their
    true win probability — the optimal contrarian picks.
    """
    rd = equity_df[equity_df["round"] == round_num].copy()
    high_eq = rd[(rd["raw_equity"] >= min_equity) & (rd["win_prob"] >= min_win_prob)]
    return high_eq.sort_values("raw_equity", ascending=False)


# =========================================================================
# Helper functions
# =========================================================================

def _get_pick_pct(row: pd.Series, col: str) -> float:
    """Get public pick percentage as a proportion (0-1).

    The CSV stores values like "99.00%" (stripped to 99.0) and "0.727%" (stripped to 0.727).
    ALL values are percentages that need dividing by 100 to get proportions.
    """
    val = row.get(col, 0.0)
    if pd.isna(val):
        return 0.01
    val = float(val)
    # ALL values from the CSV are percentages (0-100 scale), convert to proportion
    # Values > 1.0 are clearly percentages (e.g., 99.0 → 0.99)
    # Values <= 1.0 are also percentages (e.g., 0.727 → 0.00727 = 0.727%)
    val = val / 100.0
    return max(val, 0.00001)


def _normalize_equity(raw_equity: float) -> float:
    """Normalize equity score to a 0-1 scale for blending.

    Maps raw equity through a sigmoid-like transformation:
    equity=1.0 → 0.5 (neutral), equity=2.0 → ~0.73, equity=3.0 → ~0.88
    """
    # Logistic transformation centered at equity=1.0
    return 1.0 / (1.0 + np.exp(-1.5 * (raw_equity - 1.0)))


def _seed_based_win_probs(seed: int) -> dict[int, float]:
    """Generate baseline win probabilities based on historical seed performance."""
    # Historical round-by-round advancement rates by seed (from Seed_Results)
    seed_probs = {
        1:  {64: 0.99, 32: 0.85, 16: 0.65, 8: 0.45, 4: 0.30, 2: 0.18},
        2:  {64: 0.94, 32: 0.75, 16: 0.50, 8: 0.30, 4: 0.15, 2: 0.07},
        3:  {64: 0.85, 32: 0.60, 16: 0.35, 8: 0.18, 4: 0.08, 2: 0.03},
        4:  {64: 0.80, 32: 0.50, 16: 0.28, 8: 0.12, 4: 0.05, 2: 0.02},
        5:  {64: 0.65, 32: 0.35, 16: 0.18, 8: 0.08, 4: 0.03, 2: 0.01},
        6:  {64: 0.63, 32: 0.30, 16: 0.15, 8: 0.06, 4: 0.02, 2: 0.01},
        7:  {64: 0.60, 32: 0.25, 16: 0.12, 8: 0.05, 4: 0.02, 2: 0.01},
        8:  {64: 0.50, 32: 0.20, 16: 0.08, 8: 0.03, 4: 0.01, 2: 0.005},
        9:  {64: 0.50, 32: 0.18, 16: 0.07, 8: 0.03, 4: 0.01, 2: 0.004},
        10: {64: 0.40, 32: 0.15, 16: 0.06, 8: 0.02, 4: 0.01, 2: 0.003},
        11: {64: 0.38, 32: 0.14, 16: 0.06, 8: 0.02, 4: 0.01, 2: 0.003},
        12: {64: 0.35, 32: 0.12, 16: 0.04, 8: 0.01, 4: 0.005, 2: 0.002},
        13: {64: 0.22, 32: 0.06, 16: 0.02, 8: 0.005, 4: 0.002, 2: 0.001},
        14: {64: 0.12, 32: 0.03, 16: 0.01, 8: 0.003, 4: 0.001, 2: 0.0005},
        15: {64: 0.07, 32: 0.02, 16: 0.005, 8: 0.002, 4: 0.001, 2: 0.0003},
        16: {64: 0.02, 32: 0.005, 16: 0.001, 8: 0.0005, 4: 0.0002, 2: 0.0001},
    }
    return seed_probs.get(seed, seed_probs[8])


def _seed_fallback_picks(seed: int) -> dict:
    """Fallback public pick percentages by seed for teams not in the picks file.

    Derived from BetMGM championship odds averages per seed group.
    """
    # Average implied championship probability by seed from BetMGM 2026
    champ_by_seed = {
        1: 0.118, 2: 0.038, 3: 0.022, 4: 0.014, 5: 0.010,
        6: 0.008, 7: 0.006, 8: 0.004, 9: 0.004, 10: 0.004,
        11: 0.004, 12: 0.004, 13: 0.004, 14: 0.004, 15: 0.004, 16: 0.004,
    }
    c = champ_by_seed.get(seed, 0.004)
    return {
        "R64": min(c * 80, 0.99), "R32": min(c * 35, 0.95),
        "S16": min(c * 18, 0.85), "E8": min(c * 10, 0.70),
        "F4": min(c * 5.5, 0.60), "FINALS": c,
    }


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    from data_pipeline import run_pipeline

    hist, curr, refs, bracket = run_pipeline()
    picks = refs["public_picks_2026"]

    # Compute equity using seed-based win probabilities (ML model not loaded here)
    equity_df = compute_all_equity(curr, picks)

    print("\n" + "=" * 80)
    print("2026 MARCH MADNESS — POOL EQUITY REPORT")
    if equity_df["estimated"].all():
        print("⚠️  ALL VALUES ARE ESTIMATED — using seed-based priors, not real ESPN public picks")
        print("⚠️  Real pick data available after bracket lock Thursday 12:15pm ET")
    print("=" * 80)

    # Show R64 equity scores
    r64 = equity_df[equity_df["round"] == 64].copy()
    r64 = r64.sort_values("raw_equity", ascending=False)

    print(f"\nR64 EQUITY SCORES (top 20 — highest equity = most undervalued):\n")
    print(f"{'Team':<22s} {'Seed':>4s} {'Region':<10s} {'Win%':>6s} {'Public':>7s} {'Equity':>7s} {'Blended':>8s}")
    print("-" * 70)
    for _, row in r64.head(20).iterrows():
        est = "*" if row["estimated"] else ""
        print(f"{row['team_name']:<22s} {int(row['seed']):>4d} {row['region']:<10s} "
              f"{row['win_prob']:>5.1%} {row['public_pick_pct']:>6.1%} "
              f"{row['raw_equity']:>7.2f}{est} {row['blended_score']:>7.3f}")

    # Show high-equity picks for later rounds
    for round_num, round_name in [(16, "Sweet 16"), (4, "Final Four")]:
        high = get_high_equity_picks(equity_df, round_num, min_equity=1.3)
        if len(high) > 0:
            print(f"\n{round_name} HIGH EQUITY PICKS (equity > 1.3):\n")
            for _, row in high.head(10).iterrows():
                est = "*" if row["estimated"] else ""
                print(f"  {row['team_name']:<22s} (seed {int(row['seed'])}) "
                      f"Win: {row['win_prob']:>5.1%}  Public: {row['public_pick_pct']:>5.1%}  "
                      f"Equity: {row['raw_equity']:.2f}{est}")
