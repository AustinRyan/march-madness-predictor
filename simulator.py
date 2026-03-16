"""
Monte Carlo Bracket Simulator — March Madness Bracket Prediction System

Runs 50,000 full tournament simulations using calibrated ML win probabilities.
Blends equity-adjusted probabilities for later rounds based on --risk parameter.

Each simulation samples game winners using probabilities as coin flips,
producing round-by-round advancement rates, championship frequencies,
and score distributions.
"""

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_N_SIMS = 50_000

# Standard bracket scoring: 10 pts R64, 20 R32, 40 S16, 80 E8, 160 F4, 320 Champ
ROUND_POINTS = {64: 10, 32: 20, 16: 40, 8: 80, 4: 160, 2: 320}


def simulate_tournament(
    bracket: dict,
    predict_fn,
    current_teams_df: pd.DataFrame,
    equity_df: pd.DataFrame = None,
    n_sims: int = DEFAULT_N_SIMS,
    risk: float = 0.3,
    seed_results: pd.DataFrame = None,
) -> dict:
    """Run Monte Carlo tournament simulation.

    Args:
        bracket: 2026 bracket structure from bracket_2026.json
        predict_fn: Function(team_a_row, team_b_row, round_num, seed_results)
                    → float (probability team_a wins). Should use the ML model.
        current_teams_df: 2026 team stats
        equity_df: Pool equity scores (optional, for equity blending)
        n_sims: Number of simulations (default 50,000)
        risk: Risk parameter 0.0-1.0 (higher = more equity weighting)
        seed_results: For feature computation in predict_fn

    Returns:
        Dict with simulation results:
        - "team_results": DataFrame with per-team advancement rates
        - "champion_counts": Dict of team → championship count
        - "final_four_counts": Dict of team → F4 appearance count
        - "bracket_results": List of bracket outcomes per simulation
        - "n_sims": Number of simulations run
        - "risk": Risk level used
    """
    log.info("Starting Monte Carlo simulation: %d tournaments, risk=%.2f", n_sims, risk)

    # Build team lookup
    teams_lookup = current_teams_df.set_index("team_name")

    # Build equity lookup: {(team_name, round): raw_equity}
    equity_lookup = {}
    if equity_df is not None:
        for _, row in equity_df.iterrows():
            equity_lookup[(row["team_name"], int(row["round"]))] = row["raw_equity"]

    # Parse bracket into region matchup structures
    regions = {}
    for region_name in ["East", "South", "West", "Midwest"]:
        region_teams = _parse_region(bracket, region_name, current_teams_df)
        regions[region_name] = region_teams

    # Pre-compute win probabilities for all possible matchups
    # This avoids calling the model 50k × 63 times
    log.info("Pre-computing pairwise win probabilities...")
    all_teams = list(teams_lookup.index)
    prob_cache = {}
    for i, team_a in enumerate(all_teams):
        for team_b in all_teams[i + 1:]:
            if team_a not in teams_lookup.index or team_b not in teams_lookup.index:
                continue
            row_a = teams_lookup.loc[team_a]
            row_b = teams_lookup.loc[team_b]
            prob = predict_fn(row_a, row_b, 64, seed_results)
            prob_cache[(team_a, team_b)] = prob
            prob_cache[(team_b, team_a)] = 1.0 - prob
    log.info("Cached %d pairwise probabilities", len(prob_cache))

    # Tracking arrays
    team_names = list(teams_lookup.index)
    advance_counts = {t: {64: 0, 32: 0, 16: 0, 8: 0, 4: 0, 2: 0, "champ": 0}
                      for t in team_names}
    champion_counts = {}
    score_totals = {t: 0.0 for t in team_names}

    # Run simulations
    rng = np.random.default_rng(seed=42)

    for sim in range(n_sims):
        # Simulate each region through Elite 8
        final_four = {}
        sim_advances = {}

        for region_name, region_teams in regions.items():
            region_winner, region_advances = _simulate_region(
                region_teams, prob_cache, equity_lookup, risk, rng
            )
            final_four[region_name] = region_winner
            sim_advances.update(region_advances)

        # Final Four: East vs South, West vs Midwest (standard bracket)
        # All four FF teams reached round 4 (from region wins)
        for ff_team in final_four.values():
            sim_advances[ff_team] = min(sim_advances.get(ff_team, 999), 4)

        ff_game1 = _sim_game(final_four["East"], final_four["South"],
                             prob_cache, equity_lookup, 4, risk, rng)
        ff_game2 = _sim_game(final_four["West"], final_four["Midwest"],
                             prob_cache, equity_lookup, 4, risk, rng)

        # FF winners reach championship game (round 2)
        sim_advances[ff_game1] = 2
        sim_advances[ff_game2] = 2

        # Championship
        champion = _sim_game(ff_game1, ff_game2, prob_cache, equity_lookup, 2, risk, rng)
        sim_advances[champion] = 1

        # Record results
        champion_counts[champion] = champion_counts.get(champion, 0) + 1

        # Count advancement: lower furthest_round = deeper run
        # furthest_round=64 means lost in R64, =32 means won R64 (reached R32), etc.
        # =1 means won championship
        for team, furthest_round in sim_advances.items():
            for rd in [64, 32, 16, 8, 4, 2]:
                if furthest_round <= rd:
                    advance_counts[team][rd] += 1
            if furthest_round <= 1:
                advance_counts[team]["champ"] += 1

    # Build results DataFrame
    rows = []
    for team in team_names:
        seed = teams_lookup.loc[team].get("seed", 0)
        region = teams_lookup.loc[team].get("region", "")
        row = {
            "team_name": team,
            "seed": int(seed),
            "region": region,
        }
        for rd in [64, 32, 16, 8, 4, 2]:
            row[f"R{rd}_pct"] = advance_counts[team][rd] / n_sims
        row["champ_pct"] = advance_counts[team]["champ"] / n_sims
        rows.append(row)

    results_df = pd.DataFrame(rows)
    results_df = results_df.sort_values("champ_pct", ascending=False).reset_index(drop=True)

    # Log top results
    log.info("Simulation complete. Top 10 championship contenders:")
    for _, row in results_df.head(10).iterrows():
        log.info("  (%d) %-20s  Champ: %.1f%%  F4: %.1f%%  S16: %.1f%%",
                 row["seed"], row["team_name"],
                 row["champ_pct"] * 100, row["R4_pct"] * 100, row["R16_pct"] * 100)

    return {
        "team_results": results_df,
        "champion_counts": champion_counts,
        "n_sims": n_sims,
        "risk": risk,
    }


# =========================================================================
# Internal simulation helpers
# =========================================================================

def _parse_region(bracket: dict, region_name: str,
                  current_teams_df: pd.DataFrame) -> list[str]:
    """Parse a region into an ordered list of 16 team names for bracket simulation.

    Returns teams in bracket order: [1-seed, 16-seed, 8-seed, 9-seed,
    5-seed, 12-seed, 4-seed, 13-seed, 6-seed, 11-seed, 3-seed, 14-seed,
    7-seed, 10-seed, 2-seed, 15-seed].
    """
    bracket_order = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]
    region_df = current_teams_df[current_teams_df["region"] == region_name]
    seed_to_name = {int(row["seed"]): row["team_name"] for _, row in region_df.iterrows()}

    ordered = []
    for seed in bracket_order:
        name = seed_to_name.get(seed, f"Unknown-{seed}")
        ordered.append(name)
    return ordered


def _simulate_region(
    teams: list[str],
    prob_cache: dict,
    equity_lookup: dict,
    risk: float,
    rng: np.random.Generator,
) -> tuple[str, dict[str, int]]:
    """Simulate a single region from R64 through Elite 8.

    Returns (region_winner, {team: furthest_round_reached}).
    """
    advances = {}

    # R64: 8 games (pairs of consecutive teams in bracket order)
    r64_winners = []
    for i in range(0, 16, 2):
        winner = _sim_game(teams[i], teams[i + 1], prob_cache, equity_lookup,
                           64, risk, rng)
        r64_winners.append(winner)
        # Both teams at least played in R64
        advances[teams[i]] = 64
        advances[teams[i + 1]] = 64
        advances[winner] = 32  # winner advances to R32

    # R32: 4 games
    r32_winners = []
    for i in range(0, 8, 2):
        winner = _sim_game(r64_winners[i], r64_winners[i + 1], prob_cache,
                           equity_lookup, 32, risk, rng)
        r32_winners.append(winner)
        advances[winner] = 16

    # S16: 2 games
    s16_winners = []
    for i in range(0, 4, 2):
        winner = _sim_game(r32_winners[i], r32_winners[i + 1], prob_cache,
                           equity_lookup, 16, risk, rng)
        s16_winners.append(winner)
        advances[winner] = 8

    # E8: 1 game
    region_winner = _sim_game(s16_winners[0], s16_winners[1], prob_cache,
                              equity_lookup, 8, risk, rng)
    advances[region_winner] = 4  # advances to Final Four

    return region_winner, advances


def _sim_game(
    team_a: str,
    team_b: str,
    prob_cache: dict,
    equity_lookup: dict,
    round_num: int,
    risk: float,
    rng: np.random.Generator,
) -> str:
    """Simulate a single game using ML probability + equity blending."""
    # Get base ML probability
    base_prob = prob_cache.get((team_a, team_b), 0.5)

    # Apply equity adjustment for later rounds
    if risk > 0 and round_num <= 16:
        eq_a = equity_lookup.get((team_a, round_num), 1.0)
        eq_b = equity_lookup.get((team_b, round_num), 1.0)

        # Equity-adjusted probability: shift toward higher-equity team
        if eq_a + eq_b > 0:
            equity_shift = (eq_a - eq_b) / (eq_a + eq_b)  # -1 to +1
            # Risk controls how much equity shifts the probability
            adjusted_prob = base_prob + risk * equity_shift * 0.15
            # Clamp to valid range
            adjusted_prob = np.clip(adjusted_prob, 0.02, 0.98)
        else:
            adjusted_prob = base_prob
    else:
        adjusted_prob = base_prob

    # Sample outcome
    return team_a if rng.random() < adjusted_prob else team_b


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    from data_pipeline import run_pipeline
    from features import build_matchup_features_2026, FEATURE_NAMES
    from model import load_trained_models, predict_matchup
    from pool_equity import compute_all_equity

    hist, curr, refs, bracket = run_pipeline()

    # Load trained ML models
    models, config = load_trained_models()

    # Build prediction function that uses the ML model
    def ml_predict(team_a_row, team_b_row, round_num, seed_results):
        feats = build_matchup_features_2026(team_a_row, team_b_row, round_num,
                                             seed_results)
        return predict_matchup(models, feats.values)

    # Compute equity scores
    picks = refs["public_picks_2026"]
    equity_df = compute_all_equity(curr, picks)

    # Run simulation
    results = simulate_tournament(
        bracket=bracket,
        predict_fn=ml_predict,
        current_teams_df=curr,
        equity_df=equity_df,
        n_sims=50_000,
        risk=0.3,
        seed_results=refs["seed_results"],
    )

    # Print results
    df = results["team_results"]
    print("\n" + "=" * 90)
    print("2026 MARCH MADNESS — MONTE CARLO SIMULATION RESULTS (50,000 tournaments)")
    print(f"Risk level: {results['risk']}")
    print("=" * 90)

    print(f"\nCHAMPIONSHIP CONTENDERS (top 20):\n")
    print(f"{'Team':<22s} {'Seed':>4s} {'Region':<10s} {'R32':>6s} {'S16':>6s} "
          f"{'E8':>6s} {'F4':>6s} {'Champ':>6s}")
    print("-" * 70)
    for _, row in df.head(20).iterrows():
        print(f"{row['team_name']:<22s} {int(row['seed']):>4d} {row['region']:<10s} "
              f"{row['R32_pct']:>5.1%} {row['R16_pct']:>5.1%} "
              f"{row['R8_pct']:>5.1%} {row['R4_pct']:>5.1%} "
              f"{row['champ_pct']:>5.1%}")

    print(f"\nFINAL FOUR MOST LIKELY:\n")
    for region in ["East", "South", "West", "Midwest"]:
        region_df = df[df["region"] == region].sort_values("R4_pct", ascending=False)
        top = region_df.iloc[0]
        print(f"  {region:<10s}: ({int(top['seed'])}) {top['team_name']:<20s} "
              f"F4: {top['R4_pct']:.1%}  Champ: {top['champ_pct']:.1%}")

    print(f"\nUPSET WATCH — teams seeded 9+ with >5% S16 rate:\n")
    underdogs = df[(df["seed"] >= 9) & (df["R16_pct"] > 0.05)].sort_values(
        "R16_pct", ascending=False)
    for _, row in underdogs.iterrows():
        print(f"  ({int(row['seed'])}) {row['team_name']:<20s}  "
              f"R32: {row['R32_pct']:.1%}  S16: {row['R16_pct']:.1%}")
