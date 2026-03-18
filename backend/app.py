"""
Backend API — March Madness Bracket Prediction System

FastAPI backend exposing simulation, bracket, upset, team stats,
and model benchmark endpoints.

Run with: uvicorn backend.app:app --reload --port 8000
"""

import json
import logging
import math
import sys
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


def _sanitize(obj):
    """Recursively replace NaN/Inf/numpy types with JSON-safe equivalents."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def nan_safe_response(content):
    """Create a Response with NaN-safe JSON — recursively sanitizes all values."""
    from starlette.responses import Response
    clean = _sanitize(content)
    body = json.dumps(clean)
    return Response(content=body, media_type="application/json")

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="March Madness AI Bracket API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state (loaded once at startup) ──────────────────────────
_state = {}


def _get_state():
    """Lazy-load all data and models on first request."""
    if _state:
        return _state

    log.info("Loading data pipeline...")
    from data_pipeline import run_pipeline
    hist, curr, refs, bracket = run_pipeline()

    log.info("Loading ML models...")
    from model import load_trained_models, predict_matchup
    from features import build_matchup_features_2026
    models, config = load_trained_models()

    def ml_predict(ta, tb, rn, sr):
        feats = build_matchup_features_2026(ta, tb, rn, sr)
        return predict_matchup(models, feats.values)

    log.info("Running simulation...")
    from simulator import simulate_tournament
    from pool_equity import compute_all_equity, sim_results_to_win_probs

    sim = simulate_tournament(
        bracket=bracket, predict_fn=ml_predict, current_teams_df=curr,
        equity_df=None, n_sims=50_000, risk=0.0,
        seed_results=refs["seed_results"],
    )
    win_probs = sim_results_to_win_probs(sim["team_results"])
    picks = refs["public_picks_2026"]
    equity_df = compute_all_equity(curr, picks, win_probs_by_team=win_probs)

    # Upsets are computed on-demand in /api/upset-alerts with projected picks
    alerts = None

    # Sanitize DataFrames: replace NaN/Inf with None for JSON safety
    import pandas as pd
    for df in [curr, equity_df, sim["team_results"]]:
        for col in df.select_dtypes(include=["float64", "float32"]).columns:
            df[col] = df[col].where(df[col].notna(), None)

    _state.update({
        "curr": curr,
        "refs": refs,
        "bracket": bracket,
        "models": models,
        "config": config,
        "ml_predict": ml_predict,
        "sim": sim,
        "equity_df": equity_df,
        "alerts": alerts,
    })
    log.info("Backend ready.")
    return _state


# ── Request/Response models ────────────────────────────────────────

class SimulationRequest(BaseModel):
    risk: float = 0.3
    pool_size: int = 1_000_000
    year: int = 2026


class OverrideRequest(BaseModel):
    """Request to override a single pick and recalculate downstream."""
    round: int                # Round of the game to override (64, 32, 16, 8, 4, 2)
    team_a: str               # Team A in the game
    team_b: str               # Team B in the game
    new_winner: str           # The team that should win (must be team_a or team_b)
    region: str               # Region of the game
    current_picks: list       # Full current bracket state as list of pick dicts


# ── Endpoints ──────────────────────────────────────────────────────

@app.post("/api/run-simulation")
def run_simulation(req: SimulationRequest):
    """Run bracket optimization at the requested risk level."""
    state = _get_state()
    from optimizer import optimize_bracket, compare_brackets, compute_public_overlap

    safe = optimize_bracket(
        state["bracket"], state["curr"], state["ml_predict"],
        state["equity_df"], state["refs"]["seed_results"],
        risk=0.1, pool_size=req.pool_size,
    )
    equity = optimize_bracket(
        state["bracket"], state["curr"], state["ml_predict"],
        state["equity_df"], state["refs"]["seed_results"],
        risk=req.risk, pool_size=req.pool_size,
    )

    comparison = compare_brackets(safe, equity)
    sim_df = state["sim"]["team_results"]

    # Enrich picks with Vegas spreads
    vegas = state["refs"].get("vegas_lines_2026")
    vegas_map = {}
    if vegas is not None and len(vegas) > 0:
        for _, vr in vegas.iterrows():
            vegas_map[(str(vr.get("team_a", "")), str(vr.get("team_b", "")))] = {
                "spread_a": vr.get("spread_a"), "spread_b": vr.get("spread_b"),
            }
    for bracket_result in [safe, equity]:
        for _, pick in bracket_result["picks"].iterrows():
            vdata = vegas_map.get((pick["team_a"], pick["team_b"])) or \
                    vegas_map.get((pick["team_b"], pick["team_a"]))
            if vdata:
                bracket_result["picks"].loc[pick.name, "vegas_spread_a"] = vdata["spread_a"]
                bracket_result["picks"].loc[pick.name, "vegas_spread_b"] = vdata["spread_b"]

    # Enrich picks with equity data (true_win_prob, public_pick_pct) for the Equity Dashboard
    equity_df = state["equity_df"]
    for bracket_result in [safe, equity]:
        picks_df = bracket_result["picks"]
        for idx, pick in picks_df.iterrows():
            rd = pick["round"]
            # Look up equity data for team_a
            eq_a = equity_df[
                (equity_df["team_name"] == pick["team_a"]) &
                (equity_df["round"] == rd)
            ]
            if len(eq_a) > 0:
                picks_df.loc[idx, "true_win_prob_a"] = eq_a.iloc[0]["win_prob"]
                picks_df.loc[idx, "public_pick_pct_a"] = eq_a.iloc[0]["public_pick_pct"]
                picks_df.loc[idx, "equity_score_a"] = eq_a.iloc[0]["blended_score"]
            # Look up equity data for team_b
            eq_b = equity_df[
                (equity_df["team_name"] == pick["team_b"]) &
                (equity_df["round"] == rd)
            ]
            if len(eq_b) > 0:
                picks_df.loc[idx, "true_win_prob_b"] = eq_b.iloc[0]["win_prob"]
                picks_df.loc[idx, "public_pick_pct_b"] = eq_b.iloc[0]["public_pick_pct"]
                picks_df.loc[idx, "equity_score_b"] = eq_b.iloc[0]["blended_score"]

    # Sanitize optimizer picks (may contain NaN from ML features)
    def _clean_df_records(df):
        return _sanitize(df.to_dict(orient="records"))

    return nan_safe_response({
        "safe_bracket": {
            "champion": safe["champion"],
            "final_four": safe["final_four"],
            "picks": _clean_df_records(safe["picks"]),
            "corrections": safe["corrections"],
            "public_overlap": compute_public_overlap(safe["picks"]),
            "upsets": int(safe["picks"]["is_upset"].sum()),
        },
        "equity_bracket": {
            "champion": equity["champion"],
            "final_four": equity["final_four"],
            "picks": _clean_df_records(equity["picks"]),
            "corrections": equity["corrections"],
            "public_overlap": compute_public_overlap(equity["picks"]),
            "upsets": int(equity["picks"]["is_upset"].sum()),
        },
        "comparison": {
            "total_games": comparison["total_games"],
            "same_picks": comparison["same_picks"],
            "different_picks": comparison["different_picks"],
            "overlap_pct": comparison["overlap_pct"],
            "differences": _clean_df_records(comparison["differences"]),
        },
        "simulation": {
            "n_sims": state["sim"]["n_sims"],
            "top_contenders": _clean_df_records(sim_df.head(20)),
            "all_teams": _clean_df_records(sim_df),
            "champion_counts": state["sim"]["champion_counts"],
        },
        "risk": req.risk,
        "pool_size": req.pool_size,
    })


@app.get("/api/bracket-data")
def get_bracket_data():
    """Return 2026 bracket structure."""
    state = _get_state()
    return state["bracket"]


class UpsetAlertsRequest(BaseModel):
    """Optional custom picks for upset detection (e.g. after overrides)."""
    picks: list = None  # If provided, use these as projected picks


@app.post("/api/upset-alerts")
def post_upset_alerts(req: UpsetAlertsRequest):
    """Return upset detection results using custom picks (e.g. after overrides)."""
    return _run_upset_alerts(custom_picks=req.picks)


@app.get("/api/upset-alerts")
def get_upset_alerts():
    """Return upset detection results for ALL rounds.

    Uses projected picks from the equity bracket for R32+ matchups.
    """
    return _run_upset_alerts(custom_picks=None)


def _run_upset_alerts(custom_picks: list = None):
    """Shared upset alert logic. Uses custom_picks if provided, otherwise generates from equity bracket."""
    state = _get_state()

    from upset_detector import detect_upsets
    from optimizer import optimize_bracket

    curr = state["curr"]
    refs = state["refs"]
    bracket = state["bracket"]

    if custom_picks:
        projected_picks = custom_picks
    else:
        # Generate from equity bracket
        equity_df = state["equity_df"]
        eq_bracket = optimize_bracket(
            bracket, curr, state["ml_predict"], equity_df,
            refs["seed_results"], risk=0.5)
        projected_picks = eq_bracket["picks"].to_dict(orient="records")

    vegas_lines = refs.get("vegas_lines_2026")

    alerts = detect_upsets(
        curr, bracket,
        refs["coach_results"],
        refs["seed_results"],
        refs["upset_seed_info"],
        projected_picks=projected_picks,
        vegas_lines=vegas_lines,
    )

    # Build per-round summary
    round_summary = {}
    for rd in [64, 32, 16, 8, 4]:
        rd_df = alerts[alerts["round"] == rd]
        round_summary[f"R{rd}"] = {
            "total": len(rd_df),
            "high": int(rd_df["high_alert"].sum()),
            "watch": int(((rd_df["upset_score"] >= 2) & (~rd_df["high_alert"])).sum()),
        }

    return nan_safe_response({
        "total_games": len(alerts),
        "high_alerts": int(alerts["high_alert"].sum()),
        "round_summary": round_summary,
        "alerts": _sanitize(alerts.to_dict(orient="records")),
    })


@app.get("/api/team-stats/{team_name}")
def get_team_stats(team_name: str):
    """Return all 2026 stats for a specific team."""
    state = _get_state()
    curr = state["curr"]
    # Try exact match first, then case-insensitive
    team = curr[curr["team_name"] == team_name]
    if len(team) == 0:
        team = curr[curr["team_name"].str.lower() == team_name.lower()]
    if len(team) == 0:
        # Fuzzy substring match
        team = curr[curr["team_name"].str.contains(team_name, case=False, na=False)]
    if len(team) == 0:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    row = team.iloc[0]
    stats = {}
    for col in row.index:
        val = row[col]
        if hasattr(val, "item"):
            stats[col] = val.item()
        else:
            stats[col] = val

    # Add simulation results
    sim_df = state["sim"]["team_results"]
    sim_row = sim_df[sim_df["team_name"] == row["team_name"]]
    if len(sim_row) > 0:
        sr = sim_row.iloc[0]
        stats["sim_R64_pct"] = float(sr.get("R64_pct", 0))
        stats["sim_R32_pct"] = float(sr.get("R32_pct", 0))
        stats["sim_S16_pct"] = float(sr.get("R16_pct", 0))
        stats["sim_E8_pct"] = float(sr.get("R8_pct", 0))
        stats["sim_F4_pct"] = float(sr.get("R4_pct", 0))
        stats["sim_champ_pct"] = float(sr.get("champ_pct", 0))

    # Add equity scores
    eq_df = state["equity_df"]
    team_eq = eq_df[eq_df["team_name"] == row["team_name"]]
    if len(team_eq) > 0:
        stats["equity"] = team_eq[["round", "raw_equity", "blended_score"]].to_dict(orient="records")

    return nan_safe_response(stats)


@app.get("/api/model-benchmark")
def get_model_benchmark():
    """Return model accuracy vs baselines."""
    state = _get_state()
    config = state["config"]
    benchmarks = config.get("benchmarks", {})
    return {
        "benchmarks": benchmarks,
        "feature_names": config.get("feature_names", []),
        "ensemble_weights": {"xgb": 0.45, "lgb": 0.35, "nn": 0.20},
    }


@app.get("/api/equity-data")
def get_equity_data():
    """Return pool equity scores for all teams."""
    state = _get_state()
    eq = state["equity_df"]
    return nan_safe_response({
        "equity_scores": _sanitize(eq.to_dict(orient="records")),
    })


@app.get("/api/vegas-lines")
def get_vegas_lines():
    """Return Vegas opening lines for R64 games."""
    state = _get_state()
    vegas = state["refs"].get("vegas_lines_2026")
    if vegas is None or len(vegas) == 0:
        return {"games": [], "available": False}
    return nan_safe_response({
        "games": _sanitize(vegas.to_dict(orient="records")),
        "available": True,
    })


@app.post("/api/override-pick")
def override_pick(req: OverrideRequest):
    """Override a single pick and recalculate all downstream games.

    Takes the current bracket state, applies the override, then re-runs
    downstream matchups using ML win probabilities. Does NOT re-run the
    full 50k simulation — uses cached pairwise probabilities.
    """
    state = _get_state()
    from features import build_matchup_features_2026
    from model import predict_matchup

    curr = state["curr"]
    teams_lookup = curr.set_index("team_name")
    models = state["models"]
    seed_results = state["refs"]["seed_results"]

    # Build pairwise probability cache (or reuse from state)
    if "prob_cache" not in state:
        cache = {}
        all_names = list(teams_lookup.index)
        for i, a in enumerate(all_names):
            for b in all_names[i + 1:]:
                feats = build_matchup_features_2026(
                    teams_lookup.loc[a], teams_lookup.loc[b], 64, seed_results)
                prob = predict_matchup(models, feats.values)
                cache[(a, b)] = prob
                cache[(b, a)] = 1.0 - prob
        state["prob_cache"] = cache
    prob_cache = state["prob_cache"]

    # Reconstruct picks as a list of mutable dicts
    picks = [dict(p) for p in req.current_picks]

    # Find the overridden game and apply
    override_applied = False
    changed_picks = []

    for p in picks:
        if (p["round"] == req.round and
            p["team_a"] == req.team_a and p["team_b"] == req.team_b):
            old_winner = p["winner"]
            p["winner"] = req.new_winner
            p["winner_seed"] = p["seed_a"] if req.new_winner == p["team_a"] else p["seed_b"]
            p["is_upset"] = (p["winner_seed"] > min(p["seed_a"], p["seed_b"]))
            p["is_override"] = True
            override_applied = True
            if old_winner != req.new_winner:
                changed_picks.append({
                    "round": req.round,
                    "region": req.region,
                    "old_winner": old_winner,
                    "new_winner": req.new_winner,
                    "type": "override",
                })
            break

    if not override_applied:
        raise HTTPException(status_code=400,
                            detail=f"Game not found: R{req.round} {req.team_a} vs {req.team_b}")

    # Recalculate downstream rounds
    # Round order: 64 → 32 → 16 → 8 → 4 → 2
    downstream_rounds = [r for r in [64, 32, 16, 8, 4, 2] if r < req.round]

    # Build a lookup of picks by (round, region, team_a, team_b)
    def get_round_picks(rd):
        return [p for p in picks if p["round"] == rd]

    def get_seed(team_name):
        if team_name in teams_lookup.index:
            return int(teams_lookup.loc[team_name].get("seed", 8))
        return 8

    for rd in downstream_rounds:
        rd_picks = get_round_picks(rd)
        # For each game in this round, check if either team was affected
        # by the override (i.e., a team that was supposed to be here is
        # now replaced by the override winner)
        prev_rd = {64: None, 32: 64, 16: 32, 8: 16, 4: 8, 2: 4}[rd]
        if prev_rd is None:
            continue

        # Get winners from the previous round to determine who plays in this round
        prev_winners = {}
        for p in get_round_picks(prev_rd):
            # Map: (region, game_index_in_round) -> winner
            key = (p.get("region", ""), p.get("team_a", ""), p.get("team_b", ""))
            prev_winners[key] = p["winner"]

        # Rebuild this round's matchups from previous round winners
        prev_picks = get_round_picks(prev_rd)

        if rd in [32, 16, 8]:
            # Region rounds: pair consecutive previous-round winners
            region_games = {}
            for p in prev_picks:
                region = p.get("region", "")
                if region not in region_games:
                    region_games[region] = []
                region_games[region].append(p["winner"])

            new_rd_picks = []
            for p in rd_picks:
                region = p.get("region", "")
                winners = region_games.get(region, [])

                # Find which pair of previous winners feeds this game
                # The bracket structure pairs winners sequentially
                game_idx = rd_picks.index(p)
                region_rd_picks = [x for x in rd_picks if x.get("region") == region]
                local_idx = region_rd_picks.index(p)

                team_a_new = winners[local_idx * 2] if local_idx * 2 < len(winners) else p["team_a"]
                team_b_new = winners[local_idx * 2 + 1] if local_idx * 2 + 1 < len(winners) else p["team_b"]

                if team_a_new != p["team_a"] or team_b_new != p["team_b"]:
                    # Matchup changed — recalculate
                    prob = prob_cache.get((team_a_new, team_b_new), 0.5)
                    new_winner = team_a_new if prob >= 0.5 else team_b_new
                    seed_a = get_seed(team_a_new)
                    seed_b = get_seed(team_b_new)
                    old_winner = p["winner"]

                    p["team_a"] = team_a_new
                    p["team_b"] = team_b_new
                    p["seed_a"] = seed_a
                    p["seed_b"] = seed_b
                    p["ml_prob_a"] = prob
                    p["winner"] = new_winner
                    p["winner_seed"] = seed_a if new_winner == team_a_new else seed_b
                    p["is_upset"] = (p["winner_seed"] > min(seed_a, seed_b))
                    p["is_recalculated"] = True

                    if old_winner != new_winner:
                        changed_picks.append({
                            "round": rd,
                            "region": region,
                            "old_winner": old_winner,
                            "new_winner": new_winner,
                            "type": "cascade",
                        })

        elif rd == 4:
            # Final Four: East winner vs South winner, West winner vs Midwest winner
            e8_picks = get_round_picks(8)
            region_winners = {}
            for p in e8_picks:
                region_winners[p.get("region", "")] = p["winner"]

            ff_matchups = [
                (region_winners.get("East", ""), region_winners.get("South", "")),
                (region_winners.get("West", ""), region_winners.get("Midwest", "")),
            ]

            for i, p in enumerate(rd_picks):
                if i < len(ff_matchups):
                    team_a_new, team_b_new = ff_matchups[i]
                    if team_a_new and team_b_new and (team_a_new != p["team_a"] or team_b_new != p["team_b"]):
                        prob = prob_cache.get((team_a_new, team_b_new), 0.5)
                        new_winner = team_a_new if prob >= 0.5 else team_b_new
                        old_winner = p["winner"]
                        p["team_a"] = team_a_new
                        p["team_b"] = team_b_new
                        p["seed_a"] = get_seed(team_a_new)
                        p["seed_b"] = get_seed(team_b_new)
                        p["ml_prob_a"] = prob
                        p["winner"] = new_winner
                        p["winner_seed"] = get_seed(new_winner)
                        p["is_upset"] = False
                        p["is_recalculated"] = True

                        if old_winner != new_winner:
                            changed_picks.append({
                                "round": 4, "region": "Final Four",
                                "old_winner": old_winner, "new_winner": new_winner,
                                "type": "cascade",
                            })

        elif rd == 2:
            # Championship: winners of the two F4 games
            f4_picks = get_round_picks(4)
            if len(f4_picks) >= 2:
                team_a_new = f4_picks[0]["winner"]
                team_b_new = f4_picks[1]["winner"]
                p = rd_picks[0] if rd_picks else None
                if p and (team_a_new != p["team_a"] or team_b_new != p["team_b"]):
                    prob = prob_cache.get((team_a_new, team_b_new), 0.5)
                    new_winner = team_a_new if prob >= 0.5 else team_b_new
                    old_winner = p["winner"]
                    p["team_a"] = team_a_new
                    p["team_b"] = team_b_new
                    p["seed_a"] = get_seed(team_a_new)
                    p["seed_b"] = get_seed(team_b_new)
                    p["ml_prob_a"] = prob
                    p["winner"] = new_winner
                    p["winner_seed"] = get_seed(new_winner)
                    p["is_upset"] = False
                    p["is_recalculated"] = True

                    if old_winner != new_winner:
                        changed_picks.append({
                            "round": 2, "region": "Championship",
                            "old_winner": old_winner, "new_winner": new_winner,
                            "type": "cascade",
                        })

    # Determine new champion and Final Four
    champ_game = next((p for p in picks if p["round"] == 2), None)
    champion = champ_game["winner"] if champ_game else None

    e8_games = [p for p in picks if p["round"] == 8]
    final_four = {}
    for p in e8_games:
        final_four[p["region"]] = p["winner"]

    return nan_safe_response({
        "picks": _sanitize(picks),
        "champion": champion,
        "final_four": final_four,
        "changes": changed_picks,
        "total_changes": len(changed_picks),
    })
