"""
Feature Engineering — March Madness Bracket Prediction System

Transforms raw per-team stats into matchup-level differential features
for ML model training (historical) and 2026 predictions.

All features are computed as (Team A value) minus (Team B value) for
differential features, or absolute values for non-directional features.

Missing data is preserved as NaN — XGBoost/LightGBM handle NaN natively.
No zero-filling for missing values (avoids spurious zero/non-zero splits).

Feature groups:
  1. Efficiency differentials (4) — dropped bpi_diff (35% coverage)
  2. Stylistic matchup features (6)
  3. Variance and experience features (3)
  4. Luck and momentum features (4)
  5. Historical and context features (8) — dropped coach_pake/exp (leakage),
     program_champ_pct (blue-blood proxy); added seed_diff
  6. Travel and location features (2)
  → 29 features total
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature names — used for consistent column ordering everywhere
# ---------------------------------------------------------------------------
FEATURE_NAMES = [
    # 1. Efficiency differentials (4)
    "adj_em_diff",
    "barthag_diff",
    "adj_o_diff",
    "adj_d_diff",
    # 2. Stylistic matchup (6)
    "tempo_mismatch",
    "three_pt_clash_a",    # A's 3pt rate vs B's 3pt defense
    "three_pt_clash_b",    # B's 3pt rate vs A's 3pt defense
    "turnover_battle",     # A's TOV% advantage (lower = better for A)
    "rebound_battle",      # A's offensive rebounding edge
    "ft_disparity",        # A's FTR vs B's ability to avoid fouling
    "shot_quality_clash",  # A's dunks/close shots vs B's interior D
    # 3. Variance / experience (3)
    "experience_diff",
    "height_diff",
    "talent_diff",
    # 4. Luck / momentum (4)
    "luck_diff",
    "luck_top25_diff",
    "preseason_momentum_diff",
    "preseason_rank_delta_diff",
    # 5. Historical / context (8)
    "seed_diff",                # Numerical seed differential (A - B)
    "seed_upset_hist_rate",
    "kenpom_vs_seed_discrep_a",
    "kenpom_vs_seed_discrep_b",
    "elo_diff",
    "q1_wins_diff",
    "auto_bid_a",
    "auto_bid_b",
    # 6. Travel / location (2)
    "travel_distance_diff",
    "timezone_diff",
]

NUM_FEATURES = len(FEATURE_NAMES)


# =========================================================================
# HISTORICAL feature computation (from historical_games_df)
# =========================================================================

def build_historical_features(
    games_df: pd.DataFrame,
    seed_results: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build the full feature matrix for historical tournament games.

    Args:
        games_df: Output of data_pipeline.build_historical_games
        seed_results: Seed_Results reference DataFrame

    Returns:
        X: DataFrame with FEATURE_NAMES columns, one row per game
        y: Series with target (1 = team A won)
    """
    n = len(games_df)
    log.info("Building historical features for %d games", n)

    # Pre-compute seed upset rates lookup
    seed_upset_map = _build_seed_upset_map(seed_results)

    features = {}

    # ----- 1. Efficiency differentials (4) -----
    # Use Pre-Tournament.AdjEM where available, fall back to KADJ EM
    em_a = games_df["Pre-Tournament.AdjEM_a"].fillna(games_df["KADJ EM_a"])
    em_b = games_df["Pre-Tournament.AdjEM_b"].fillna(games_df["KADJ EM_b"])
    features["adj_em_diff"] = em_a - em_b

    features["barthag_diff"] = games_df["BARTHAG_a"] - games_df["BARTHAG_b"]

    features["adj_o_diff"] = games_df["KADJ O_a"] - games_df["KADJ O_b"]

    # AdjD: lower is better, so A having lower D is an advantage → negate
    features["adj_d_diff"] = -(games_df["KADJ D_a"] - games_df["KADJ D_b"])

    # ----- 2. Stylistic matchup (6) -----
    features["tempo_mismatch"] = (games_df["KADJ T_a"] - games_df["KADJ T_b"]).abs()

    # 3pt clash: A shoots 3s at rate, B defends 3s
    features["three_pt_clash_a"] = games_df["3PT%_a"] - games_df["3PT%D_b"]
    features["three_pt_clash_b"] = games_df["3PT%_b"] - games_df["3PT%D_a"]

    # Turnover battle: positive = A has turnover advantage
    features["turnover_battle"] = (
        (games_df["TOV%D_a"] - games_df["TOV%_a"]) -
        (games_df["TOV%D_b"] - games_df["TOV%_b"])
    )

    # Rebound battle
    features["rebound_battle"] = (
        (games_df["OREB%_a"] - games_df["OP OREB%_b"]) -
        (games_df["OREB%_b"] - games_df["OP OREB%_a"])
    )

    # Free throw rate disparity
    features["ft_disparity"] = (
        (games_df["FTR_a"] - games_df["FTRD_b"]) -
        (games_df["FTR_b"] - games_df["FTRD_a"])
    )

    # Shot quality: A's ability to score at rim vs B's
    features["shot_quality_clash"] = (
        games_df["DUNKS SHARE_a"] * games_df["DUNKS FG%_a"] +
        games_df["CLOSE TWOS SHARE_a"] * games_df["CLOSE TWOS FG%_a"]
    ) - (
        games_df["DUNKS SHARE_b"] * games_df["DUNKS FG%_b"] +
        games_df["CLOSE TWOS SHARE_b"] * games_df["CLOSE TWOS FG%_b"]
    )

    # ----- 3. Variance / experience (3) -----
    features["experience_diff"] = games_df["EXP_a"] - games_df["EXP_b"]
    features["height_diff"] = games_df["AVG HGT_a"] - games_df["AVG HGT_b"]
    features["talent_diff"] = games_df["TALENT_a"] - games_df["TALENT_b"]

    # ----- 4. Luck / momentum (4) -----
    # NaN preserved — XGBoost/LightGBM handle natively
    features["luck_diff"] = games_df["LUCK RATING_a"] - games_df["LUCK RATING_b"]
    features["luck_top25_diff"] = (
        games_df["LUCK V 1-25 WINS_a"] - games_df["LUCK V 1-25 WINS_b"]
    )
    features["preseason_momentum_diff"] = (
        games_df["KADJ EM CHANGE_a"] - games_df["KADJ EM CHANGE_b"]
    )
    features["preseason_rank_delta_diff"] = (
        games_df["KADJ EM RANK CHANGE_a"] - games_df["KADJ EM RANK CHANGE_b"]
    )

    # ----- 5. Historical / context (8) -----
    # Seed differential (clean, powerful)
    features["seed_diff"] = games_df["seed_a"].astype(float) - games_df["seed_b"].astype(float)

    # Seed matchup historical upset rate
    features["seed_upset_hist_rate"] = pd.Series(
        [_get_upset_rate(row["seed_a"], row["seed_b"], seed_upset_map)
         for _, row in games_df.iterrows()],
        index=games_df.index,
    )

    # KenPom rank vs seed discrepancy: (SEED * 4) - rank
    # Large positive → underseeded (better than seed suggests)
    em_rank_a = games_df["Pre-Tournament.RankAdjEM_a"].fillna(games_df["KADJ EM RANK_a"])
    em_rank_b = games_df["Pre-Tournament.RankAdjEM_b"].fillna(games_df["KADJ EM RANK_b"])
    features["kenpom_vs_seed_discrep_a"] = (games_df["seed_a"] * 4) - em_rank_a
    features["kenpom_vs_seed_discrep_b"] = (games_df["seed_b"] * 4) - em_rank_b

    features["elo_diff"] = games_df["ELO_a"] - games_df["ELO_b"]
    features["q1_wins_diff"] = games_df["Q1 W_a"] - games_df["Q1 W_b"]

    # Auto-bid flag: 1 if team is auto-bid (conference tournament winner, not at-large)
    features["auto_bid_a"] = (games_df["BID TYPE_a"] == "Auto").astype(float)
    features["auto_bid_b"] = (games_df["BID TYPE_b"] == "Auto").astype(float)

    # DROPPED: coach_pake_diff (temporal leakage), coach_experience_diff (same),
    #          program_champ_pct_diff (blue-blood proxy), bpi_diff (35% coverage)

    # ----- 6. Travel / location (2) -----
    features["travel_distance_diff"] = (
        games_df["LOC_DISTANCE (MI)_a"] - games_df["LOC_DISTANCE (MI)_b"]
    )
    features["timezone_diff"] = (
        games_df["LOC_TIME ZONES CROSSED_a"] - games_df["LOC_TIME ZONES CROSSED_b"]
    )

    # Build DataFrame — NaN preserved for tree models, inf replaced with NaN
    X = pd.DataFrame(features, index=games_df.index)
    X = X[FEATURE_NAMES]  # enforce column order

    y = games_df["team_a_won"].astype(int)

    # Only replace inf → NaN. Do NOT fill NaN with 0.
    X = X.replace([np.inf, -np.inf], np.nan)

    log.info("Historical feature matrix: %d rows × %d features", X.shape[0], X.shape[1])
    _log_feature_stats(X)

    return X, y


# =========================================================================
# 2026 MATCHUP feature computation (for predictions)
# =========================================================================

def build_matchup_features_2026(
    team_a: pd.Series,
    team_b: pd.Series,
    round_num: int,
    seed_results: pd.DataFrame,
) -> pd.DataFrame:
    """Build feature vector for a single 2026 matchup.

    Args:
        team_a: Row from current_teams_df for team A
        team_b: Row from current_teams_df for team B
        round_num: Tournament round (64, 32, 16, 8, 4, 2)
        seed_results: Seed_Results reference DataFrame

    Returns:
        Single-row DataFrame with FEATURE_NAMES columns
    """
    seed_upset_map = _build_seed_upset_map(seed_results)
    features = {}

    # ----- 1. Efficiency differentials -----
    features["adj_em_diff"] = _safe_diff(team_a, "KP_AdjEM", team_b, "KP_AdjEM")

    features["barthag_diff"] = _safe_diff(team_a, "BT_BARTHAG", team_b, "BT_BARTHAG")

    features["adj_o_diff"] = _safe_diff(team_a, "ORtg", team_b, "ORtg",
                                        fallback_a="BT_AdjO", fallback_b="BT_AdjO")

    # DRtg: lower is better → negate
    features["adj_d_diff"] = -(
        _safe_val(team_a, "DRtg", "BT_AdjD") - _safe_val(team_b, "DRtg", "BT_AdjD")
    )

    features["bpi_diff"] = 0.0  # BPI not available for 2026 — use 0 (model trained with many 0s)

    # ----- 2. Stylistic matchup -----
    features["tempo_mismatch"] = abs(
        _safe_val(team_a, "AdjT", "BT_AdjT") - _safe_val(team_b, "AdjT", "BT_AdjT")
    )

    # For 2026: use KB_ columns from KenPom_Barttorvik 2026 when available
    features["three_pt_clash_a"] = _safe_diff_nan(team_a, "KB_3PT%", team_b, "KB_3PT%D")
    features["three_pt_clash_b"] = _safe_diff_nan(team_b, "KB_3PT%", team_a, "KB_3PT%D")

    features["turnover_battle"] = (
        (_safe_val_nan(team_a, "KB_TOV%D") - _safe_val_nan(team_a, "KB_TOV%")) -
        (_safe_val_nan(team_b, "KB_TOV%D") - _safe_val_nan(team_b, "KB_TOV%"))
    ) if not (np.isnan(_safe_val_nan(team_a, "KB_TOV%")) or np.isnan(_safe_val_nan(team_b, "KB_TOV%"))) else np.nan

    features["rebound_battle"] = (
        (_safe_val_nan(team_a, "KB_OREB%") - _safe_val_nan(team_b, "KB_OP OREB%")) -
        (_safe_val_nan(team_b, "KB_OREB%") - _safe_val_nan(team_a, "KB_OP OREB%"))
    ) if not (np.isnan(_safe_val_nan(team_a, "KB_OREB%")) or np.isnan(_safe_val_nan(team_b, "KB_OREB%"))) else np.nan

    features["ft_disparity"] = (
        (_safe_val_nan(team_a, "KB_FTR") - _safe_val_nan(team_b, "KB_FTRD")) -
        (_safe_val_nan(team_b, "KB_FTR") - _safe_val_nan(team_a, "KB_FTRD"))
    ) if not (np.isnan(_safe_val_nan(team_a, "KB_FTR")) or np.isnan(_safe_val_nan(team_b, "KB_FTR"))) else np.nan

    features["shot_quality_clash"] = np.nan  # No Shooting Splits for 2026

    # ----- 3. Variance / experience -----
    features["experience_diff"] = _safe_diff_nan(team_a, "KB_EXP", team_b, "KB_EXP")
    features["height_diff"] = _safe_diff_nan(team_a, "KB_AVG HGT", team_b, "KB_AVG HGT")
    features["talent_diff"] = _safe_diff_nan(team_a, "KB_TALENT", team_b, "KB_TALENT")

    # ----- 4. Luck / momentum -----
    features["luck_diff"] = _safe_diff_nan(team_a, "Luck", team_b, "Luck")
    features["luck_top25_diff"] = np.nan  # Not in 2026 data
    features["preseason_momentum_diff"] = np.nan
    features["preseason_rank_delta_diff"] = np.nan

    # ----- 5. Historical / context -----
    seed_a = int(team_a.get("seed", 8))
    seed_b = int(team_b.get("seed", 8))

    features["seed_diff"] = float(seed_a - seed_b)

    features["seed_upset_hist_rate"] = _get_upset_rate(seed_a, seed_b, seed_upset_map)

    kp_rank_a = _safe_val_nan(team_a, "KP_RANK")
    kp_rank_b = _safe_val_nan(team_b, "KP_RANK")
    features["kenpom_vs_seed_discrep_a"] = (seed_a * 4) - kp_rank_a if not np.isnan(kp_rank_a) else np.nan
    features["kenpom_vs_seed_discrep_b"] = (seed_b * 4) - kp_rank_b if not np.isnan(kp_rank_b) else np.nan

    features["elo_diff"] = np.nan  # ELO not in 2026 data
    features["q1_wins_diff"] = np.nan
    features["auto_bid_a"] = np.nan
    features["auto_bid_b"] = np.nan

    # DROPPED: coach_pake_diff, coach_experience_diff, program_champ_pct_diff, bpi_diff

    # ----- 6. Travel / location -----
    features["travel_distance_diff"] = np.nan  # No 2026 location data yet
    features["timezone_diff"] = np.nan

    row = pd.DataFrame([features])[FEATURE_NAMES]
    row = row.replace([np.inf, -np.inf], np.nan)
    return row


def build_all_2026_matchup_features(
    bracket: dict,
    current_teams_df: pd.DataFrame,
    seed_results: pd.DataFrame,
) -> pd.DataFrame:
    """Build feature vectors for all R64 matchups in the 2026 bracket.

    Uses seed+region from current_teams_df (already name-resolved) to
    look up teams, avoiding bracket↔canonical name mismatches.

    Returns a DataFrame with columns: team_a, team_b, seed_a, seed_b, region,
    plus all FEATURE_NAMES.
    """
    rows = []

    for region in ["East", "South", "West", "Midwest"]:
        # R64 matchups by bracket position
        matchup_seeds = [(1, 16), (8, 9), (5, 12), (4, 13), (6, 11), (3, 14), (7, 10), (2, 15)]

        # Look up teams by (seed, region) from current_teams_df — names are already canonical
        region_df = current_teams_df[current_teams_df["region"] == region]
        seed_to_row = {int(row["seed"]): row for _, row in region_df.iterrows()}

        for seed_a, seed_b in matchup_seeds:
            team_a_row = seed_to_row.get(seed_a)
            team_b_row = seed_to_row.get(seed_b)
            if team_a_row is None or team_b_row is None:
                log.warning("Missing team for seed %d or %d in %s", seed_a, seed_b, region)
                continue

            feats = build_matchup_features_2026(team_a_row, team_b_row, 64, seed_results)
            feats = feats.iloc[0].to_dict()
            feats["team_a"] = team_a_row["team_name"]
            feats["team_b"] = team_b_row["team_name"]
            feats["seed_a"] = seed_a
            feats["seed_b"] = seed_b
            feats["region"] = region
            rows.append(feats)

    result = pd.DataFrame(rows)
    meta_cols = ["team_a", "team_b", "seed_a", "seed_b", "region"]
    col_order = meta_cols + FEATURE_NAMES
    result = result[col_order]
    log.info("2026 R64 matchup features: %d games × %d features", len(result), NUM_FEATURES)
    return result


# =========================================================================
# Helper functions
# =========================================================================

def _build_seed_upset_map(seed_results: pd.DataFrame) -> dict[int, float]:
    """Build seed → historical win rate lookup from Seed_Results."""
    mapping = {}
    for _, row in seed_results.iterrows():
        seed = int(row["SEED"])
        win_pct = row.get("WIN%", 0.5)
        if isinstance(win_pct, str):
            win_pct = float(win_pct.replace("%", "")) / 100
        mapping[seed] = float(win_pct)
    return mapping


def _get_upset_rate(seed_a: int, seed_b: int, seed_map: dict[int, float]) -> float:
    """Get historical upset rate for a seed matchup.

    Returns the probability that the lower-seeded team (higher number) wins.
    If seed_a > seed_b (A is the underdog), returns A's historical win rate.
    """
    if pd.isna(seed_a) or pd.isna(seed_b):
        return 0.5
    seed_a, seed_b = int(seed_a), int(seed_b)
    higher_seed = min(seed_a, seed_b)  # better seed (lower number)
    lower_seed = max(seed_a, seed_b)   # worse seed (higher number)

    # Win rate in seed_map is for that seed overall
    # Upset rate = 1 - favorite's win rate
    favorite_win_rate = seed_map.get(higher_seed, 0.5)
    return 1.0 - favorite_win_rate


def _safe_val(row: pd.Series, col: str, fallback_col: str = None) -> float:
    """Safely get a numeric value from a Series. Returns 0 for NaN."""
    val = row.get(col, np.nan) if len(row) > 0 else np.nan
    if pd.isna(val) and fallback_col is not None:
        val = row.get(fallback_col, np.nan) if len(row) > 0 else np.nan
    return float(val) if pd.notna(val) else 0.0


def _safe_val_nan(row: pd.Series, col: str, fallback_col: str = None) -> float:
    """Safely get a numeric value from a Series. Preserves NaN."""
    val = row.get(col, np.nan) if len(row) > 0 else np.nan
    if pd.isna(val) and fallback_col is not None:
        val = row.get(fallback_col, np.nan) if len(row) > 0 else np.nan
    return float(val) if pd.notna(val) else np.nan


def _safe_diff(row_a: pd.Series, col_a: str,
               row_b: pd.Series, col_b: str,
               fallback_a: str = None, fallback_b: str = None) -> float:
    """Compute A - B safely with fallback columns. Returns 0 for NaN."""
    return _safe_val(row_a, col_a, fallback_a) - _safe_val(row_b, col_b, fallback_b)


def _safe_diff_nan(row_a: pd.Series, col_a: str,
                   row_b: pd.Series, col_b: str,
                   fallback_a: str = None, fallback_b: str = None) -> float:
    """Compute A - B safely. Returns NaN if either value is missing."""
    a = _safe_val_nan(row_a, col_a, fallback_a)
    b = _safe_val_nan(row_b, col_b, fallback_b)
    if np.isnan(a) or np.isnan(b):
        return np.nan
    return a - b


def _log_feature_stats(X: pd.DataFrame) -> None:
    """Log summary statistics for the feature matrix."""
    log.info("Feature statistics:")
    for col in X.columns:
        non_zero = (X[col] != 0).mean()
        log.info("  %-30s  mean=%7.3f  std=%7.3f  non-zero=%.1f%%",
                 col, X[col].mean(), X[col].std(), non_zero * 100)


# =========================================================================
# CLI entry point — test with real data
# =========================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from data_pipeline import run_pipeline

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    hist, curr, refs, bracket = run_pipeline()

    print("\n" + "=" * 60)
    print("BUILDING HISTORICAL FEATURES")
    print("=" * 60)
    X, y = build_historical_features(hist, refs["seed_results"])

    print(f"\nFeature matrix shape: {X.shape}")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    print(f"\nFeature sample (first 5 rows):")
    print(X.head().to_string())

    print(f"\nFeature correlations with target (top 15):")
    corrs = X.corrwith(y).abs().sort_values(ascending=False)
    for feat, corr in corrs.head(15).items():
        print(f"  {feat}: {corr:.4f}")

    print("\n" + "=" * 60)
    print("BUILDING 2026 R64 MATCHUP FEATURES")
    print("=" * 60)
    matchups_2026 = build_all_2026_matchup_features(bracket, curr, refs["seed_results"])
    print(f"\n2026 matchups shape: {matchups_2026.shape}")
    print(matchups_2026[["team_a", "team_b", "seed_a", "seed_b", "region",
                          "adj_em_diff", "barthag_diff", "tempo_mismatch"]].to_string(index=False))
