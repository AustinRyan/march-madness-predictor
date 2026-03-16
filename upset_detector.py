"""
Upset Detection Module — March Madness Bracket Prediction System

Rule-based module that flags HIGH UPSET ALERT for games across ALL rounds
(R64, R32, S16, E8, F4) where 3+ of 9 upset conditions are triggered.

R64 matchups are known. R32+ matchups are based on the projected bracket
from the optimizer/simulator — actual opponents may differ.

All conditions are computed from real data files — no synthetic thresholds.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

# Number of tournaments in our data (2008-2025 minus 2020)
_N_TOURNAMENTS = 17
_GAMES_PER_MATCHUP_R64 = _N_TOURNAMENTS * 4  # 4 regions

ROUND_NAMES = {64: "R64", 32: "R32", 16: "S16", 8: "E8", 4: "F4", 2: "Championship"}


def compute_historical_upset_rates_by_round(
    upset_seed_info: pd.DataFrame,
) -> dict[tuple[int, int, int], float]:
    """Compute historical upset rate for each (round, higher_seed, lower_seed) triple.

    Returns dict mapping (round, higher_seed, lower_seed) → upset_rate.
    """
    rates = {}
    for rd in [64, 32, 16, 8, 4]:
        rd_upsets = upset_seed_info[upset_seed_info["CURRENT ROUND"] == rd]
        counts = rd_upsets.groupby(["SEED WON", "SEED LOST"]).size().reset_index(name="upsets")

        # Total games per seed matchup varies by round
        # R64: 4 per year, R32: 4 per year, S16: 4, E8: 4, F4: 2
        games_per_year = 4 if rd >= 8 else 2
        total_games = _N_TOURNAMENTS * games_per_year

        for _, row in counts.iterrows():
            higher = min(int(row["SEED WON"]), int(row["SEED LOST"]))
            lower = max(int(row["SEED WON"]), int(row["SEED LOST"]))
            upset_count = int(row["upsets"])
            # Only count if the lower seed (higher number) won
            if int(row["SEED WON"]) > int(row["SEED LOST"]):
                rates[(rd, higher, lower)] = upset_count / max(total_games, 1)

    return rates


def detect_upsets(
    current_teams_df: pd.DataFrame,
    bracket: dict,
    coach_results: pd.DataFrame,
    seed_results: pd.DataFrame,
    upset_seed_info: pd.DataFrame,
    ml_probabilities: dict[tuple[str, str], float] = None,
    projected_picks: list[dict] = None,
    vegas_lines: pd.DataFrame = None,
) -> pd.DataFrame:
    """Run the upset detector for ALL rounds (up to 11 conditions).

    9 base conditions use KenPom/Barttorvik/Coach/Seed data.
    2 additional conditions use Vegas lines (when available).

    For R64: uses bracket structure (known matchups).
    For R32+: uses projected_picks from the optimizer (projected matchups).

    Args:
        current_teams_df: 2026 team stats
        bracket: 2026 bracket structure
        coach_results: Career coach tournament records
        seed_results: Historical seed performance
        upset_seed_info: Historical upset records by seed pairing and round
        ml_probabilities: Optional {(team_a, team_b): prob_a_wins}
        projected_picks: List of pick dicts from optimizer (for R32+ matchups)
        vegas_lines: Optional DataFrame with spread/moneyline data for R64

    Returns:
        DataFrame sorted by round then upset_score, with all flag columns.
    """
    log.info("Running upset detection on ALL rounds")

    teams = current_teams_df.set_index("team_name")
    upset_rates = compute_historical_upset_rates_by_round(upset_seed_info)
    coach_avg_pake = coach_results["PAKE"].mean()
    coach_lookup = coach_results.set_index("coach_name")

    # Build Vegas lookup: {(team_a, team_b): {"spread_a": float, ...}}
    vegas_lookup = {}
    if vegas_lines is not None and len(vegas_lines) > 0:
        for _, vrow in vegas_lines.iterrows():
            key = (str(vrow.get("team_a", "")), str(vrow.get("team_b", "")))
            vegas_lookup[key] = {
                "spread_a": vrow.get("spread_a"),
                "spread_b": vrow.get("spread_b"),
                "moneyline_a": vrow.get("moneyline_a"),
                "moneyline_b": vrow.get("moneyline_b"),
                "total": vrow.get("total"),
            }
        log.info("Vegas lines loaded: %d games", len(vegas_lookup))

    results = []

    # ── R64: from bracket structure (known matchups) ──────────────
    for region in ["East", "South", "West", "Midwest"]:
        region_df = current_teams_df[current_teams_df["region"] == region]
        seed_to_row = {int(row["seed"]): row for _, row in region_df.iterrows()}
        matchup_seeds = [(1, 16), (8, 9), (5, 12), (4, 13), (6, 11), (3, 14), (7, 10), (2, 15)]

        for higher_seed, lower_seed in matchup_seeds:
            fav = seed_to_row.get(higher_seed)
            dog = seed_to_row.get(lower_seed)
            if fav is None or dog is None:
                continue
            alert = _build_alert(
                fav, dog, higher_seed, lower_seed, 64, region,
                upset_rates, coach_lookup, coach_avg_pake, ml_probabilities,
                is_projected=False, vegas_lookup=vegas_lookup,
            )
            results.append(alert)

    # ── R32+ : from projected bracket picks ───────────────────────
    if projected_picks:
        for rd in [32, 16, 8, 4]:
            rd_picks = [p for p in projected_picks if p.get("round") == rd]
            for pick in rd_picks:
                team_a = pick.get("team_a", "")
                team_b = pick.get("team_b", "")
                seed_a = pick.get("seed_a", 8)
                seed_b = pick.get("seed_b", 8)
                region = pick.get("region", "")

                if team_a not in teams.index or team_b not in teams.index:
                    continue

                fav_row = teams.loc[team_a]
                dog_row = teams.loc[team_b]

                # Determine who is the favorite (lower seed number)
                if seed_a <= seed_b:
                    fav, dog = fav_row, dog_row
                    fav_seed, dog_seed = int(seed_a), int(seed_b)
                else:
                    fav, dog = dog_row, fav_row
                    fav_seed, dog_seed = int(seed_b), int(seed_a)

                alert = _build_alert(
                    fav, dog, fav_seed, dog_seed, rd, region,
                    upset_rates, coach_lookup, coach_avg_pake, ml_probabilities,
                    is_projected=True, vegas_lookup=vegas_lookup,
                )
                results.append(alert)

    df = pd.DataFrame(results)
    # Sort by round (ascending = R64 first), then upset_score descending
    df = df.sort_values(["round", "upset_score"], ascending=[True, False]).reset_index(drop=True)

    for rd in [64, 32, 16, 8, 4]:
        rd_df = df[df["round"] == rd]
        n_high = rd_df["high_alert"].sum() if len(rd_df) > 0 else 0
        log.info("  %s: %d games, %d HIGH ALERTS", ROUND_NAMES.get(rd, rd), len(rd_df), n_high)

    log.info("Upset detection complete: %d total games, %d HIGH ALERTS",
             len(df), df["high_alert"].sum())
    return df


def _build_alert(
    fav: pd.Series,
    dog: pd.Series,
    fav_seed: int,
    dog_seed: int,
    round_num: int,
    region: str,
    upset_rates: dict,
    coach_lookup: pd.DataFrame,
    coach_avg_pake: float,
    ml_probabilities: dict = None,
    is_projected: bool = False,
    vegas_lookup: dict = None,
) -> dict:
    """Build a single alert dict for a matchup."""
    fav_name = fav.get("team_name", fav.name if hasattr(fav, "name") else "Unknown")
    dog_name = dog.get("team_name", dog.name if hasattr(dog, "name") else "Unknown")

    # Find Vegas data for this matchup (try both orderings)
    vegas = None
    if vegas_lookup:
        vegas = vegas_lookup.get((fav_name, dog_name))
        if not vegas:
            vegas = vegas_lookup.get((dog_name, fav_name))

    flags = _evaluate_flags(fav, dog, fav_seed, dog_seed, round_num,
                            upset_rates, coach_lookup, coach_avg_pake, vegas, fav_name)
    upset_score = sum(v for k, v in flags.items() if k != "_max_score" and isinstance(v, bool))

    row = {
        "round": round_num,
        "round_name": ROUND_NAMES.get(round_num, f"R{round_num}"),
        "region": region,
        "higher_seed": fav_seed,
        "lower_seed": dog_seed,
        "favorite": fav_name,
        "underdog": dog_name,
        "upset_score": upset_score,
        "max_score": flags.pop("_max_score", 9),
        "high_alert": upset_score >= 3,
        "is_projected": is_projected,
        "vegas_spread": _get_vegas_spread(vegas, fav_name) if vegas else None,
    }

    # ML probability
    if ml_probabilities is not None:
        ml_prob = ml_probabilities.get((fav_name, dog_name))
        if ml_prob is not None:
            row["ml_upset_prob"] = 1.0 - ml_prob
        else:
            ml_prob = ml_probabilities.get((dog_name, fav_name))
            if ml_prob is not None:
                row["ml_upset_prob"] = ml_prob
            else:
                row["ml_upset_prob"] = np.nan
    else:
        row["ml_upset_prob"] = np.nan

    # Individual flags
    for flag_name, triggered in flags.items():
        row[flag_name] = triggered

    # Context stats
    row["fav_kp_rank"] = _safe(fav, "KP_RANK")
    row["dog_kp_rank"] = _safe(dog, "KP_RANK")
    row["fav_adj_em"] = _safe(fav, "KP_AdjEM")
    row["dog_adj_em"] = _safe(dog, "KP_AdjEM")
    row["rank_gap"] = abs((_safe(fav, "KP_RANK") or 0) - (_safe(dog, "KP_RANK") or 0))
    row["hist_upset_rate"] = upset_rates.get((round_num, fav_seed, dog_seed), 0.0)

    return row


def _evaluate_flags(
    fav: pd.Series,
    dog: pd.Series,
    fav_seed: int,
    dog_seed: int,
    round_num: int,
    upset_rates: dict,
    coach_lookup: pd.DataFrame,
    coach_avg_pake: float,
    vegas: dict = None,
    fav_name: str = "",
) -> dict[str, bool]:
    """Evaluate upset flag conditions for a single matchup in any round.

    9 base conditions always evaluated.
    2 Vegas conditions evaluated when Vegas data is available.
    Returns flags dict with a special '_max_score' key for the denominator.
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

    # 3. Higher seed fading (positive Luck = overperformed, likely to regress)
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

    # 6. 3-point style clash
    dog_drtg_rank = _safe(dog, "DRtg_Rank")
    fav_ortg_rank = _safe(fav, "ORtg_Rank")
    flags["style_clash_3pt"] = (dog_drtg_rank is not None and dog_drtg_rank <= 30 and
                                 fav_ortg_rank is not None and fav_ortg_rank <= 30)

    # 7. Historical upset rate > 30% for this seed pairing IN THIS ROUND
    hist_rate = upset_rates.get((round_num, fav_seed, dog_seed), 0.0)
    flags["hist_upset_rate_30"] = hist_rate > 0.30

    # 8. AdjEM gap < 8 points (close game)
    fav_em = _safe(fav, "KP_AdjEM")
    dog_em = _safe(dog, "KP_AdjEM")
    em_gap = abs(fav_em - dog_em) if fav_em is not None and dog_em is not None else 999
    flags["elo_close"] = em_gap < 8

    # 9. Higher seed has soft losses (WAB rank > 20)
    fav_wab_rk = _safe(fav, "BT_WAB Rk")
    flags["fav_soft_losses"] = (fav_wab_rk is not None and fav_wab_rk > 20)

    # ── Vegas conditions (10-11) — only when Vegas data available ──
    max_score = 9
    if vegas is not None:
        max_score = 11
        # Determine which spread belongs to the favorite
        fav_spread = _get_vegas_spread(vegas, fav_name)

        # 10. Vegas line within 5.5 points (close game by market)
        if fav_spread is not None:
            flags["vegas_close_line"] = abs(fav_spread) <= 5.5
        else:
            flags["vegas_close_line"] = False

        # 11. Vegas implied upset probability > 25%
        # Convert spread to win probability: prob = 1 / (1 + 10^(spread/15))
        # where spread is the DOG's spread (positive = underdog)
        if fav_spread is not None:
            dog_spread = abs(fav_spread)  # dog's spread magnitude (always positive)
            vegas_upset_prob = 1.0 / (1.0 + 10.0 ** (dog_spread / 15.0))
            flags["vegas_upset_likely"] = vegas_upset_prob > 0.25
        else:
            flags["vegas_upset_likely"] = False

    flags["_max_score"] = max_score
    return flags


def _get_vegas_spread(vegas: dict, fav_name: str) -> float:
    """Get the favorite's spread from a Vegas data dict.

    The CSV stores team_a/team_b with their respective spreads.
    We need to figure out which one is the favorite.
    The favorite's spread is the more negative number.
    """
    if vegas is None:
        return None
    spread_a = vegas.get("spread_a")
    spread_b = vegas.get("spread_b")
    if spread_a is not None and spread_b is not None:
        # Return the more negative spread (the favorite's line)
        return min(spread_a, spread_b)
    return None


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
    print("2026 MARCH MADNESS — UPSET DETECTION REPORT (ALL ROUNDS)")
    print("=" * 80)

    for rd in [64, 32, 16, 8, 4]:
        rd_alerts = alerts[alerts["round"] == rd]
        high = rd_alerts[rd_alerts["high_alert"]]
        rd_name = ROUND_NAMES[rd]
        print(f"\n{rd_name}: {len(rd_alerts)} games, {len(high)} HIGH ALERTS")
        if len(high) > 0:
            for _, row in high.iterrows():
                proj = " [PROJECTED]" if row.get("is_projected") else ""
                print(f"  ({row['higher_seed']}) {row['favorite']} vs ({row['lower_seed']}) {row['underdog']}  "
                      f"Score: {row['upset_score']}/9  [{row['region']}]{proj}")
