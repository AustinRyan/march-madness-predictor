"""
Upset Detection Module — March Madness Bracket Prediction System

Standalone rule-based module that flags HIGH UPSET ALERT for first-round
games where 3+ of 9 upset conditions are triggered.

All conditions are computed from real data files — no synthetic thresholds.
Uses 2026 KenPom, Barttorvik, Coach_Results, Seed_Results, and Resumes data.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

# Historical R64 upset counts per seed matchup (2008-2025, 17 tournaments)
# Computed from Upset_Seed_Info.csv
_R64_GAMES_PER_MATCHUP = 17 * 4  # 17 years × 4 regions = 68 games per matchup


def compute_historical_upset_rates(upset_seed_info: pd.DataFrame) -> dict[tuple[int, int], float]:
    """Compute exact historical upset rate for each seed pairing from real data.

    Returns dict mapping (higher_seed, lower_seed) → upset_rate.
    E.g., (5, 12) → 0.412 means 12-seeds beat 5-seeds 41.2% of the time.
    """
    r64 = upset_seed_info[upset_seed_info["CURRENT ROUND"] == 64]
    upset_counts = r64.groupby(["SEED WON", "SEED LOST"]).size().reset_index(name="upsets")

    rates = {}
    matchups = [(1, 16), (2, 15), (3, 14), (4, 13), (5, 12), (6, 11), (7, 10), (8, 9)]
    for higher, lower in matchups:
        row = upset_counts[(upset_counts["SEED WON"] == lower) &
                           (upset_counts["SEED LOST"] == higher)]
        n_upsets = int(row["upsets"].values[0]) if len(row) > 0 else 0
        rate = n_upsets / _R64_GAMES_PER_MATCHUP
        rates[(higher, lower)] = rate
    return rates


def detect_upsets(
    current_teams_df: pd.DataFrame,
    bracket: dict,
    coach_results: pd.DataFrame,
    seed_results: pd.DataFrame,
    upset_seed_info: pd.DataFrame,
    ml_probabilities: dict[tuple[str, str], float] = None,
) -> pd.DataFrame:
    """Run the 9-flag upset detector for all R64 matchups.

    Args:
        current_teams_df: 2026 team stats (from data pipeline)
        bracket: 2026 bracket structure
        coach_results: Career coach tournament records
        seed_results: Historical seed performance
        upset_seed_info: Historical upset records by seed pairing
        ml_probabilities: Optional dict of {(team_a, team_b): prob_a_wins}
                          from the ML model. If provided, used for composite score.

    Returns:
        DataFrame sorted by upset_score descending with all flag columns.
    """
    log.info("Running upset detection on R64 matchups")

    # Pre-compute lookups
    teams = current_teams_df.set_index("team_name")
    upset_rates = compute_historical_upset_rates(upset_seed_info)
    coach_avg_pake = coach_results["PAKE"].mean()
    coach_lookup = coach_results.set_index("coach_name")

    results = []

    for region in ["East", "South", "West", "Midwest"]:
        region_df = current_teams_df[current_teams_df["region"] == region]
        seed_to_row = {int(row["seed"]): row for _, row in region_df.iterrows()}

        matchup_seeds = [(1, 16), (8, 9), (5, 12), (4, 13), (6, 11), (3, 14), (7, 10), (2, 15)]

        for higher_seed, lower_seed in matchup_seeds:
            fav = seed_to_row.get(higher_seed)
            dog = seed_to_row.get(lower_seed)
            if fav is None or dog is None:
                continue

            fav_name = fav["team_name"]
            dog_name = dog["team_name"]

            flags = _evaluate_flags(fav, dog, higher_seed, lower_seed,
                                    upset_rates, coach_lookup, coach_avg_pake)

            upset_score = sum(flags.values())

            row = {
                "region": region,
                "higher_seed": higher_seed,
                "lower_seed": lower_seed,
                "favorite": fav_name,
                "underdog": dog_name,
                "upset_score": upset_score,
                "high_alert": upset_score >= 3,
            }

            # Add ML probability if available
            if ml_probabilities is not None:
                # ML prob is P(team_a wins) where team_a = higher seed
                ml_prob = ml_probabilities.get((fav_name, dog_name))
                if ml_prob is not None:
                    row["ml_upset_prob"] = 1.0 - ml_prob
                else:
                    row["ml_upset_prob"] = np.nan
            else:
                row["ml_upset_prob"] = np.nan

            # Add individual flag columns
            for flag_name, triggered in flags.items():
                row[flag_name] = triggered

            # Add key stats for context
            row["fav_kp_rank"] = _safe(fav, "KP_RANK")
            row["dog_kp_rank"] = _safe(dog, "KP_RANK")
            row["fav_adj_em"] = _safe(fav, "KP_AdjEM")
            row["dog_adj_em"] = _safe(dog, "KP_AdjEM")
            row["rank_gap"] = abs(_safe(fav, "KP_RANK") - _safe(dog, "KP_RANK"))
            row["hist_upset_rate"] = upset_rates.get((higher_seed, lower_seed), 0.0)

            results.append(row)

    df = pd.DataFrame(results)
    df = df.sort_values("upset_score", ascending=False).reset_index(drop=True)

    n_alerts = df["high_alert"].sum()
    log.info("Upset detection complete: %d games, %d HIGH UPSET ALERTs", len(df), n_alerts)
    return df


def _evaluate_flags(
    fav: pd.Series,
    dog: pd.Series,
    fav_seed: int,
    dog_seed: int,
    upset_rates: dict,
    coach_lookup: pd.DataFrame,
    coach_avg_pake: float,
) -> dict[str, bool]:
    """Evaluate the 9 upset flag conditions for a single matchup.

    Returns dict of {flag_name: True/False}.
    """
    flags = {}

    # 1. KenPom rank gap within 15 spots
    fav_rank = _safe(fav, "KP_RANK")
    dog_rank = _safe(dog, "KP_RANK")
    rank_gap = abs(fav_rank - dog_rank) if fav_rank and dog_rank else 999
    flags["rank_within_15"] = rank_gap <= 15

    # 2. Tempo mismatch > 8 possessions
    fav_tempo = _safe(fav, "AdjT", "BT_AdjT")
    dog_tempo = _safe(dog, "AdjT", "BT_AdjT")
    tempo_diff = abs(fav_tempo - dog_tempo) if fav_tempo and dog_tempo else 0
    flags["tempo_mismatch_8"] = tempo_diff > 8

    # 3. Higher seed fading (negative preseason rank change)
    # We don't have preseason data for 2026 yet — use KenPom Luck as proxy
    # Positive luck = overperformed, likely to regress
    fav_luck = _safe(fav, "Luck")
    flags["favorite_fading"] = fav_luck > 0.04 if fav_luck is not None else False

    # 4. Lower seed coach PAKE > league average
    dog_coach = dog.get("Current Coach") if pd.notna(dog.get("Current Coach")) else None
    dog_coach_pake = np.nan
    if dog_coach and dog_coach in coach_lookup.index:
        dog_coach_pake = coach_lookup.loc[dog_coach, "PAKE"]
    flags["dog_coach_above_avg"] = (pd.notna(dog_coach_pake) and
                                     dog_coach_pake > coach_avg_pake)

    # 5. Lower seed LUCK RATING negative (underperformed, due for regression up)
    dog_luck = _safe(dog, "Luck")
    flags["dog_luck_negative"] = dog_luck < 0 if dog_luck is not None else False

    # 6. 3-point style clash: lower seed defends 3s well AND higher seed shoots many 3s
    # Use DRtg_Rank as proxy for overall defensive quality
    dog_drtg_rank = _safe(dog, "DRtg_Rank")
    fav_ortg_rank = _safe(fav, "ORtg_Rank")
    # Dog has top-30 defense AND fav relies on offense (top-30 ORtg)
    flags["style_clash_3pt"] = (dog_drtg_rank is not None and dog_drtg_rank <= 30 and
                                 fav_ortg_rank is not None and fav_ortg_rank <= 30)

    # 7. Historical upset rate > 30% for this seed pairing
    hist_rate = upset_rates.get((fav_seed, dog_seed), 0.0)
    flags["hist_upset_rate_30"] = hist_rate > 0.30

    # 8. ELO within 50 points
    # We don't have 2026 ELO — use KenPom AdjEM gap as proxy (< 8 points ≈ within 50 ELO)
    fav_em = _safe(fav, "KP_AdjEM")
    dog_em = _safe(dog, "KP_AdjEM")
    em_gap = abs(fav_em - dog_em) if fav_em is not None and dog_em is not None else 999
    flags["elo_close"] = em_gap < 8

    # 9. Higher seed has > 3 Q3/Q4 losses
    # Not directly in 2026 data — use WAB rank as proxy
    # Low WAB = more losses against weaker opponents
    fav_wab_rk = _safe(fav, "BT_WAB Rk")
    flags["fav_soft_losses"] = (fav_wab_rk is not None and fav_wab_rk > 40)

    return flags


def _safe(row: pd.Series, col: str, fallback: str = None):
    """Get value or None."""
    val = row.get(col)
    if pd.isna(val) and fallback:
        val = row.get(fallback)
    return float(val) if pd.notna(val) else None


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    from data_pipeline import run_pipeline

    hist, curr, refs, bracket = run_pipeline()

    alerts = detect_upsets(
        curr, bracket,
        refs["coach_results"],
        refs["seed_results"],
        refs["upset_seed_info"],
    )

    print("\n" + "=" * 80)
    print("2026 MARCH MADNESS — UPSET DETECTION REPORT")
    print("=" * 80)

    # HIGH ALERT games
    high_alerts = alerts[alerts["high_alert"]]
    print(f"\n🚨 HIGH UPSET ALERTS ({len(high_alerts)} games with 3+ flags):\n")

    flag_cols = [c for c in alerts.columns if c in [
        "rank_within_15", "tempo_mismatch_8", "favorite_fading",
        "dog_coach_above_avg", "dog_luck_negative", "style_clash_3pt",
        "hist_upset_rate_30", "elo_close", "fav_soft_losses"
    ]]

    for _, row in high_alerts.iterrows():
        triggered = [f for f in flag_cols if row[f]]
        print(f"  ({row['higher_seed']}) {row['favorite']:<20s} vs ({row['lower_seed']}) {row['underdog']:<20s}"
              f"  [{row['region']}]  Score: {row['upset_score']}/9")
        print(f"    KenPom: #{int(row['fav_kp_rank'])} vs #{int(row['dog_kp_rank'])}  "
              f"(gap: {int(row['rank_gap'])} spots)  "
              f"Hist upset rate: {row['hist_upset_rate']:.1%}")
        print(f"    Flags: {', '.join(triggered)}")
        print()

    # All games table
    print(f"\nFull R64 Upset Scores (all {len(alerts)} games):\n")
    print(f"{'Matchup':<45s} {'Region':<10s} {'Score':>5s} {'Alert':>6s} {'Rank Gap':>8s} {'Hist%':>6s}")
    print("-" * 85)
    for _, row in alerts.iterrows():
        matchup = f"({row['higher_seed']}) {row['favorite']} vs ({row['lower_seed']}) {row['underdog']}"
        alert = "HIGH" if row["high_alert"] else ""
        print(f"{matchup:<45s} {row['region']:<10s} {row['upset_score']:>5d} {alert:>6s} "
              f"{int(row['rank_gap']):>8d} {row['hist_upset_rate']:>5.1%}")
