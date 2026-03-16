# March Madness AI Bracket Predictor

A production-grade NCAA March Madness bracket prediction system powered by a 3-model ML ensemble, Monte Carlo simulation, and pool equity optimization. Built to maximize expected winnings in bracket pools — not just pick accuracy.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![React](https://img.shields.io/badge/React-18-61DAFB) ![XGBoost](https://img.shields.io/badge/XGBoost-Ensemble-green) ![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)

## What This Does

Most bracket tools pick the "most likely" winner of each game. That's a losing strategy in large pools — a bracket that picks all favorites is nearly identical to millions of other brackets.

This system takes a different approach:

1. **ML Model** predicts game-by-game win probabilities using 28 engineered features from KenPom, Barttorvik, and Vegas lines
2. **Monte Carlo Simulator** runs 50,000 full tournaments to get team-specific advancement rates
3. **Pool Equity Engine** compares ML win probabilities against BetMGM championship odds to identify where the betting public is wrong
4. **Bracket Optimizer** generates two brackets: a safe bracket (ML-driven) and an equity bracket (contrarian, maximizing pool differentiation)
5. **11-Condition Upset Detector** with Vegas line integration flags volatile games across all rounds

The equity bracket intentionally picks upsets where the model sees value the public doesn't — the key to winning large bracket pools.

## AI/ML Architecture

### 3-Model Ensemble

| Model | Weight | Type | Purpose |
|-------|--------|------|---------|
| **XGBoost** | 45% | Gradient boosted trees | Primary predictor, handles feature interactions |
| **LightGBM** | 35% | Gradient boosted trees | Secondary, different splitting strategy |
| **PyTorch Neural Net** | 20% | 2-layer MLP (128→64) | Captures non-linear patterns |

All three models are calibrated via **Platt scaling** (`CalibratedClassifierCV`) to produce well-calibrated probabilities, then combined with weighted averaging.

### Training Data

- **1,071 NCAA tournament games** from 2008–2025 (2020 excluded — tournament cancelled)
- **2025 held out** as a final out-of-sample validation set (63 games)
- Training uses **Pre-Tournament AdjEM** from KenPom (not end-of-season) to prevent data leakage

### 28 Engineered Features

| Group | Features | Source |
|-------|----------|--------|
| **Efficiency** (4) | AdjEM diff, BARTHAG diff, AdjO diff, AdjD diff | KenPom, Barttorvik |
| **Stylistic Matchup** (6) | Tempo mismatch, 3PT clash, turnover battle, rebounding, FT rate, shot quality | KenPom, Barttorvik |
| **Variance/Experience** (3) | Experience diff, height diff, talent diff | KenPom, Barttorvik |
| **Luck/Momentum** (4) | Luck rating diff, luck vs top-25, preseason momentum, rank delta | TeamRankings, KenPom Preseason |
| **Historical/Context** (8) | Seed diff, upset rate, KenPom-seed discrepancy, ELO, Q1 wins, auto-bid flags | Resumes, Seed Results, Upset History |
| **Travel** (2) | Distance diff, timezone diff | Tournament Locations |

For 2026 predictions, full feature coverage is achieved for all 68 tournament teams via the KenPom_Barttorvik dataset including 3PT%, TOV%, OREB%, experience, height, and talent.

### Model Performance

| Metric | Ensemble | Chalk Baseline | Vegas Proxy |
|--------|----------|----------------|-------------|
| **Accuracy** | 76.2% | 79.4% | 81.0% |
| **Log Loss** | **0.464** | 0.491 | 0.482 |
| **Brier Score** | **0.149** | 0.156 | 0.156 |
| **AUC** | **0.863** | 0.769 | 0.849 |

The ensemble beats all baselines on log loss, Brier score, and AUC — the metrics that matter for probabilistic predictions and pool equity.

### Regularization

- XGBoost: `max_depth=3`, `n_estimators=150`, `min_child_weight=10`
- LightGBM: `num_leaves=15`, `min_child_samples=20`
- Neural Net: 2 hidden layers, `dropout=0.5`, early stopping with `patience=10`
- Training accuracy under 85% for all models (overfitting resolved)

## Upset Detection

11-condition rule-based detector running on ALL tournament rounds (R64 through F4):

| # | Condition | Source | R64 Trigger Rate |
|---|-----------|--------|-----------------|
| 1 | KenPom rank gap ≤ 15 | KenPom 2026 | 18.8% |
| 2 | Tempo mismatch > 8 possessions | Barttorvik | 3.1% |
| 3 | Favorite overperformed (Luck regression) | KenPom | 34.4% |
| 4 | Underdog coach PAKE > average | Coach Results | 31.2% |
| 5 | Underdog underperformed (Luck regression up) | KenPom | 25.0% |
| 6 | Style clash (both top-30 O/D) | KenPom | 3.1% |
| 7 | Historical upset rate > 30% for seed pairing | Upset History | 37.5% |
| 8 | AdjEM gap < 8 points | KenPom | 31.2% |
| 9 | Favorite WAB rank > 20 | Barttorvik | 37.5% |
| **10** | **Vegas line ≤ 5.5 points** | **BetMGM** | **25.0%** |
| **11** | **Vegas implied upset prob > 25%** | **BetMGM** | **31.2%** |

R64 alerts use known matchups. R32+ alerts use projected matchups from the bracket optimizer.

## Pool Equity System

### Public Pick Source

Championship pick percentages are derived from **BetMGM moneyline odds** (March 15, 2026), converted to implied probabilities and normalized to 100%. Round-by-round picks (R64–F4) use seed-based priors calibrated to ESPN bracket challenge behavior.

Key equity examples:
- **Duke**: 19.8% sim championship vs 13.6% public → equity **1.44** (model more bullish than market)
- **Michigan**: 8.3% sim vs 13.9% public → equity **0.52** (market far more bullish than model)
- **Louisville**: 2.9% sim vs 0.97% public → equity **3.00** (massive contrarian value)

### Equity Formula

```
Equity Score = ML Win Probability / Public Pick Percentage
```

The optimizer blends ML probability with equity at round-dependent weights:
- R64/R32: up to 30% equity
- S16: up to 60% equity
- E8: up to 75% equity
- F4/Championship: up to 85-90% equity

## System Components

```
data_pipeline.py    → Loads 19 data sources, standardizes names, builds team stats
features.py         → Computes 28 differential features per matchup (NaN-native)
model.py            → 3-model ensemble with Platt calibration
upset_detector.py   → 11-condition detector across all rounds with Vegas integration
pool_equity.py      → BetMGM-derived equity scoring
simulator.py        → 50,000 Monte Carlo tournament simulations
optimizer.py        → Risk-tunable bracket optimization with anti-chalk rules
main.py             → Rich CLI with side-by-side bracket output
backend/app.py      → FastAPI backend (8 endpoints including override + Vegas)
frontend/           → React 18 + Vite + TailwindCSS interactive bracket UI
```

## Setup

### Prerequisites
- Python 3.9+, Node.js 18+, Homebrew (macOS for `libomp`)

### Quick Start

```bash
git clone https://github.com/AustinRyan/march-madness-predictor.git
cd march-madness-predictor

# Install Python deps
pip install -r requirements.txt
brew install libomp  # macOS only

# Train models (~3 min)
python model.py

# CLI
python main.py --year 2026 --risk 0.5 --show-upsets --explain

# Backend + Frontend
uvicorn backend.app:app --port 8001
cd frontend && npm install && npm run dev -- --port 5180
# Open http://localhost:5180
```

### CLI Options

```bash
python main.py \
  --year 2026 \
  --risk 0.5 \              # 0.0 = pure chalk, 1.0 = max contrarian
  --pool-size 1000000 \
  --show-upsets \
  --explain \
  --sims 50000 \
  --output table             # table | json | csv
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/run-simulation` | POST | Full simulation + both brackets |
| `/api/bracket-data` | GET | Bracket structure |
| `/api/upset-alerts` | GET | All-round alerts with Vegas conditions |
| `/api/team-stats/{name}` | GET | Full stats for any team |
| `/api/model-benchmark` | GET | Model vs baselines |
| `/api/equity-data` | GET | Pool equity scores |
| `/api/vegas-lines` | GET | Vegas spreads/moneylines |
| `/api/override-pick` | POST | Manual bracket override with cascade |

## Data Files

```
data/
├── historical/     11 files (2008–2026 training + 2026 tournament teams)
├── 2026/           5 files (KenPom, Barttorvik, bracket, public picks, Vegas lines)
├── reference/      6 files (coaches, seeds, teams, conferences, upsets)
└── supplemental/   22 files (extra datasets)
```

## Tech Stack

**Backend**: Python, FastAPI, XGBoost, LightGBM, PyTorch, scikit-learn, SHAP, pandas, numpy

**Frontend**: React 18, Vite, TailwindCSS, Recharts, Framer Motion, Axios

**Data**: KenPom, Barttorvik, BetMGM odds, TeamRankings, Sports-Reference
