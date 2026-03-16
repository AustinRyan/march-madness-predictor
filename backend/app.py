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

    log.info("Computing upsets...")
    from upset_detector import detect_upsets
    alerts = detect_upsets(
        curr, bracket, refs["coach_results"],
        refs["seed_results"], refs["upset_seed_info"],
    )

    # Sanitize DataFrames: replace NaN/Inf with None for JSON safety
    import pandas as pd
    for df in [curr, equity_df, alerts, sim["team_results"]]:
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


@app.get("/api/upset-alerts")
def get_upset_alerts():
    """Return upset detection results for R64 games."""
    state = _get_state()
    alerts = state["alerts"]
    return nan_safe_response({
        "total_games": len(alerts),
        "high_alerts": int(alerts["high_alert"].sum()),
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
