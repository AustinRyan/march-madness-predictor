# March Madness AI Bracket Predictor

A production-grade NCAA March Madness bracket prediction system powered by a 3-model ML ensemble, Monte Carlo simulation, and pool equity optimization. Built to maximize expected winnings in bracket pools — not just pick accuracy.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![React](https://img.shields.io/badge/React-18-61DAFB) ![XGBoost](https://img.shields.io/badge/XGBoost-Ensemble-green) ![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)

## What This Does

Most bracket tools pick the "most likely" winner of each game. That's a losing strategy in large pools — a bracket that picks all favorites is nearly identical to millions of other brackets.

This system takes a different approach:

1. **ML Model** predicts game-by-game win probabilities using 28 engineered features
2. **Monte Carlo Simulator** runs 50,000 full tournaments to get team-specific advancement rates
3. **Pool Equity Engine** identifies where the public is wrong — teams the model rates higher than the crowd expects
4. **Bracket Optimizer** generates two brackets: a safe bracket (ML-driven) and an equity bracket (contrarian, maximizing pool differentiation)

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
| **Stylistic Matchup** (6) | Tempo mismatch, 3PT clash, turnover battle, rebounding, FT rate, shot quality | KenPom, Barttorvik, Shooting Splits |
| **Variance/Experience** (3) | Experience diff, height diff, talent diff | KenPom, Barttorvik |
| **Luck/Momentum** (4) | Luck rating diff, luck vs top-25, preseason momentum, rank delta | TeamRankings, KenPom Preseason |
| **Historical/Context** (8) | Seed diff, upset rate, KenPom-seed discrepancy, ELO, Q1 wins, auto-bid flags | Resumes, Seed Results, Upset History |
| **Travel** (2) | Distance diff, timezone diff | Tournament Locations |

NaN values are preserved (not zero-filled) — XGBoost and LightGBM handle missing values natively via their split algorithms.

### Model Performance

| Metric | Ensemble | Chalk Baseline | Vegas Proxy |
|--------|----------|----------------|-------------|
| **Accuracy** | 76.2% | 79.4% | 81.0% |
| **Log Loss** | **0.465** | 0.491 | 0.482 |
| **Brier Score** | **0.149** | 0.156 | 0.156 |
| **AUC** | **0.862** | 0.769 | 0.849 |

The ensemble beats all baselines on log loss, Brier score, and AUC — the metrics that matter for probabilistic predictions and pool equity. Raw accuracy favors chalk because most games are won by the better seed.

### Regularization (Overfitting Prevention)

After diagnostics revealed 100% training accuracy (severe overfitting), the following fixes were applied:
- XGBoost: `max_depth=3`, `n_estimators=150`, `min_child_weight=10`
- LightGBM: `num_leaves=15`, `min_child_samples=20`
- Neural Net: 2 hidden layers (not 4), `dropout=0.5`, early stopping with `patience=10`
- Removed 4 toxic features: `program_champ_pct` (blue-blood proxy), `coach_pake` (temporal leakage), `coach_experience` (same), `bpi_diff` (35% coverage)

Final training accuracy: 81.6% (XGB), 84.4% (LGB), 72.7% (NN) — under the 85% target.

## Data Sources

All data from real CSV files — no synthetic or mock data.

### Historical Training Data (2008–2025)
| File | Description | Rows |
|------|-------------|------|
| `KenPom Barttorvik.csv` | Combined KenPom + Barttorvik metrics for every tournament team | 1,147 |
| `Barttorvik Neutral.csv` | Neutral-site-only stats (more predictive for tournament) | 1,147 |
| `Tournament Matchups.csv` | Every tournament game with scores | 2,140 |
| `Tournament Locations.csv` | Travel distance and timezone data per game | 2,140 |
| `DEV _ March Madness.csv` | Master 165-column KenPom file with Pre-Tournament metrics | 8,315 |
| `Resumes.csv` | ELO, Q1 wins, bid type | 1,147 |
| `TeamRankings.csv` | Luck metrics and consistency ratings | 1,147 |
| `Shooting Splits.csv` | Shot zone breakdowns (2010+) | 1,017 |
| `KenPom Preseason.csv` | Preseason vs final rankings (momentum) | 884 |

### 2026 Current Season
| File | Description |
|------|-------------|
| `kenpom_2026.csv` | Current KenPom ratings for all 364 D1 teams |
| `barttorvik_2026.csv` | Current Barttorvik T-Rank stats |
| `bracket_2026.json` | Official 2026 NCAA tournament bracket (68 teams) |
| `public_picks_2026.csv` | Public pick percentages (seed-based priors calibrated to ESPN behavior) |

### Reference Data
| File | Description |
|------|-------------|
| `Coach Results.csv` | 319 coaches' tournament records |
| `Seed Results.csv` | Historical win rates by seed |
| `Team Results.csv` | All-time program tournament performance |
| `Upset Seed Info.csv` | Every upset 2008–2025 by seed matchup |

## System Components

```
data_pipeline.py    → Loads 18 CSV files, standardizes team names (fuzzy matching),
                      builds historical game pairs and 2026 team stats
features.py         → Computes 28 differential features per matchup
model.py            → Trains XGBoost + LightGBM + Neural Net ensemble with calibration
upset_detector.py   → 9-flag rule-based upset detection for R64 games
pool_equity.py      → Equity scores: ML win probability ÷ public pick percentage
simulator.py        → 50,000 Monte Carlo tournament simulations
optimizer.py        → Bracket optimization with anti-chalk rules enforcement
main.py             → CLI interface with Rich tables and side-by-side bracket output
backend/app.py      → FastAPI backend (6 endpoints)
frontend/           → React 18 + Vite + TailwindCSS + Recharts + Framer Motion
```

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- Homebrew (macOS, for `libomp`)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/march-madness-predictor.git
cd march-madness-predictor

# Install Python dependencies
pip install -r requirements.txt

# macOS: install OpenMP runtime (required for XGBoost)
brew install libomp

# Train the ML models (runs ~3 minutes)
python model.py

# Run the CLI
python main.py --year 2026 --risk 0.7 --show-upsets --explain
```

### Frontend Setup

```bash
# Install frontend dependencies
cd frontend
npm install

# Start the backend (from project root)
cd ..
uvicorn backend.app:app --port 8001

# Start the frontend (from frontend/)
cd frontend
npm run dev -- --port 5180
```

Then open `http://localhost:5180` in your browser.

### CLI Options

```bash
python main.py \
  --year 2026 \
  --risk 0.7 \              # 0.0 = pure chalk, 1.0 = max contrarian
  --pool-size 1000000 \     # Assumed bracket pool size
  --show-upsets \            # Display upset alert panel
  --explain \                # Show model benchmark comparison
  --sims 50000 \            # Number of Monte Carlo simulations
  --output table             # table | json | csv
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/run-simulation` | POST | Run full simulation with `{risk, pool_size, year}` |
| `/api/bracket-data` | GET | 2026 bracket structure |
| `/api/upset-alerts` | GET | Upset detection results (32 games, 9 flags) |
| `/api/team-stats/{name}` | GET | Full stats for a specific team |
| `/api/model-benchmark` | GET | Model accuracy vs baselines |
| `/api/equity-data` | GET | Pool equity scores for all teams |

## How the Equity System Works

The core insight: in a large bracket pool, picking all favorites makes your bracket identical to millions of others. Even if you score well, you split the winnings with everyone else who picked chalk.

**Equity Score = ML Win Probability ÷ Public Pick Percentage**

- Duke: 19.2% sim championship rate ÷ 22% public pick = **0.87 equity** (overvalued by public)
- Illinois: 4.4% sim rate ÷ 1.5% public pick = **2.93 equity** (undervalued — contrarian value)
- Louisville: 2.9% sim rate ÷ 0.2% public pick = **14.5 equity** (massive contrarian value)

The optimizer blends ML probability with equity scores, weighted by round:
- **R64/R32**: 70-79% ML + 21-30% equity (upsets are rare, stick mostly with ML)
- **S16/E8**: 48-58% ML + 42-52% equity (equity starts driving contrarian picks)
- **F4/Championship**: 37-40% ML + 60-63% equity (maximum differentiation in the rounds that matter most for pool scoring)

## Anti-Chalk Rules

Five hardcoded rules enforced regardless of ML output:

1. At least one 1-seed must be eliminated before the Final Four
2. At least one 10+ seed must reach the Sweet 16
3. At least one 12-seed must beat a 5-seed (35% historical rate)
4. The largest KenPom rank vs seed discrepancy is flagged as an upset candidate
5. The #1 overall seed wins the championship less than 20% historically — don't over-index

## Tech Stack

**Backend**: Python, FastAPI, XGBoost, LightGBM, PyTorch, scikit-learn, SHAP, pandas, numpy

**Frontend**: React 18, Vite, TailwindCSS, Recharts, Framer Motion, Axios

**Data**: KenPom, Barttorvik, ESPN, TeamRankings, Sports-Reference (all pre-downloaded CSVs)
