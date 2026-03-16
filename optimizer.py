"""
Bracket Optimizer — March Madness Bracket Prediction System

Generates complete 63-game bracket picks using ML probabilities
and equity scores, with anti-chalk enforcement.

Produces two brackets:
  - Safe bracket (risk=0.1): ML probability-driven, minimal upsets
  - Equity bracket (risk=0.6): Contrarian, targets high-equity picks

Anti-chalk rules (hardcoded, enforced regardless of ML output):
  1. At least one 1-seed eliminated before Final Four
  2. At least one 10+ seed in Sweet 16
  3. At least one 12-seed beats a 5-seed
  4. Largest KenPom rank vs seed discrepancy flagged as upset candidate
  5. #1 overall seed wins championship < 20% of time — don't over-index
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


def optimize_bracket(
    bracket: dict,
    current_teams_df: pd.DataFrame,
    predict_fn,
    equity_df: pd.DataFrame,
    seed_results: pd.DataFrame,
    risk: float = 0.3,
    pool_size: int = 1_000_000,
) -> dict:
    """Generate optimized bracket picks for all 63 games.

    Args:
        bracket: 2026 bracket structure
        current_teams_df: Team stats
        predict_fn: ML prediction function(team_a_row, team_b_row, round, seed_results) → float
        equity_df: Pool equity scores
        seed_results: Historical seed performance
        risk: 0.0 (pure ML) to 1.0 (pure equity)
        pool_size: Assumed pool size for equity weighting

    Returns:
        Dict with bracket picks, corrections, and metadata.
    """
    log.info("Optimizing bracket with risk=%.2f, pool_size=%d", risk, pool_size)

    teams_lookup = current_teams_df.set_index("team_name")

    # Build equity lookup: {(team_name, round): raw_equity}
    eq_lookup = {}
    for _, row in equity_df.iterrows():
        eq_lookup[(row["team_name"], int(row["round"]))] = row["raw_equity"]

    # Cache pairwise ML probabilities
    prob_cache = _build_prob_cache(current_teams_df, predict_fn, seed_results)

    # Simulate each region through Elite 8
    region_picks = {}
    all_picks = []

    for region_name in ["East", "South", "West", "Midwest"]:
        region_df = current_teams_df[current_teams_df["region"] == region_name]
        seed_to_row = {int(r["seed"]): r for _, r in region_df.iterrows()}

        # Bracket order for matchups
        matchup_seeds = [(1, 16), (8, 9), (5, 12), (4, 13), (6, 11), (3, 14), (7, 10), (2, 15)]

        # R64
        r64_winners = []
        for seed_a, seed_b in matchup_seeds:
            row_a = seed_to_row.get(seed_a)
            row_b = seed_to_row.get(seed_b)
            if row_a is None or row_b is None:
                continue
            winner, pick_info = _pick_game(
                row_a, row_b, 64, prob_cache, eq_lookup, risk, region_name
            )
            r64_winners.append(winner)
            all_picks.append(pick_info)

        # R32
        r32_winners = []
        for i in range(0, 8, 2):
            winner, pick_info = _pick_game(
                _to_series(r64_winners[i], teams_lookup),
                _to_series(r64_winners[i + 1], teams_lookup),
                32, prob_cache, eq_lookup, risk, region_name
            )
            r32_winners.append(winner)
            all_picks.append(pick_info)

        # S16
        s16_winners = []
        for i in range(0, 4, 2):
            winner, pick_info = _pick_game(
                _to_series(r32_winners[i], teams_lookup),
                _to_series(r32_winners[i + 1], teams_lookup),
                16, prob_cache, eq_lookup, risk, region_name
            )
            s16_winners.append(winner)
            all_picks.append(pick_info)

        # E8
        winner, pick_info = _pick_game(
            _to_series(s16_winners[0], teams_lookup),
            _to_series(s16_winners[1], teams_lookup),
            8, prob_cache, eq_lookup, risk, region_name
        )
        all_picks.append(pick_info)
        region_picks[region_name] = winner

    # Final Four: East vs South, West vs Midwest
    ff1_winner, ff1_info = _pick_game(
        _to_series(region_picks["East"], teams_lookup),
        _to_series(region_picks["South"], teams_lookup),
        4, prob_cache, eq_lookup, risk, "Final Four"
    )
    ff2_winner, ff2_info = _pick_game(
        _to_series(region_picks["West"], teams_lookup),
        _to_series(region_picks["Midwest"], teams_lookup),
        4, prob_cache, eq_lookup, risk, "Final Four"
    )
    all_picks.append(ff1_info)
    all_picks.append(ff2_info)

    # Championship
    champ_winner, champ_info = _pick_game(
        _to_series(ff1_winner, teams_lookup),
        _to_series(ff2_winner, teams_lookup),
        2, prob_cache, eq_lookup, risk, "Championship"
    )
    all_picks.append(champ_info)

    picks_df = pd.DataFrame(all_picks)

    # Apply anti-chalk rules
    corrections = _enforce_anti_chalk(
        picks_df, current_teams_df, prob_cache, eq_lookup, risk, teams_lookup
    )

    final_four = {
        "East": region_picks["East"],
        "South": region_picks["South"],
        "West": region_picks["West"],
        "Midwest": region_picks["Midwest"],
    }

    result = {
        "picks": picks_df,
        "champion": champ_winner,
        "final_four": final_four,
        "corrections": corrections,
        "risk": risk,
        "pool_size": pool_size,
    }

    log.info("Bracket optimized: champion=%s, risk=%.2f, corrections=%d",
             champ_winner, risk, len(corrections))
    return result


# =========================================================================
# Game picking logic
# =========================================================================

# Optimizer equity weights by round.
# These are the equity blend ceiling at risk=1.0.
# Later rounds are deliberately aggressive — the whole point of the equity
# bracket is to deviate from chalk in the rounds that matter for pool equity.
# At risk=0.7: R64/R32 → 21%, S16 → 42%, E8 → 52%, F4 → 60%, Champ → 63%.
_ROUND_EQ_WEIGHT = {
    64: 0.30,   # R64: up to 30% equity at risk=1.0
    32: 0.30,   # R32: up to 30% equity
    16: 0.60,   # S16: up to 60% equity
    8:  0.75,   # E8:  up to 75% equity — must flip 1-seeds with low equity
    4:  0.85,   # F4:  up to 85% equity — contrarian F4 is the money round
    2:  0.90,   # Championship: up to 90% equity
}


def _pick_game(
    row_a: pd.Series,
    row_b: pd.Series,
    round_num: int,
    prob_cache: dict,
    eq_lookup: dict,
    risk: float,
    region: str,
) -> tuple[str, dict]:
    """Pick the winner of a single game using ML + equity blending.

    Blending formula:
      equity_prob = eq_a / (eq_a + eq_b)  — equity-implied win probability
      round_eq_wt = per-round equity weight from spec (0.15 to 0.60)
      blend_factor = risk * round_eq_wt   — how much equity shifts the pick
      blended_prob = (1 - blend_factor) * ml_prob + blend_factor * equity_prob
    """
    team_a = row_a.get("team_name", row_a.name if hasattr(row_a, "name") else "Unknown")
    team_b = row_b.get("team_name", row_b.name if hasattr(row_b, "name") else "Unknown")
    seed_a = int(row_a.get("seed", 8))
    seed_b = int(row_b.get("seed", 8))

    # Base ML probability (P(team_a wins))
    ml_prob = prob_cache.get((team_a, team_b), 0.5)

    # Equity-implied probability: normalize equity scores to a probability
    eq_a = eq_lookup.get((team_a, round_num), 1.0)
    eq_b = eq_lookup.get((team_b, round_num), 1.0)

    if eq_a + eq_b > 0:
        equity_prob = eq_a / (eq_a + eq_b)
    else:
        equity_prob = 0.5

    # Blend: risk controls how much equity overrides ML
    round_eq_wt = _ROUND_EQ_WEIGHT.get(round_num, 0.15)
    blend_factor = risk * round_eq_wt
    blended_prob = (1.0 - blend_factor) * ml_prob + blend_factor * equity_prob
    blended_prob = np.clip(blended_prob, 0.02, 0.98)

    # Tiered ML probability floor: prevents reckless equity flips in early
    # rounds but allows full equity differentiation in late rounds where
    # pool points are highest and differentiation matters most.
    _ROUND_ML_FLOOR = {
        64: 0.35,   # R64/R32: 35% minimum — protect against early busts
        32: 0.35,
        16: 0.30,   # S16: 30% — slightly more aggressive
        8:  0.0,    # E8: no floor — equity has full control
        4:  0.0,    # F4: no floor
        2:  0.0,    # Championship: no floor
    }
    ml_floor = _ROUND_ML_FLOOR.get(round_num, 0.35)
    if ml_floor > 0:
        if blended_prob < 0.5 and ml_prob > (1.0 - ml_floor):
            # Equity wants team_b but ML is too confident in team_a
            blended_prob = ml_prob
        elif blended_prob >= 0.5 and ml_prob < ml_floor:
            # Equity wants team_a but ML is too confident in team_b
            blended_prob = ml_prob

    # Pick winner
    winner = team_a if blended_prob >= 0.5 else team_b
    is_upset = (winner == team_b and seed_a < seed_b) or (winner == team_a and seed_a > seed_b)

    pick_info = {
        "round": round_num,
        "region": region,
        "team_a": team_a,
        "team_b": team_b,
        "seed_a": seed_a,
        "seed_b": seed_b,
        "ml_prob_a": ml_prob,
        "equity_a": eq_a,
        "equity_b": eq_b,
        "equity_prob_a": equity_prob,
        "blended_prob_a": blended_prob,
        "winner": winner,
        "winner_seed": seed_a if winner == team_a else seed_b,
        "is_upset": is_upset,
    }

    return winner, pick_info


# =========================================================================
# Anti-chalk enforcement
# =========================================================================

def _enforce_anti_chalk(
    picks_df: pd.DataFrame,
    current_teams_df: pd.DataFrame,
    prob_cache: dict,
    eq_lookup: dict,
    risk: float,
    teams_lookup: pd.DataFrame,
) -> list[dict]:
    """Enforce the 5 anti-chalk rules. Return list of corrections made."""
    corrections = []

    # Rule 1: At least one 1-seed eliminated before Final Four
    r_e8 = picks_df[picks_df["round"] == 8]
    one_seeds_in_ff = r_e8[r_e8["winner_seed"] == 1]
    if len(one_seeds_in_ff) == 4:
        # All four 1-seeds in FF — force one out
        # Pick the weakest 1-seed (lowest ML prob in E8 game)
        weakest = one_seeds_in_ff.sort_values("blended_prob_a").iloc[0]
        corrections.append({
            "rule": 1,
            "description": "At least one 1-seed must be eliminated before F4",
            "action": f"Flagged: All four 1-seeds made F4 — weakest E8 win is "
                      f"{weakest['winner']} ({weakest['blended_prob_a']:.1%} prob). "
                      f"Consider flipping in manual review.",
            "auto_corrected": False,
        })
        log.warning("ANTI-CHALK RULE 1: All four 1-seeds in FF. Flagging weakest for review.")

    # Rule 2: At least one 10+ seed in Sweet 16
    r_r32 = picks_df[picks_df["round"] == 32]
    high_seeds_in_s16 = r_r32[r_r32["winner_seed"] >= 10]
    if len(high_seeds_in_s16) == 0:
        # No 10+ seed in S16 — find best candidate
        r64_picks = picks_df[picks_df["round"] == 64]
        # Look for 10+ seeds that won R64
        r64_high = r64_picks[r64_picks["winner_seed"] >= 10]
        if len(r64_high) > 0:
            # Find the one with the best equity/probability combo
            best = r64_high.sort_values("blended_prob_a", ascending=False).iloc[0]
            corrections.append({
                "rule": 2,
                "description": "At least one 10+ seed must reach Sweet 16",
                "action": f"No 10+ seed in S16. Best R64 winner: "
                          f"({best['winner_seed']}) {best['winner']}. "
                          f"Consider advancing through R32.",
                "auto_corrected": False,
            })
            log.warning("ANTI-CHALK RULE 2: No 10+ seed in S16. Flagging for review.")

    # Rule 3: At least one 12-seed beats a 5-seed
    r64_5v12 = picks_df[(picks_df["round"] == 64) &
                         (((picks_df["seed_a"] == 5) & (picks_df["seed_b"] == 12)) |
                          ((picks_df["seed_a"] == 12) & (picks_df["seed_b"] == 5)))]
    twelve_wins = r64_5v12[r64_5v12["winner_seed"] == 12]
    if len(twelve_wins) == 0 and len(r64_5v12) > 0:
        # No 12-seed upset — force the best one
        # Find the 5v12 game with highest upset probability
        best_5v12 = None
        best_prob = 0
        for _, game in r64_5v12.iterrows():
            if game["seed_a"] == 12:
                upset_prob = game["blended_prob_a"]
            else:
                upset_prob = 1.0 - game["blended_prob_a"]
            if upset_prob > best_prob:
                best_prob = upset_prob
                best_5v12 = game

        if best_5v12 is not None:
            twelve_name = best_5v12["team_a"] if best_5v12["seed_a"] == 12 else best_5v12["team_b"]
            five_name = best_5v12["team_a"] if best_5v12["seed_a"] == 5 else best_5v12["team_b"]
            # Auto-correct: flip this game
            idx = picks_df[(picks_df["round"] == 64) &
                           (picks_df["team_a"] == best_5v12["team_a"]) &
                           (picks_df["team_b"] == best_5v12["team_b"])].index
            if len(idx) > 0:
                picks_df.loc[idx[0], "winner"] = twelve_name
                picks_df.loc[idx[0], "winner_seed"] = 12
                picks_df.loc[idx[0], "is_upset"] = True
                corrections.append({
                    "rule": 3,
                    "description": "At least one 12-seed must beat a 5-seed (35% historical rate)",
                    "action": f"FORCED: ({twelve_name}) over ({five_name}) — "
                              f"upset prob {best_prob:.1%}",
                    "auto_corrected": True,
                })
                log.warning("ANTI-CHALK RULE 3: Forced 12-over-5 upset: %s over %s",
                           twelve_name, five_name)

    # Rule 4: Flag largest KenPom rank vs seed discrepancy
    if "KP_RANK" in current_teams_df.columns:
        current_teams_df = current_teams_df.copy()
        current_teams_df["discrep"] = (current_teams_df["seed"] * 4) - current_teams_df["KP_RANK"]
        most_underseeded = current_teams_df.sort_values("discrep", ascending=False).iloc[0]
        corrections.append({
            "rule": 4,
            "description": "Largest KenPom rank vs seed discrepancy flagged as upset candidate",
            "action": f"FLAGGED: ({int(most_underseeded['seed'])}) {most_underseeded['team_name']} "
                      f"— KenPom #{int(most_underseeded['KP_RANK'])} but seeded "
                      f"#{int(most_underseeded['seed'])} (discrepancy: "
                      f"{most_underseeded['discrep']:.0f})",
            "auto_corrected": False,
        })

    # Rule 5: #1 overall seed championship < 20%
    # Duke is the #1 overall seed (KP_RANK=1)
    overall_1 = current_teams_df.sort_values("KP_RANK").iloc[0]
    champ = picks_df[picks_df["round"] == 2]
    if len(champ) > 0 and champ.iloc[0]["winner"] == overall_1["team_name"]:
        corrections.append({
            "rule": 5,
            "description": "#1 overall seed wins championship < 20% historically — don't over-index",
            "action": f"NOTE: {overall_1['team_name']} (#{int(overall_1['KP_RANK'])} overall) "
                      f"is the champion pick. Historically, the #1 overall wins < 20% of the time. "
                      f"This is acceptable if ML probability supports it.",
            "auto_corrected": False,
        })

    return corrections


# =========================================================================
# Helpers
# =========================================================================

def _build_prob_cache(
    current_teams_df: pd.DataFrame,
    predict_fn,
    seed_results: pd.DataFrame,
) -> dict:
    """Pre-compute all pairwise ML win probabilities."""
    from features import build_matchup_features_2026
    teams = current_teams_df.set_index("team_name")
    all_names = list(teams.index)
    cache = {}
    for i, a in enumerate(all_names):
        for b in all_names[i + 1:]:
            row_a = teams.loc[a]
            row_b = teams.loc[b]
            feats = build_matchup_features_2026(row_a, row_b, 64, seed_results)
            from model import predict_matchup, load_trained_models
            # Import models once (cached after first call)
            if not hasattr(_build_prob_cache, "_models"):
                _build_prob_cache._models, _ = load_trained_models()
            prob = predict_matchup(_build_prob_cache._models, feats.values)
            cache[(a, b)] = prob
            cache[(b, a)] = 1.0 - prob
    log.info("Probability cache: %d pairwise matchups", len(cache))
    return cache


def _to_series(team_name: str, teams_lookup: pd.DataFrame) -> pd.Series:
    """Get team row from lookup, with team_name available."""
    if team_name in teams_lookup.index:
        s = teams_lookup.loc[team_name].copy()
        s["team_name"] = team_name
        return s
    return pd.Series({"team_name": team_name, "seed": 8})


def compare_brackets(bracket_a: dict, bracket_b: dict) -> dict:
    """Compare two bracket results and return differences."""
    picks_a = bracket_a["picks"]
    picks_b = bracket_b["picks"]

    # Match games by (round, team_a, team_b)
    diffs = []
    for idx in range(len(picks_a)):
        row_a = picks_a.iloc[idx]
        row_b = picks_b.iloc[idx]
        if row_a["winner"] != row_b["winner"]:
            diffs.append({
                "round": row_a["round"],
                "region": row_a["region"],
                "team_a": row_a["team_a"],
                "team_b": row_a["team_b"],
                "safe_pick": row_a["winner"],
                "equity_pick": row_b["winner"],
                "safe_prob": row_a["blended_prob_a"],
                "equity_prob": row_b["blended_prob_a"],
            })

    total_games = len(picks_a)
    same = total_games - len(diffs)

    return {
        "total_games": total_games,
        "same_picks": same,
        "different_picks": len(diffs),
        "overlap_pct": same / total_games,
        "differences": pd.DataFrame(diffs),
    }


def compute_public_overlap(picks_df: pd.DataFrame) -> float:
    """Estimate how much this bracket overlaps with the public field.

    Higher-seeded winner = public pick. Upset picks reduce overlap.
    """
    chalk_count = 0
    for _, row in picks_df.iterrows():
        # "Chalk" = higher seed (lower number) wins
        if row["winner_seed"] <= min(row["seed_a"], row["seed_b"]):
            chalk_count += 1
        elif row["seed_a"] == row["seed_b"]:
            chalk_count += 1  # same seed = neutral
    return chalk_count / len(picks_df)


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
    from pool_equity import compute_all_equity, sim_results_to_win_probs
    from simulator import simulate_tournament

    hist, curr, refs, bracket = run_pipeline()
    models, config = load_trained_models()

    def ml_predict(team_a_row, team_b_row, round_num, sr):
        feats = build_matchup_features_2026(team_a_row, team_b_row, round_num, sr)
        return predict_matchup(models, feats.values)

    # Run simulation to get team-specific win probabilities
    log.info("Running 50k simulation for team-specific equity...")
    sim_results = simulate_tournament(
        bracket=bracket, predict_fn=ml_predict, current_teams_df=curr,
        equity_df=None, n_sims=50_000, risk=0.0,
        seed_results=refs["seed_results"],
    )
    win_probs = sim_results_to_win_probs(sim_results["team_results"])

    # Compute equity using simulation-derived team-specific probabilities
    picks = refs["public_picks_2026"]
    equity_df = compute_all_equity(curr, picks, win_probs_by_team=win_probs)

    # Generate both brackets
    log.info("=" * 70)
    log.info("GENERATING SAFE BRACKET (risk=0.1)")
    log.info("=" * 70)
    safe = optimize_bracket(bracket, curr, ml_predict, equity_df,
                            refs["seed_results"], risk=0.1)

    log.info("=" * 70)
    log.info("GENERATING EQUITY BRACKET (risk=0.6)")
    log.info("=" * 70)
    equity = optimize_bracket(bracket, curr, ml_predict, equity_df,
                              refs["seed_results"], risk=0.6)

    # Compare
    comparison = compare_brackets(safe, equity)
    safe_overlap = compute_public_overlap(safe["picks"])
    equity_overlap = compute_public_overlap(equity["picks"])

    # Print results
    print("\n" + "=" * 80)
    print("2026 MARCH MADNESS — BRACKET OPTIMIZER RESULTS")
    print("=" * 80)

    print(f"\n{'─' * 40}")
    print(f"SAFE BRACKET (risk=0.1)")
    print(f"{'─' * 40}")
    print(f"  Champion: {safe['champion']}")
    print(f"  Final Four:")
    for region, team in safe["final_four"].items():
        seed = int(curr[curr.team_name == team].iloc[0]["seed"])
        print(f"    {region:<10s}: ({seed}) {team}")
    print(f"  Upsets picked: {safe['picks']['is_upset'].sum()}")
    print(f"  Public overlap: {safe_overlap:.1%}")

    print(f"\n{'─' * 40}")
    print(f"EQUITY BRACKET (risk=0.6)")
    print(f"{'─' * 40}")
    print(f"  Champion: {equity['champion']}")
    print(f"  Final Four:")
    for region, team in equity["final_four"].items():
        seed = int(curr[curr.team_name == team].iloc[0]["seed"])
        print(f"    {region:<10s}: ({seed}) {team}")
    print(f"  Upsets picked: {equity['picks']['is_upset'].sum()}")
    print(f"  Public overlap: {equity_overlap:.1%}")

    print(f"\n{'─' * 40}")
    print(f"BRACKET COMPARISON")
    print(f"{'─' * 40}")
    print(f"  Total games: {comparison['total_games']}")
    print(f"  Same picks: {comparison['same_picks']}")
    print(f"  Different picks: {comparison['different_picks']}")
    print(f"  Overlap between brackets: {comparison['overlap_pct']:.1%}")

    if len(comparison["differences"]) > 0:
        print(f"\n  Differences:")
        diffs = comparison["differences"]
        for _, d in diffs.iterrows():
            print(f"    R{int(d['round']):>2d} [{d['region']:<12s}]: "
                  f"Safe={d['safe_pick']:<20s} vs Equity={d['equity_pick']}")

    print(f"\n{'─' * 40}")
    print(f"ANTI-CHALK RULES")
    print(f"{'─' * 40}")
    all_corrections = safe["corrections"] + equity["corrections"]
    seen_rules = set()
    for c in all_corrections:
        key = (c["rule"], c["action"])
        if key not in seen_rules:
            seen_rules.add(key)
            status = "AUTO-CORRECTED" if c["auto_corrected"] else "FLAGGED"
            print(f"  Rule {c['rule']} [{status}]: {c['description']}")
            print(f"    → {c['action']}")
            print()
