# PROJECT PLAN — March Madness Bracket Prediction System

---

## Pre-Build Notes: Data Inventory vs. Spec

Before building, here's what I found when auditing `/data/`:

### File Location Differences
- **All data files are in `/data/` (flat directory)** — the spec references `/data/historical/`, `/data/2026/`, `/data/reference/` subdirectories but those don't exist. I will organize files into those subdirectories as Phase 0.
- **File names use spaces**, not underscores (e.g., `KenPom Barttorvik.csv`). The data pipeline will handle this.
- **`bracket_2026.json`** is at the project root, not in `/data/2026/`. Will move it.

### Files Present (Confirmed with correct columns)
| Spec Name | Actual File | Status |
|-----------|------------|--------|
| `KenPom_Barttorvik.csv` | `KenPom Barttorvik.csv` | ✅ All columns match |
| `Barttorvik_Neutral.csv` | `Barttorvik Neutral.csv` | ✅ |
| `Tournament_Matchups.csv` | `Tournament Matchups.csv` | ✅ |
| `Tournament_Locations.csv` | `Tournament Locations.csv` | ✅ |
| `Resumes.csv` | `Resumes.csv` | ✅ |
| `TeamRankings.csv` | `TeamRankings.csv` | ✅ LUCK columns confirmed |
| `Shooting_Splits.csv` | `Shooting Splits.csv` | ✅ |
| `KenPom_Preseason.csv` | `KenPom Preseason.csv` | ✅ |
| `Heat_Check_Tournament_Index.csv` | `Heat Check Tournament Index.csv` | ✅ |
| `DEV___March_Madness.csv` | `DEV _ March Madness.csv` | ✅ 165 columns, Pre-Tournament.AdjEM confirmed |
| `barttorvik_2026.csv` | `2026_team_results.csv` | ✅ Full Barttorvik 2026 data |
| `bracket_2026.json` | `bracket_2026.json` (root) | ✅ All 4 regions + First Four |
| `Coach_Results.csv` | `Coach Results.csv` | ✅ PAKE columns confirmed |
| `Seed_Results.csv` | `Seed Results.csv` | ✅ |
| `Team_Results.csv` | `Team Results.csv` | ✅ |
| `Conference_Results.csv` | `Conference Results.csv` | ✅ |
| `Upset_Seed_Info.csv` | `Upset Seed Info.csv` | ✅ |
| `Teamsheet_Ranks.csv` | `Teamsheet Ranks.csv` | ✅ BPI column confirmed |
| `Public_Picks.csv` | `Public Picks.csv` | ⚠️ 2025 only (63 teams) |

### Files Missing
| Spec Name | Status | Action Required |
|-----------|--------|----------------|
| `kenpom_2026.csv` | ❌ Not present | Must scrape from kenpom.com public page or user provides |
| `public_picks_2026.csv` | ❌ Not present | Must scrape ESPN or use seed-based priors |

### Action Items Before Coding
1. Organize `/data/` into subdirectories (`historical/`, `2026/`, `reference/`)
2. Move `bracket_2026.json` into `/data/2026/`
3. Attempt to fetch `kenpom_2026.csv` — if scraping fails, STOP and ask user
4. Attempt to fetch `public_picks_2026.csv` from ESPN — if unavailable, use seed-based priors with clear flag

---

## Phase 0: Project Setup & Data Organization
**Files:** `requirements.txt`, directory structure
**Tasks:**
1. Create directory structure: `models/`, `outputs/`, `outputs/calibration_plots/`, `backend/`, `data/historical/`, `data/2026/`, `data/reference/`
2. Move data files into correct subdirectories
3. Create `requirements.txt` with pinned dependencies
4. Verify all data files load correctly

**Dependencies:** None — this is the starting point

---

## Phase 1: Data Pipeline (`data_pipeline.py`)
**File:** `data_pipeline.py`
**Dependencies:** Phase 0 complete

### Tasks:
1. **Load all Category A historical files** (9 files)
   - `KenPom Barttorvik.csv` → primary training features
   - `Barttorvik Neutral.csv` → neutral-site stats for feature engineering
   - `Tournament Matchups.csv` → game-level outcomes (ground truth)
   - `Tournament Locations.csv` → travel features
   - `Resumes.csv` → ELO, Q1 wins, bid type
   - `TeamRankings.csv` → luck metrics
   - `Shooting Splits.csv` → shot zone breakdowns
   - `KenPom Preseason.csv` → momentum features
   - `DEV _ March Madness.csv` → Pre-Tournament.AdjEM and supplemental columns

2. **Load all Category C reference files** (6 files)
   - `Coach Results.csv`, `Seed Results.csv`, `Team Results.csv`
   - `Conference Results.csv`, `Upset Seed Info.csv`, `Teamsheet Ranks.csv`

3. **Load Category B 2026 files** (3 files)
   - `2026_team_results.csv` (Barttorvik 2026)
   - `kenpom_2026.csv` (fetch if missing)
   - `bracket_2026.json`

4. **Team name standardization**
   - Build master team name mapping using `fuzzywuzzy` (threshold 85)
   - Cross-source matching: KenPom names ↔ Barttorvik names ↔ bracket names ↔ DEV March Madness names
   - Standardize to `team_name` column across all DataFrames
   - Log match rates per source pair

5. **Build `historical_games_df`**
   - Start with `Tournament Matchups.csv` — pair rows by `BY YEAR NO` to get Team A vs Team B per game
   - Join team stats from all historical sources by (YEAR, team_name)
   - Use `Pre-Tournament.AdjEM` from `DEV _ March Madness.csv` instead of end-of-season AdjEM
   - Target variable: did Team A win? (binary, derived from SCORE comparison)
   - Expected shape: ~1,100 rows × 80+ feature columns

6. **Build `current_teams_df`**
   - Merge Barttorvik 2026 + KenPom 2026 for all 68 bracket teams
   - Add reference data (coach results, seed results, team pedigree)
   - Handle First Four TBD teams (default to higher-seeded/first-listed team)

7. **Validation**
   - Print row counts, year ranges, null percentages per column
   - Verify all 68 bracket teams match to stats

**Output:** Two DataFrames saved to memory — `historical_games_df` and `current_teams_df`

---

## Phase 2: Feature Engineering (`features.py`)
**File:** `features.py`
**Dependencies:** Phase 1 complete (uses `data_pipeline.py` outputs)

### Tasks:
1. **Efficiency differential features** (5 features)
   - AdjEM differential (Pre-Tournament.AdjEM for historical, current for 2026)
   - BARTHAG differential
   - Offensive efficiency differential (KADJ O)
   - Defensive efficiency differential (KADJ D)
   - BPI differential (from Teamsheet Ranks, where available)

2. **Stylistic matchup features** (6 features)
   - Tempo mismatch: `|KADJ T_A - KADJ T_B|`
   - 3-point rate clash: `3PTR_A` vs `3PT%D_B`
   - Turnover battle: `TOV%_A` vs `TOV%D_B`
   - Rebounding battle: `OREB%_A` vs `DREB%_B`
   - Free throw disparity: `FTR_A` vs `FTRD_B`
   - Shot quality clash from Shooting Splits

3. **Variance and experience features** (3 features)
   - Experience differential
   - Height differential
   - Talent differential

4. **Luck and momentum features** (4 features)
   - Luck rating differential (from TeamRankings)
   - Luck vs top opponents differential
   - Preseason momentum (KADJ EM CHANGE differential)
   - Preseason rank delta

5. **Historical and context features** (9 features)
   - Seed matchup historical upset rate
   - KenPom rank vs seed discrepancy
   - ELO differential
   - Quad 1 wins differential
   - Bubble flag (auto-bid indicator)
   - Coach PAKE differential
   - Coach tournament experience differential
   - Program historical CHAMP%
   - Conference strength (PAKE from Conference Results)

6. **Travel and location features** (4 features, historical only)
   - Distance traveled differential
   - Time zones crossed differential
   - Travel direction encoding
   - Relative travel disadvantage

7. **Public pick features** (stored for pool equity, not ML training)
   - Public pick % per team per round (2026 only)

8. **Feature pipeline function**
   - `build_matchup_features(team_a_stats, team_b_stats, round_num, year)` → feature vector
   - Apply to all historical games → training matrix
   - Apply to 2026 bracket matchups → prediction matrix

**Output:** Feature matrix for training (~1,100 rows × ~31 features) and feature generation function for 2026 predictions

---

## Phase 3: ML Model (`model.py`)
**File:** `model.py`
**Dependencies:** Phase 2 complete

### Tasks:
1. **Data split**
   - Training: 2008–2024 (all tournament games)
   - Holdout: 2025 (full tournament — final validation)

2. **Train 3 models**
   - XGBoost classifier with hyperparameter tuning
   - LightGBM classifier with hyperparameter tuning
   - PyTorch neural network (4 hidden layers: 256→128→64→32, ReLU, dropout 0.3)

3. **Calibration**
   - Apply Platt scaling via `CalibratedClassifierCV` to each model
   - Generate reliability diagrams → save to `/outputs/calibration_plots/`

4. **Ensemble**
   - Weighted average: 45% XGBoost + 35% LightGBM + 20% Neural Net
   - Output calibrated win probabilities per matchup

5. **Validation & benchmarking**
   - 5-fold CV on 2008–2024: accuracy, log loss, Brier score, AUC
   - 2025 holdout test: same metrics
   - Benchmark against: always-higher-seed, Vegas line proxy, KenPom AdjEM-only

6. **Feature importance**
   - SHAP values for top 20 features → `/outputs/shap_importance.png`

7. **Save models**
   - All 3 models + calibrators + ensemble config → `/models/` via joblib

**Output:** Trained ensemble model, benchmark report, calibration plots, SHAP plot

---

## Phase 4: Upset Detection (`upset_detector.py`)
**File:** `upset_detector.py`
**Dependencies:** Phase 1 (data), Phase 3 (ML probabilities)

### Tasks:
1. **Implement 9-flag rule-based upset detector** for each first-round game:
   - KADJ EM RANK within 15 spots
   - Tempo mismatch > 8 possessions
   - Higher seed fading (negative preseason rank change)
   - Lower seed coach PAKE above average
   - Lower seed luck rating negative (due for regression up)
   - 3-point style clash (lower seed defends 3s well, higher seed shoots many 3s)
   - Historical upset rate > 30% for this seed pairing
   - ELO within 50 points
   - Higher seed has > 3 Q3/Q4 losses

2. **Scoring**: Count triggered flags → upset score. Flag HIGH UPSET ALERT if 3+ triggers.

3. **Output**: DataFrame sorted by upset score with all triggered flags as columns

**Output:** Upset alerts DataFrame for all R64 games

---

## Phase 5: Pool Equity (`pool_equity.py`)
**File:** `pool_equity.py`
**Dependencies:** Phase 3 (ML probabilities), public pick data

### Tasks:
1. **Load public pick data**
   - If `public_picks_2026.csv` exists: use real percentages
   - If not: compute seed-based priors from historical public pick patterns and flag clearly

2. **Equity calculation**
   - `equity_score = true_win_prob / public_pick_pct` per team per round

3. **Round-weighted blending**
   - R64/R32: 85% win prob + 15% equity
   - S16/E8: 55% win prob + 45% equity
   - F4/Championship: 40% win prob + 60% equity

4. **Output**: Equity-adjusted score per team per round

**Output:** Equity scores DataFrame

---

## Phase 6: Monte Carlo Simulator (`simulator.py`)
**File:** `simulator.py`
**Dependencies:** Phase 3 (model), Phase 5 (equity scores), bracket_2026.json

### Tasks:
1. **Load bracket structure** from `bracket_2026.json`
2. **Simulate 50,000 full tournaments**
   - Use calibrated ML win probabilities for each matchup
   - Blend equity-adjusted probabilities for rounds 3–6 based on `--risk` parameter
   - Each simulation: sample winners game-by-game using probabilities as coin flips
3. **Track statistics**
   - Per-team: round-by-round advancement %, championship win %, average score
   - Overall: Final Four frequency distribution, champion frequency distribution
4. **Handle First Four** — simulate those games first, then feed winners into main bracket

**Output:** Simulation results with 50k tournament outcomes

---

## Phase 7: Bracket Optimizer (`optimizer.py`)
**File:** `optimizer.py`
**Dependencies:** Phase 3 (model), Phase 5 (equity), Phase 6 (simulations)

### Tasks:
1. **Pick selection logic by round**
   - R1–R2: ML win probability directly
   - R3–R4: equity scores, target equity > 1.8
   - F4+: equity-weighted, minimum 12% true win prob for champion
2. **Anti-chalk rule enforcement**
   - At least one 1-seed eliminated before F4
   - At least one 10+ seed in Sweet 16
   - At least one 12-seed beats a 5-seed
   - Flag largest KenPom rank vs seed discrepancy
   - Don't over-index #1 overall seed for championship
3. **Generate two brackets**
   - Safe bracket (risk=0.1)
   - Equity bracket (risk=0.6)
4. **Output formatting** — full bracket picks with probabilities and equity scores

**Output:** Two complete bracket predictions (safe + equity)

---

## Phase 8: CLI Interface (`main.py`)
**File:** `main.py`
**Dependencies:** All previous phases (1–7)

### Tasks:
1. **CLI argument parsing** via argparse
   - `--year`, `--risk`, `--bracket-input`, `--output`, `--pool-size`, `--show-upsets`, `--explain`
2. **Orchestration** — run full pipeline:
   - Load data → engineer features → load trained model → run upset detection → compute equity → simulate → optimize → output
3. **Rich console output**
   - Formatted bracket table
   - Upset alerts table
   - Model benchmark summary
   - Champion prediction with confidence
4. **Export** — save bracket to `/outputs/bracket_2026.json` and `/outputs/bracket_2026.csv`

**Output:** Complete CLI tool that runs the full system

---

## Phase 9: Backend API (`backend/app.py`)
**File:** `backend/app.py`
**Dependencies:** All previous phases

### Tasks:
1. **FastAPI app** with 5 endpoints:
   - `POST /api/run-simulation` — run full simulation with risk/pool_size params
   - `GET /api/bracket-data` — return bracket structure
   - `GET /api/upset-alerts` — return upset detector output
   - `GET /api/team-stats/{team_name}` — return all stats for a team
   - `GET /api/model-benchmark` — return accuracy comparisons
2. **Model loading** — load pre-trained models from `/models/` at startup
3. **CORS configuration** for frontend dev server

---

## Phase 10: React Frontend (`frontend/`)
**Files:** `frontend/` directory
**Dependencies:** Phase 9 (backend running)

### Tasks:
1. **Project setup**: React 18 + Vite + TailwindCSS + Recharts + Framer Motion + Axios
2. **Hero / Landing page** — risk slider, pool size input, RUN SIMULATION button
3. **Simulation loading state** — animated counter, live probability bars
4. **Interactive bracket view** — full 64-team bracket, color-coded picks, click-to-inspect
5. **Upset alerts panel** — card layout with triggered flags
6. **Final Four + Champion display** — large centered display with confidence gauges
7. **Pool equity dashboard** — scatter plot (true prob vs public pick %)
8. **Model benchmark panel** — bar chart comparisons
9. **Dark theme styling** — navy/charcoal base, electric gold/amber accents

---

## Module Dependency Graph

```
Phase 0 (Setup)
    │
    ▼
Phase 1 (data_pipeline.py)
    │
    ▼
Phase 2 (features.py)
    │
    ▼
Phase 3 (model.py)
    │
    ├──────────────┬──────────────┐
    ▼              ▼              │
Phase 4         Phase 5          │
(upset_detector) (pool_equity)   │
    │              │              │
    │              ▼              │
    │         Phase 6             │
    │         (simulator.py)      │
    │              │              │
    │              ▼              │
    │         Phase 7             │
    │         (optimizer.py)      │
    │              │              │
    ▼              ▼              │
    └──────► Phase 8 ◄───────────┘
             (main.py)
                │
                ▼
          Phase 9
          (backend/app.py)
                │
                ▼
          Phase 10
          (frontend/)
```

---

## Blockers to Resolve Before Phase 1

### BLOCKER 1: `kenpom_2026.csv` Missing
The 2026 KenPom ratings file does not exist in `/data/`. Options:
- **Option A:** I attempt to scrape from kenpom.com public page (spec provides scraper code)
- **Option B:** You provide the file manually
- **Recommendation:** Let me try Option A first. If it fails (e.g., Cloudflare blocking), I'll stop and ask for the file.

### BLOCKER 2: `public_picks_2026.csv` Missing
Only 2025 public picks exist. 2026 ESPN bracket challenge data may not be available yet (tournament just started March 15).
- **Option A:** I attempt to scrape ESPN's Who Picked Whom page
- **Option B:** Use seed-based priors derived from the 2025 public picks data + historical seed patterns, clearly flagged as estimated
- **Recommendation:** Try Option A. Fall back to Option B with clear warning in all outputs.

### NOT a blocker: Data directory organization
Files exist but are flat in `/data/`. I'll organize them into subdirectories in Phase 0 — no data is missing, just needs reorganization.

---

## Estimated File Count
| Phase | Files Created |
|-------|--------------|
| 0 | `requirements.txt`, directory structure |
| 1 | `data_pipeline.py` |
| 2 | `features.py` |
| 3 | `model.py` |
| 4 | `upset_detector.py` |
| 5 | `pool_equity.py` |
| 6 | `simulator.py` |
| 7 | `optimizer.py` |
| 8 | `main.py` |
| 9 | `backend/app.py` |
| 10 | `frontend/` (~15 files) |
| **Total** | **~25 files** |

---

**Ready for your approval. Want me to proceed with Phase 0, or do you want changes to the plan?**
