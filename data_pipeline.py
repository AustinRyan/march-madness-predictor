"""
Data Pipeline — March Madness Bracket Prediction System

Loads, cleans, and merges all data sources into two main outputs:
1. historical_games_df: One row per tournament game (2008-2025), both teams' stats + outcome
2. current_teams_df: One row per 2026 bracket team with all available stats

All data comes from real CSV files in /data/. No synthetic or mock data.
"""

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
from fuzzywuzzy import fuzz, process

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HIST_DIR = DATA_DIR / "historical"
CURR_DIR = DATA_DIR / "2026"
REF_DIR = DATA_DIR / "reference"

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known team-name aliases that fuzzy matching commonly gets wrong
# Maps variant → canonical name  (canonical = KenPom Barttorvik historical)
# ---------------------------------------------------------------------------
HARD_CODED_ALIASES: dict[str, str] = {
    # Saint / St variations
    "Saint Mary's": "St. Mary's",
    "Saint Mary's (CA)": "St. Mary's",
    "Saint Louis": "Saint Louis",
    "St Louis": "Saint Louis",
    "St. John's (NY)": "St. John's",
    "St. John's Red Storm": "St. John's",
    # Miami disambiguation
    "Miami (FL)": "Miami FL",
    "Miami (OH)": "Miami OH",
    "Miami Florida": "Miami FL",
    "Miami Ohio": "Miami OH",
    "Miami Hurricanes": "Miami FL",
    "Miami (OH) RedHawks": "Miami OH",
    # Full-name → short-name common issues
    "UConn": "Connecticut",
    "Connecticut Huskies": "Connecticut",
    "UConn Huskies": "Connecticut",
    "UCF": "UCF",
    "Central Florida": "UCF",
    "UCF Knights": "UCF",
    "UCSB": "UC Santa Barbara",
    "USC": "Southern California",
    "Southern California Trojans": "Southern California",
    "Ole Miss": "Mississippi",
    "Mississippi Rebels": "Mississippi",
    "Pitt": "Pittsburgh",
    "Pittsburgh Panthers": "Pittsburgh",
    "SMU": "SMU",
    "Southern Methodist": "SMU",
    "BYU": "BYU",
    "Brigham Young": "BYU",
    "Brigham Young Cougars": "BYU",
    "LSU": "LSU",
    "Louisiana State": "LSU",
    "VCU": "VCU",
    "Virginia Commonwealth": "VCU",
    "UNLV": "UNLV",
    "Nevada-Las Vegas": "UNLV",
    "LIU": "LIU",
    "Long Island University": "LIU",
    "Long Island": "LIU",
    "UMBC": "UMBC",
    "UC San Diego": "UC San Diego",
    "UCSD": "UC San Diego",
    "UNC": "North Carolina",
    "North Carolina Tar Heels": "North Carolina",
    "NC State": "N.C. State",
    "North Carolina State": "N.C. State",
    "NC State Wolfpack": "N.C. State",
    "ETSU": "East Tennessee St.",
    "FDU": "Fairleigh Dickinson",
    "FGCU": "Florida Gulf Coast",
    "SFA": "Stephen F. Austin",
    "Loyola Chicago": "Loyola Chicago",
    "Loyola-Chicago": "Loyola Chicago",
    "Texas A&M Corpus Christi": "Texas A&M Corpus Christi",
    "Texas A&M-CC": "Texas A&M Corpus Christi",
    "Hawai'i": "Hawaii",
    "Hawaii Rainbow Warriors": "Hawaii",
    "Prairie View A&M": "Prairie View",
    "Prairie View A&M Panthers": "Prairie View",
    "North Dakota State": "North Dakota St.",
    "North Dakota State Bison": "North Dakota St.",
    "Wright State": "Wright St.",
    "Wright State Raiders": "Wright St.",
    "Tennessee State": "Tennessee St.",
    "Tennessee State Tigers": "Tennessee St.",
    "Kennesaw State": "Kennesaw St.",
    "Kennesaw State Owls": "Kennesaw St.",
    "Utah State": "Utah St.",
    "Utah State Aggies": "Utah St.",
    "Cal Baptist": "Cal Baptist",
    "California Baptist": "Cal Baptist",
    "Cal St. Bakersfield": "Cal St. Bakersfield",
    "High Point": "High Point",
    "Northern Iowa": "Northern Iowa",
    "Iowa State": "Iowa St.",
    "Iowa St": "Iowa St.",
    "Michigan State": "Michigan St.",
    "Michigan St": "Michigan St.",
    "Ohio State": "Ohio St.",
    "Ohio St": "Ohio St.",
    "Texas Tech": "Texas Tech",
    "South Florida": "South Florida",
    "USF": "South Florida",
    "Santa Clara": "Santa Clara",
    "Queens": "Queens",
    "Hofstra": "Hofstra",
    "Akron": "Akron",
    "Furman": "Furman",
    "McNeese": "McNeese St.",
    "McNeese State": "McNeese St.",
    "Troy": "Troy",
    "Idaho": "Idaho",
    "Penn": "Penn",
    "Penn Quakers": "Penn",
}


# =========================================================================
# 1.  LOADERS — one per file, return cleaned DataFrame
# =========================================================================

def load_kenpom_barttorvik() -> pd.DataFrame:
    """Category A — primary historical training data (2008-2025)."""
    path = HIST_DIR / "KenPom Barttorvik.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("KenPom_Barttorvik: %d rows, years %d–%d", len(df), df.season.min(), df.season.max())
    return df


def load_barttorvik_neutral() -> pd.DataFrame:
    """Category A — neutral-site-only Barttorvik stats."""
    path = HIST_DIR / "Barttorvik Neutral.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    # Prefix neutral-site columns to distinguish from full-season
    stat_cols = [c for c in df.columns if c not in
                 ("season", "team_name", "TEAM NO", "TEAM ID", "SEED", "ROUND",
                  "CONF", "CONF ID", "QUAD NO", "QUAD ID")]
    df.rename(columns={c: f"NEUTRAL_{c}" for c in stat_cols}, inplace=True)
    log.info("Barttorvik_Neutral: %d rows", len(df))
    return df


def load_tournament_matchups() -> pd.DataFrame:
    """Category A — every individual tournament game 2008-2025."""
    path = HIST_DIR / "Tournament Matchups.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("Tournament_Matchups: %d rows, years %d–%d", len(df), df.season.min(), df.season.max())
    return df


def load_tournament_locations() -> pd.DataFrame:
    """Category A — travel distance and timezone data."""
    path = HIST_DIR / "Tournament Locations.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("Tournament_Locations: %d rows", len(df))
    return df


def load_resumes() -> pd.DataFrame:
    """Category A — team resume metrics (ELO, Q1 wins, bid type)."""
    path = HIST_DIR / "Resumes.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("Resumes: %d rows", len(df))
    return df


def load_team_rankings() -> pd.DataFrame:
    """Category A — TeamRankings.com composite ratings + luck metric."""
    path = HIST_DIR / "TeamRankings.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("TeamRankings: %d rows", len(df))
    return df


def load_shooting_splits() -> pd.DataFrame:
    """Category A — granular shot zone breakdowns (2010-2025)."""
    path = HIST_DIR / "Shooting Splits.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("Shooting_Splits: %d rows", len(df))
    return df


def load_kenpom_preseason() -> pd.DataFrame:
    """Category A — preseason vs final KenPom rankings."""
    path = HIST_DIR / "KenPom Preseason.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("KenPom_Preseason: %d rows", len(df))
    return df


def load_dev_march_madness() -> pd.DataFrame:
    """Category A — master joined KenPom (Pilafas), 165 cols, 2002-2025.

    Critical: contains Pre-Tournament.AdjEM and coach data.
    """
    path = HIST_DIR / "DEV _ March Madness.csv"
    df = pd.read_csv(path, low_memory=False)
    df.rename(columns={"Season": "season", "Mapped ESPN Team Name": "team_name"}, inplace=True)
    log.info("DEV_March_Madness: %d rows, years %d–%d, %d columns",
             len(df), df.season.min(), df.season.max(), len(df.columns))
    return df


def load_heat_check_tournament_index() -> pd.DataFrame:
    """Category A — pre-built pool value scores (2013-2025)."""
    path = HIST_DIR / "Heat Check Tournament Index.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("Heat_Check_Index: %d rows", len(df))
    return df


def load_public_picks_historical() -> pd.DataFrame:
    """Category A — historical public pick percentages (2025 only in this dataset)."""
    path = HIST_DIR / "Public Picks.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    # Strip % signs
    for col in ["R64", "R32", "S16", "E8", "F4", "FINALS"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("%", "", regex=False).astype(float)
    log.info("Public_Picks_Historical: %d rows", len(df))
    return df


# --- Category B: 2026 ---

def load_kenpom_2026() -> pd.DataFrame:
    """Category B — current 2026 KenPom ratings (364 D1 teams).

    Fixes header alignment: the CSV header includes 'NetRtg_Rank' which
    doesn't exist in the data (overall Rank IS the NetRtg rank). All
    columns after NetRtg are shifted by one position.
    """
    path = CURR_DIR / "kenpom_2026.csv"
    if not path.exists():
        raise FileNotFoundError(f"MISSING: {path} — provide this file manually (see PROJECT_PLAN.md)")

    # Read raw to fix column alignment
    raw = pd.read_csv(path, header=None, skiprows=1)
    correct_cols = [
        "Rank", "Team", "Conf", "W-L", "NetRtg",
        "ORtg", "ORtg_Rank", "DRtg", "DRtg_Rank",
        "AdjT", "AdjT_Rank", "Luck", "Luck_Rank",
        "SOS_NetRtg", "SOS_NetRtg_Rank",
        "SOS_ORtg", "SOS_ORtg_Rank",
        "SOS_DRtg", "SOS_DRtg_Rank",
        "NCSOS_NetRtg", "NCSOS_NetRtg_Rank",
    ]
    # The raw data may have 21 or 22 columns depending on trailing comma
    raw = raw.iloc[:, :len(correct_cols)]
    raw.columns = correct_cols

    # Clean team name: strip seed suffix (e.g. "Duke 1" → "Duke")
    raw["Team"] = raw["Team"].astype(str).str.replace(r"\s+\d+$", "", regex=True)

    # Convert numeric columns (some have + prefix)
    for col in ["NetRtg", "Luck", "SOS_NetRtg", "NCSOS_NetRtg"]:
        raw[col] = pd.to_numeric(raw[col].astype(str).str.replace("+", "", regex=False), errors="coerce")
    for col in ["ORtg", "DRtg", "AdjT", "SOS_ORtg", "SOS_DRtg"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    for col in [c for c in correct_cols if c.endswith("_Rank") or c == "Rank"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    raw.rename(columns={"Team": "team_name"}, inplace=True)
    log.info("KenPom_2026: %d rows, columns fixed (%d cols)", len(raw), len(raw.columns))
    return raw


def load_barttorvik_2026() -> pd.DataFrame:
    """Category B — full Barttorvik T-Rank stats for 2026."""
    path = CURR_DIR / "barttorvik_2026.csv"
    if not path.exists():
        raise FileNotFoundError(f"MISSING: {path}")
    df = pd.read_csv(path)
    df.rename(columns={"team": "team_name"}, inplace=True)
    log.info("Barttorvik_2026: %d rows, %d columns", len(df), len(df.columns))
    return df


def load_bracket_2026() -> dict:
    """Category B — official 2026 bracket structure."""
    path = CURR_DIR / "bracket_2026.json"
    if not path.exists():
        raise FileNotFoundError(f"MISSING: {path}")
    with open(path) as f:
        bracket = json.load(f)
    # Count teams
    team_count = sum(
        1 for region in ["East", "South", "West", "Midwest"]
        for t in bracket[region]["teams"]
        if "TBD" not in t["team"]
    )
    log.info("Bracket_2026: %d non-TBD teams across 4 regions", team_count)
    return bracket


def load_public_picks_2026() -> pd.DataFrame:
    """Category B — 2026 public pick percentages (estimated from seed priors)."""
    path = CURR_DIR / "public_picks_2026.csv"
    if not path.exists():
        raise FileNotFoundError(f"MISSING: {path}")
    df = pd.read_csv(path)
    # Strip % signs from pick columns
    for col in ["R64", "R32", "S16", "E8", "F4", "FINALS"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("%", "", regex=False).astype(float)
    df.rename(columns={"TEAM": "team_name"}, inplace=True)
    source_col = "SOURCE" if "SOURCE" in df.columns else None
    is_estimated = source_col and (df[source_col] == "ESTIMATED_SEED_PRIOR").all()
    if is_estimated:
        log.warning("Public_Picks_2026: using ESTIMATED seed-based priors, NOT real ESPN data")
    log.info("Public_Picks_2026: %d teams", len(df))
    return df


# --- Category C: Reference ---

def load_coach_results() -> pd.DataFrame:
    """Category C — coach historical tournament records."""
    path = REF_DIR / "Coach Results.csv"
    df = pd.read_csv(path)
    df.rename(columns={"COACH": "coach_name"}, inplace=True)
    # Clean percentage columns
    for col in ["F4%", "CHAMP%"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("%", "", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")
    log.info("Coach_Results: %d coaches", len(df))
    return df


def load_seed_results() -> pd.DataFrame:
    """Category C — historical win rates by seed."""
    path = REF_DIR / "Seed Results.csv"
    df = pd.read_csv(path)
    # Clean CHAMP% column
    if "CHAMP%" in df.columns:
        df["CHAMP%"] = df["CHAMP%"].astype(str).str.replace("%", "", regex=False)
        df["CHAMP%"] = pd.to_numeric(df["CHAMP%"], errors="coerce")
    log.info("Seed_Results: %d seed entries", len(df))
    return df


def load_team_results() -> pd.DataFrame:
    """Category C — all-time program tournament performance."""
    path = REF_DIR / "Team Results.csv"
    df = pd.read_csv(path)
    df.rename(columns={"TEAM": "team_name"}, inplace=True)
    log.info("Team_Results: %d programs", len(df))
    return df


def load_conference_results() -> pd.DataFrame:
    """Category C — conference tournament performance."""
    path = REF_DIR / "Conference Results.csv"
    df = pd.read_csv(path)
    if "CHAMP%" in df.columns:
        df["CHAMP%"] = df["CHAMP%"].astype(str).str.replace("%", "", regex=False)
        df["CHAMP%"] = pd.to_numeric(df["CHAMP%"], errors="coerce")
    log.info("Conference_Results: %d conferences", len(df))
    return df


def load_upset_seed_info() -> pd.DataFrame:
    """Category C — every upset 2008-2025 by seed matchup and round."""
    path = REF_DIR / "Upset Seed Info.csv"
    df = pd.read_csv(path)
    log.info("Upset_Seed_Info: %d upset records", len(df))
    return df


def load_teamsheet_ranks() -> pd.DataFrame:
    """Category C — BPI, NET, KPI, SOR, Quad wins (2019-2025)."""
    path = REF_DIR / "Teamsheet Ranks.csv"
    df = pd.read_csv(path)
    df.rename(columns={"YEAR": "season", "TEAM": "team_name"}, inplace=True)
    log.info("Teamsheet_Ranks: %d rows", len(df))
    return df


# =========================================================================
# 2.  TEAM NAME STANDARDIZATION
# =========================================================================

def _clean_name(name: str) -> str:
    """Basic cleaning: strip whitespace, collapse multiple spaces."""
    if not isinstance(name, str):
        return str(name)
    return re.sub(r"\s+", " ", name.strip())


def build_canonical_names(kb_df: pd.DataFrame, *extra_dfs: pd.DataFrame) -> set[str]:
    """Build the canonical name set from KenPom Barttorvik plus any extra sources.

    Expands the set with 2026 team names so teams new to the tournament
    (e.g., Tennessee St., Queens) don't fuzzy-match to wrong programs.
    """
    names = set(kb_df["team_name"].dropna().unique())
    for df in extra_dfs:
        if "team_name" in df.columns:
            names.update(df["team_name"].dropna().unique())
        elif "team" in df.columns:
            names.update(df["team"].dropna().unique())
    return names


def resolve_name(name: str, canonical: set[str], cache: dict[str, str]) -> str:
    """Resolve a team name to its canonical form.

    1. Check hardcoded aliases
    2. Exact match against canonical set
    3. Fuzzy match with threshold 85
    """
    name = _clean_name(name)
    if not name or name == "nan":
        return name

    if name in cache:
        return cache[name]

    # 1) Hardcoded alias
    if name in HARD_CODED_ALIASES:
        resolved = HARD_CODED_ALIASES[name]
        cache[name] = resolved
        return resolved

    # 2) Exact match
    if name in canonical:
        cache[name] = name
        return name

    # 3) Fuzzy match
    match, score = process.extractOne(name, canonical, scorer=fuzz.ratio)
    if score >= 85:
        cache[name] = match
        return match

    # 4) Try token_sort_ratio for reordered words
    match2, score2 = process.extractOne(name, canonical, scorer=fuzz.token_sort_ratio)
    if score2 >= 85:
        cache[name] = match2
        return match2

    # No match — keep original, log warning
    cache[name] = name
    return name


def standardize_names(df: pd.DataFrame, canonical: set[str],
                      cache: dict[str, str], col: str = "team_name",
                      source: str = "") -> pd.DataFrame:
    """Resolve all team names in df[col] to canonical form."""
    original_names = df[col].dropna().unique()
    df[col] = df[col].apply(lambda x: resolve_name(x, canonical, cache) if pd.notna(x) else x)
    resolved_names = df[col].dropna().unique()
    matched = sum(1 for n in resolved_names if n in canonical)
    total = len(resolved_names)
    log.info("  %s: %d/%d names matched to canonical (%.1f%%)",
             source, matched, total, 100 * matched / max(total, 1))
    return df


# =========================================================================
# 3.  BUILD HISTORICAL TEAM STATS (per team per year)
# =========================================================================

def build_historical_team_stats(
    kb: pd.DataFrame,
    bn: pd.DataFrame,
    dev: pd.DataFrame,
    resumes: pd.DataFrame,
    tr: pd.DataFrame,
    ss: pd.DataFrame,
    kp_pre: pd.DataFrame,
    tl: pd.DataFrame,
    ts_ranks: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all historical sources into one per-team-per-year DataFrame.

    Uses Pre-Tournament.AdjEM from DEV March Madness for training (not end-of-season).
    """
    # Start with KenPom Barttorvik as the base — this has SEED and ROUND for tournament teams
    base = kb[["season", "team_name", "SEED", "ROUND",
                "KADJ EM", "KADJ EM RANK", "KADJ O", "KADJ O RANK",
                "KADJ D", "KADJ D RANK", "KADJ T", "KADJ T RANK",
                "BARTHAG", "WAB",
                "EFG%", "EFG%D", "FTR", "FTRD", "TOV%", "TOV%D",
                "OREB%", "DREB%", "OP OREB%", "OP DREB%",
                "3PT%", "3PT%D", "2PT%", "2PT%D",
                "BLK%", "AST%", "FT%",
                "AVG HGT", "EXP", "TALENT",
                "ELITE SOS", "3PTR", "3PTRD",
                "2PTR", "BADJ EM"]].copy()

    # Fix column names that might not exist (3PTR may be named differently)
    for c in ["3PTR", "3PTRD", "2PTR"]:
        if c not in base.columns:
            base[c] = np.nan

    log.info("Base historical stats: %d rows", len(base))

    # --- Merge Pre-Tournament.AdjEM from DEV March Madness ---
    dev_cols = ["season", "team_name",
                "Pre-Tournament.AdjEM", "Pre-Tournament.RankAdjEM",
                "Pre-Tournament.AdjOE", "Pre-Tournament.RankAdjOE",
                "Pre-Tournament.AdjDE", "Pre-Tournament.RankAdjDE",
                "Pre-Tournament.AdjTempo", "Pre-Tournament.RankAdjTempo",
                "Current Coach", "Since",
                "Seed", "Full Team Name"]
    dev_sub = dev[[c for c in dev_cols if c in dev.columns]].copy()
    # Only keep rows with numeric seeds (tournament teams)
    dev_sub["Seed"] = pd.to_numeric(dev_sub["Seed"], errors="coerce")
    dev_tourney = dev_sub[dev_sub["Seed"].notna()].copy()
    dev_tourney["Seed"] = dev_tourney["Seed"].astype(int)
    base = base.merge(dev_tourney, on=["season", "team_name"], how="left")
    log.info("After DEV merge: %d rows, Pre-Tournament.AdjEM non-null: %d",
             len(base), base["Pre-Tournament.AdjEM"].notna().sum())

    # --- Merge Barttorvik Neutral ---
    neutral_cols = ["season", "team_name"] + [c for c in bn.columns
                                               if c.startswith("NEUTRAL_") and
                                               c not in ("NEUTRAL_CONF", "NEUTRAL_CONF ID")]
    # Keep only the most useful neutral stats
    useful_neutral = ["season", "team_name"]
    for c in bn.columns:
        if c.startswith("NEUTRAL_") and any(x in c for x in
                ["BADJ EM", "BADJ O", "BADJ D", "BARTHAG", "EFG%", "EFG%D",
                 "TOV%", "TOV%D", "OREB%", "DREB%", "3PT%", "3PT%D"]):
            useful_neutral.append(c)
    bn_sub = bn[[c for c in useful_neutral if c in bn.columns]].drop_duplicates(subset=["season", "team_name"])
    base = base.merge(bn_sub, on=["season", "team_name"], how="left")
    log.info("After Barttorvik_Neutral merge: %d rows", len(base))

    # --- Merge Resumes ---
    resume_cols = ["season", "team_name", "ELO", "B POWER",
                   "Q1 W", "Q2 W", "Q1 PLUS Q2 W", "Q3 Q4 L", "BID TYPE"]
    res_sub = resumes[[c for c in resume_cols if c in resumes.columns]].drop_duplicates(
        subset=["season", "team_name"])
    base = base.merge(res_sub, on=["season", "team_name"], how="left")
    log.info("After Resumes merge: %d rows", len(base))

    # --- Merge TeamRankings (luck metrics) ---
    tr_cols = ["season", "team_name", "TR RANK", "TR RATING",
               "LUCK RANK", "LUCK RATING",
               "LUCK V 1-25 WINS", "LUCK V 1-25 LOSS",
               "SOS RANK", "SOS RATING"]
    tr_sub = tr[[c for c in tr_cols if c in tr.columns]].drop_duplicates(
        subset=["season", "team_name"])
    base = base.merge(tr_sub, on=["season", "team_name"], how="left")
    log.info("After TeamRankings merge: %d rows", len(base))

    # --- Merge Shooting Splits ---
    ss_cols = ["season", "team_name",
               "DUNKS FG%", "DUNKS SHARE", "DUNKS FG%D", "DUNKS D SHARE",
               "CLOSE TWOS FG%", "CLOSE TWOS SHARE", "CLOSE TWOS FG%D", "CLOSE TWOS D SHARE",
               "THREES FG%", "THREES SHARE", "THREES FG%D", "THREES D SHARE"]
    ss_sub = ss[[c for c in ss_cols if c in ss.columns]].drop_duplicates(
        subset=["season", "team_name"])
    base = base.merge(ss_sub, on=["season", "team_name"], how="left")
    log.info("After Shooting_Splits merge: %d rows", len(base))

    # --- Merge KenPom Preseason ---
    kp_cols = ["season", "team_name",
               "PRESEASON KADJ EM", "PRESEASON KADJ EM RANK",
               "KADJ EM CHANGE", "KADJ EM RANK CHANGE"]
    kp_sub = kp_pre[[c for c in kp_cols if c in kp_pre.columns]].drop_duplicates(
        subset=["season", "team_name"])
    base = base.merge(kp_sub, on=["season", "team_name"], how="left")
    log.info("After KenPom_Preseason merge: %d rows", len(base))

    # --- Merge Teamsheet Ranks (BPI, NET — 2019+) ---
    tsr_cols = ["season", "team_name", "BPI", "NET", "KPI", "SOR",
                "Q1 W", "Q1 L", "Q2 W", "Q2 L"]
    # Avoid column name collision with Resumes Q1 W
    tsr_rename = {}
    for c in ["Q1 W", "Q1 L", "Q2 W", "Q2 L"]:
        tsr_rename[c] = f"TSR_{c}"
    ts_sub = ts_ranks[[c for c in tsr_cols if c in ts_ranks.columns]].copy()
    ts_sub.rename(columns=tsr_rename, inplace=True)
    ts_sub = ts_sub.drop_duplicates(subset=["season", "team_name"])
    base = base.merge(ts_sub, on=["season", "team_name"], how="left")
    log.info("After Teamsheet_Ranks merge: %d rows", len(base))

    # --- Merge Tournament Locations (aggregate per team per year across rounds) ---
    # For the per-game location data, we need round-specific info.
    # Store the locations separately — they'll be joined at the game level.
    # For now, compute average distance and timezone for the first round.
    tl_r64 = tl[tl["CURRENT ROUND"] == 64][
        ["season", "team_name", "DISTANCE (MI)", "TIME ZONES CROSSED", "DIRECTION"]
    ].drop_duplicates(subset=["season", "team_name"])
    tl_r64.rename(columns={
        "DISTANCE (MI)": "R64_DISTANCE_MI",
        "TIME ZONES CROSSED": "R64_TZ_CROSSED",
        "DIRECTION": "R64_DIRECTION",
    }, inplace=True)
    base = base.merge(tl_r64, on=["season", "team_name"], how="left")
    log.info("After Tournament_Locations merge: %d rows", len(base))

    log.info("Historical team stats complete: %d rows × %d columns", base.shape[0], base.shape[1])
    return base


# =========================================================================
# 4.  BUILD HISTORICAL GAMES DataFrame
# =========================================================================

def build_historical_games(
    matchups: pd.DataFrame,
    team_stats: pd.DataFrame,
    locations: pd.DataFrame,
) -> pd.DataFrame:
    """Pair tournament matchups into Team A vs Team B games with all stats.

    Games are formed by consecutive row pairs sorted descending by BY YEAR NO
    within each season. Target: did Team A (first of each pair) win?
    """
    # Filter to years 2008-2025
    matchups = matchups[(matchups.season >= 2008) & (matchups.season <= 2025)].copy()

    games = []
    for season, season_df in matchups.groupby("season"):
        sorted_df = season_df.sort_values("BY YEAR NO", ascending=False).reset_index(drop=True)
        for i in range(0, len(sorted_df) - 1, 2):
            row_a = sorted_df.iloc[i]
            row_b = sorted_df.iloc[i + 1]

            score_a = row_a["SCORE"]
            score_b = row_b["SCORE"]
            if pd.isna(score_a) or pd.isna(score_b):
                continue

            team_a_won = 1 if score_a > score_b else 0

            games.append({
                "season": int(season),
                "game_id": row_a["BY YEAR NO"],
                "team_a": row_a["team_name"],
                "team_b": row_b["team_name"],
                "seed_a": row_a["SEED"],
                "seed_b": row_b["SEED"],
                "score_a": score_a,
                "score_b": score_b,
                "round": row_a["CURRENT ROUND"],
                "team_a_won": team_a_won,
            })

    games_df = pd.DataFrame(games)
    log.info("Paired %d tournament games from matchups", len(games_df))

    # Join team stats for team A
    stats_a = team_stats.copy()
    stats_a.columns = [f"{c}_a" if c not in ("season", "team_name") else c for c in stats_a.columns]
    stats_a.rename(columns={"team_name": "team_a"}, inplace=True)
    games_df = games_df.merge(stats_a, on=["season", "team_a"], how="left")

    # Join team stats for team B
    stats_b = team_stats.copy()
    stats_b.columns = [f"{c}_b" if c not in ("season", "team_name") else c for c in stats_b.columns]
    stats_b.rename(columns={"team_name": "team_b"}, inplace=True)
    games_df = games_df.merge(stats_b, on=["season", "team_b"], how="left")

    # Join per-game location data for each team
    loc_cols_base = ["DISTANCE (MI)", "TIME ZONES CROSSED", "DIRECTION"]
    for side, team_col in [("a", "team_a"), ("b", "team_b")]:
        loc_side = locations[["season", "team_name", "CURRENT ROUND"] + loc_cols_base].copy()
        loc_side.rename(columns={"team_name": team_col, "CURRENT ROUND": "round"}, inplace=True)
        loc_side.rename(columns={c: f"LOC_{c}_{side}" for c in loc_cols_base}, inplace=True)
        loc_side = loc_side.drop_duplicates(subset=["season", team_col, "round"])
        games_df = games_df.merge(loc_side, on=["season", team_col, "round"], how="left")

    log.info("Historical games with stats: %d rows × %d columns", games_df.shape[0], games_df.shape[1])
    return games_df


# =========================================================================
# 5.  BUILD CURRENT (2026) TEAMS DataFrame
# =========================================================================

def build_current_teams(
    bracket: dict,
    kp26: pd.DataFrame,
    bt26: pd.DataFrame,
    coach_results: pd.DataFrame,
    seed_results: pd.DataFrame,
    team_results: pd.DataFrame,
    dev: pd.DataFrame,
    canonical: set[str],
    cache: dict[str, str],
) -> pd.DataFrame:
    """Build one row per 2026 bracket team with all available stats."""

    # Extract teams from bracket
    bracket_teams = []
    for region in ["East", "South", "West", "Midwest"]:
        for entry in bracket[region]["teams"]:
            team = entry["team"]
            seed = entry["seed"]
            record = entry.get("record", "")
            if "TBD" in team:
                # First Four — use the first listed team as default
                ff_match = re.search(r"\((.+?) or (.+?)\)", team)
                if ff_match:
                    team = ff_match.group(1)
                    record = ""
            bracket_teams.append({
                "team_name": resolve_name(team, canonical, cache),
                "seed": seed,
                "region": region,
                "record": record,
            })

    teams_df = pd.DataFrame(bracket_teams)
    log.info("Bracket teams: %d (including First Four defaults)", len(teams_df))

    # --- Merge KenPom 2026 ---
    kp26_clean = kp26.copy()
    kp26_clean["team_name"] = kp26_clean["team_name"].apply(
        lambda x: resolve_name(x, canonical, cache))
    kp26_cols = ["team_name", "Rank", "NetRtg", "ORtg", "ORtg_Rank",
                 "DRtg", "DRtg_Rank", "AdjT", "AdjT_Rank",
                 "Luck", "Luck_Rank",
                 "SOS_NetRtg", "SOS_NetRtg_Rank",
                 "SOS_ORtg", "SOS_DRtg",
                 "NCSOS_NetRtg"]
    kp26_sub = kp26_clean[[c for c in kp26_cols if c in kp26_clean.columns]].copy()
    kp26_sub.rename(columns={"Rank": "KP_RANK", "NetRtg": "KP_AdjEM"}, inplace=True)
    teams_df = teams_df.merge(kp26_sub, on="team_name", how="left")
    matched_kp = teams_df["KP_AdjEM"].notna().sum()
    log.info("KenPom 2026 matched: %d/%d teams", matched_kp, len(teams_df))

    # --- Merge Barttorvik 2026 ---
    bt26_clean = bt26.copy()
    bt26_clean["team_name"] = bt26_clean["team_name"].apply(
        lambda x: resolve_name(x, canonical, cache))
    bt_cols = ["team_name", "adjoe", "adjde", "barthag", "adjt",
               "WAB", "elite SOS", "sos", "ncsos"]
    bt_rename = {
        "adjoe": "BT_AdjO", "adjde": "BT_AdjD",
        "barthag": "BT_BARTHAG", "adjt": "BT_AdjT",
        "WAB": "BT_WAB", "elite SOS": "BT_ELITE_SOS",
        "sos": "BT_SOS", "ncsos": "BT_NCSOS",
    }
    bt26_sub = bt26_clean[[c for c in bt_cols if c in bt26_clean.columns]].copy()
    bt26_sub.rename(columns=bt_rename, inplace=True)
    bt26_sub = bt26_sub.drop_duplicates(subset=["team_name"])
    teams_df = teams_df.merge(bt26_sub, on="team_name", how="left")
    matched_bt = teams_df["BT_AdjO"].notna().sum()
    log.info("Barttorvik 2026 matched: %d/%d teams", matched_bt, len(teams_df))

    # --- Merge additional Barttorvik columns (efg, tov, oreb, etc.) ---
    bt_extra_cols = {
        "team_name": "team_name",
        "record": "BT_record",
        "rank": "BT_RANK",
    }
    # Map the column names from barttorvik to standardized names
    bt_stat_map = {}
    for orig_col in bt26_clean.columns:
        lc = orig_col.lower().strip()
        # Skip already merged
        if orig_col in ["team_name", "adjoe", "adjde", "barthag", "adjt", "WAB", "elite SOS", "sos", "ncsos"]:
            continue
        bt_stat_map[orig_col] = f"BT_{orig_col}"

    bt_extra = bt26_clean[["team_name"] + list(bt_stat_map.keys())].copy()
    bt_extra.rename(columns=bt_stat_map, inplace=True)
    bt_extra = bt_extra.drop_duplicates(subset=["team_name"])
    teams_df = teams_df.merge(bt_extra, on="team_name", how="left")

    # --- Merge coach data from DEV March Madness (2025 season as proxy for 2026) ---
    dev_2025 = dev[dev["season"] == 2025][["team_name", "Current Coach", "Since"]].copy()
    dev_2025 = dev_2025.drop_duplicates(subset=["team_name"])
    teams_df = teams_df.merge(dev_2025, on="team_name", how="left")

    # Look up coach in Coach_Results
    coach_map = coach_results.set_index("coach_name")
    coach_pake = []
    coach_games = []
    coach_win_pct = []
    for _, row in teams_df.iterrows():
        coach = row.get("Current Coach")
        if pd.notna(coach) and coach in coach_map.index:
            cr = coach_map.loc[coach]
            coach_pake.append(cr.get("PAKE", np.nan))
            coach_games.append(cr.get("GAMES", np.nan))
            coach_win_pct.append(cr.get("WIN%", np.nan))
        else:
            coach_pake.append(np.nan)
            coach_games.append(np.nan)
            coach_win_pct.append(np.nan)
    teams_df["COACH_PAKE"] = coach_pake
    teams_df["COACH_GAMES"] = coach_games
    teams_df["COACH_WIN_PCT"] = coach_win_pct
    matched_coach = teams_df["COACH_PAKE"].notna().sum()
    log.info("Coach data matched: %d/%d teams", matched_coach, len(teams_df))

    # --- Merge seed historical performance ---
    seed_res = seed_results.copy()
    seed_res.rename(columns={"SEED": "seed", "WIN%": "SEED_HIST_WIN_PCT",
                             "PAKE": "SEED_PAKE", "CHAMP%": "SEED_CHAMP_PCT"}, inplace=True)
    teams_df = teams_df.merge(
        seed_res[["seed", "SEED_HIST_WIN_PCT", "SEED_PAKE", "SEED_CHAMP_PCT"]],
        on="seed", how="left")

    # --- Merge team (program) historical performance ---
    team_res = team_results.copy()
    for col in ["CHAMP%", "F4%"]:
        if col in team_res.columns:
            team_res[col] = team_res[col].astype(str).str.replace("%", "", regex=False)
            team_res[col] = pd.to_numeric(team_res[col], errors="coerce")
    team_res.rename(columns={
        "WIN%": "PROG_WIN_PCT", "PAKE": "PROG_PAKE",
        "F4%": "PROG_F4_PCT", "CHAMP%": "PROG_CHAMP_PCT",
        "GAMES": "PROG_TOURN_GAMES",
    }, inplace=True)
    teams_df = teams_df.merge(
        team_res[["team_name", "PROG_WIN_PCT", "PROG_PAKE",
                  "PROG_F4_PCT", "PROG_CHAMP_PCT", "PROG_TOURN_GAMES"]],
        on="team_name", how="left")
    matched_prog = teams_df["PROG_PAKE"].notna().sum()
    log.info("Program pedigree matched: %d/%d teams", matched_prog, len(teams_df))

    log.info("Current teams complete: %d rows × %d columns", teams_df.shape[0], teams_df.shape[1])
    return teams_df


# =========================================================================
# 6.  COACH FEATURES FOR HISTORICAL DATA
# =========================================================================

def add_coach_features_historical(
    team_stats: pd.DataFrame,
    dev: pd.DataFrame,
    coach_results: pd.DataFrame,
    canonical: set[str],
    cache: dict[str, str],
) -> pd.DataFrame:
    """Add coach PAKE and experience to historical team stats.

    Uses DEV March Madness 'Current Coach' + 'Since' to determine
    if the current coach was coaching in that year.
    Only valid for years >= coach's start year.
    """
    # Get coach mapping from DEV (one row per team per year)
    dev_coaches = dev[["season", "team_name", "Current Coach", "Since"]].copy()
    dev_coaches = dev_coaches.drop_duplicates(subset=["season", "team_name"])

    # Parse Since: format like 202223 → coach started in year 2023
    # (the second year of the academic year)
    def parse_since(val):
        if pd.isna(val):
            return np.nan
        s = str(int(val))
        if len(s) == 6:
            return int(s[4:6]) + 2000 if int(s[4:6]) < 50 else int(s[4:6]) + 1900
        return np.nan

    dev_coaches["coach_start_year"] = dev_coaches["Since"].apply(parse_since)

    # Only keep rows where the coach was active
    dev_coaches["coach_valid"] = dev_coaches["season"] >= dev_coaches["coach_start_year"]
    dev_coaches.loc[~dev_coaches["coach_valid"], "Current Coach"] = np.nan

    # Look up coach stats
    coach_map = coach_results.set_index("coach_name")
    dev_coaches["COACH_PAKE"] = dev_coaches["Current Coach"].map(
        lambda c: coach_map.loc[c, "PAKE"] if pd.notna(c) and c in coach_map.index else np.nan
    )
    dev_coaches["COACH_GAMES"] = dev_coaches["Current Coach"].map(
        lambda c: coach_map.loc[c, "GAMES"] if pd.notna(c) and c in coach_map.index else np.nan
    )
    dev_coaches["COACH_WIN_PCT"] = dev_coaches["Current Coach"].map(
        lambda c: coach_map.loc[c, "WIN%"] if pd.notna(c) and c in coach_map.index else np.nan
    )

    coach_merge = dev_coaches[["season", "team_name", "COACH_PAKE", "COACH_GAMES", "COACH_WIN_PCT"]]
    coach_merge = coach_merge.drop_duplicates(subset=["season", "team_name"])

    team_stats = team_stats.merge(coach_merge, on=["season", "team_name"], how="left")
    valid_count = team_stats["COACH_PAKE"].notna().sum()
    log.info("Coach features added: %d/%d team-years have valid coach data",
             valid_count, len(team_stats))
    return team_stats


# =========================================================================
# 7.  ADD PROGRAM PEDIGREE TO HISTORICAL DATA
# =========================================================================

def add_program_pedigree(
    team_stats: pd.DataFrame,
    team_results: pd.DataFrame,
) -> pd.DataFrame:
    """Add all-time program tournament performance to historical stats."""
    tr = team_results.copy()
    # Clean percentage columns: strip '%' and convert to float
    for col in ["CHAMP%", "F4%"]:
        if col in tr.columns:
            tr[col] = tr[col].astype(str).str.replace("%", "", regex=False)
            tr[col] = pd.to_numeric(tr[col], errors="coerce")
    tr.rename(columns={
        "WIN%": "PROG_WIN_PCT", "PAKE": "PROG_PAKE",
        "F4%": "PROG_F4_PCT", "CHAMP%": "PROG_CHAMP_PCT",
        "GAMES": "PROG_TOURN_GAMES",
    }, inplace=True)
    cols = ["team_name", "PROG_WIN_PCT", "PROG_PAKE",
            "PROG_F4_PCT", "PROG_CHAMP_PCT", "PROG_TOURN_GAMES"]
    team_stats = team_stats.merge(tr[[c for c in cols if c in tr.columns]],
                                  on="team_name", how="left")
    return team_stats


# =========================================================================
# 8.  MAIN PIPELINE
# =========================================================================

def run_pipeline() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """Execute the full data pipeline.

    Returns:
        historical_games_df: One row per tournament game (2008-2025)
        current_teams_df: One row per 2026 bracket team
        reference_data: Dict of reference DataFrames
        bracket: The 2026 bracket structure
    """
    log.info("=" * 60)
    log.info("STARTING DATA PIPELINE")
    log.info("=" * 60)

    # ------------------------------------------------------------------
    # Load everything
    # ------------------------------------------------------------------
    log.info("--- Loading Category A (Historical) ---")
    kb = load_kenpom_barttorvik()
    bn = load_barttorvik_neutral()
    matchups = load_tournament_matchups()
    locations = load_tournament_locations()
    resumes = load_resumes()
    tr = load_team_rankings()
    ss = load_shooting_splits()
    kp_pre = load_kenpom_preseason()
    dev = load_dev_march_madness()
    hc_idx = load_heat_check_tournament_index()

    log.info("--- Loading Category B (2026) ---")
    kp26 = load_kenpom_2026()
    bt26 = load_barttorvik_2026()
    bracket = load_bracket_2026()
    picks26 = load_public_picks_2026()

    log.info("--- Loading Category C (Reference) ---")
    coach_results = load_coach_results()
    seed_results = load_seed_results()
    team_results = load_team_results()
    conf_results = load_conference_results()
    upset_info = load_upset_seed_info()
    ts_ranks = load_teamsheet_ranks()

    # ------------------------------------------------------------------
    # Standardize team names
    # ------------------------------------------------------------------
    log.info("--- Standardizing team names ---")
    canonical = build_canonical_names(kb, kp26, bt26)
    cache: dict[str, str] = {}

    kb = standardize_names(kb, canonical, cache, source="KenPom_Barttorvik")
    bn = standardize_names(bn, canonical, cache, source="Barttorvik_Neutral")
    matchups = standardize_names(matchups, canonical, cache, source="Tournament_Matchups")
    locations = standardize_names(locations, canonical, cache, source="Tournament_Locations")
    resumes = standardize_names(resumes, canonical, cache, source="Resumes")
    tr = standardize_names(tr, canonical, cache, source="TeamRankings")
    ss = standardize_names(ss, canonical, cache, source="Shooting_Splits")
    kp_pre = standardize_names(kp_pre, canonical, cache, source="KenPom_Preseason")
    dev = standardize_names(dev, canonical, cache, source="DEV_March_Madness")
    ts_ranks = standardize_names(ts_ranks, canonical, cache, source="Teamsheet_Ranks")
    team_results = standardize_names(team_results, canonical, cache, source="Team_Results")
    hc_idx = standardize_names(hc_idx, canonical, cache, source="Heat_Check_Index")

    # ------------------------------------------------------------------
    # Build historical team stats
    # ------------------------------------------------------------------
    log.info("--- Building historical team stats ---")
    hist_team_stats = build_historical_team_stats(
        kb, bn, dev, resumes, tr, ss, kp_pre, locations, ts_ranks
    )

    # Add coach features
    hist_team_stats = add_coach_features_historical(
        hist_team_stats, dev, coach_results, canonical, cache
    )

    # Add program pedigree
    hist_team_stats = add_program_pedigree(hist_team_stats, team_results)

    # ------------------------------------------------------------------
    # Build historical games
    # ------------------------------------------------------------------
    log.info("--- Building historical games ---")
    historical_games_df = build_historical_games(matchups, hist_team_stats, locations)

    # ------------------------------------------------------------------
    # Build 2026 current teams
    # ------------------------------------------------------------------
    log.info("--- Building 2026 current teams ---")
    current_teams_df = build_current_teams(
        bracket, kp26, bt26, coach_results, seed_results,
        team_results, dev, canonical, cache
    )

    # ------------------------------------------------------------------
    # Pack reference data
    # ------------------------------------------------------------------
    reference_data = {
        "coach_results": coach_results,
        "seed_results": seed_results,
        "team_results": team_results,
        "conference_results": conf_results,
        "upset_seed_info": upset_info,
        "teamsheet_ranks": ts_ranks,
        "heat_check_index": hc_idx,
        "public_picks_2026": picks26,
        "public_picks_historical": load_public_picks_historical(),
        "tournament_locations": locations,
    }

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("  historical_games_df: %d games × %d columns", *historical_games_df.shape)
    log.info("  current_teams_df:    %d teams × %d columns", *current_teams_df.shape)
    log.info("  reference tables:    %d DataFrames", len(reference_data))
    log.info("=" * 60)

    return historical_games_df, current_teams_df, reference_data, bracket


# =========================================================================
# CLI entry point
# =========================================================================
if __name__ == "__main__":
    hist, curr, refs, bracket = run_pipeline()

    print("\n--- Historical Games Sample ---")
    print(hist[["season", "team_a", "team_b", "seed_a", "seed_b",
                "round", "team_a_won"]].head(10).to_string(index=False))

    print("\n--- 2026 Teams Sample ---")
    cols = ["team_name", "seed", "region", "KP_AdjEM", "BT_AdjO", "BT_AdjD", "BT_BARTHAG"]
    avail = [c for c in cols if c in curr.columns]
    print(curr[avail].sort_values("seed").head(20).to_string(index=False))

    # Null check
    print("\n--- Historical null % (top 20) ---")
    null_pct = hist.isnull().mean().sort_values(ascending=False).head(20)
    for col, pct in null_pct.items():
        print(f"  {col}: {pct:.1%}")

    print("\n--- 2026 Teams null % (top 20) ---")
    null_pct = curr.isnull().mean().sort_values(ascending=False).head(20)
    for col, pct in null_pct.items():
        print(f"  {col}: {pct:.1%}")
