# March Madness Bracket Algorithm — Claude Code Prompt (v2 — Full Data Spec)

---

## Paste everything below this line into Claude Code:

---

Build me a production-grade March Madness bracket prediction system in Python with a React frontend. This is a full ML + simulation + pool optimization engine with a visually stunning UI. Here is the complete spec:

---

## Goal

Predict winners for every game in the NCAA March Madness tournament using a hybrid ML + simulation approach. The system has two objectives:
1. Predict game outcomes as accurately as possible
2. Optimize bracket picks for **pool equity** — maximizing expected winnings relative to millions of other submitted brackets, not just raw game accuracy

Do NOT default to chalk. A bracket that picks all favorites is nearly worthless in a large pool. This system must intelligently identify where the public is wrong.

---

## HARD RULES — Non-negotiable, override everything else

- NO synthetic data. NO mock data. NO placeholder data. NO fake records. Every data point must come from the real files specified below. If a file is missing or a column is absent, STOP and tell me — do not substitute fake data.
- NO shortcuts. NO MVP approach. NO "simplified version for now". NO "you can expand this later". Build every feature in the spec completely the first time.
- NO placeholder functions. NO TODO comments left in code. Every function must be fully implemented before moving to the next module.
- If you hit a real blocker, STOP and tell me exactly what it is. Do not work around it silently.

---

## Data Architecture

All data files live in `/data/`. There are three categories:

### Category A — Historical Training Data (2008–2025)
Used to train the ML model. These files are pre-downloaded and ready to load. Do NOT re-scrape them.

### Category B — 2026 Current Season Data
Stats for the 68 teams in this year's bracket. Used for predictions. Some must be fetched live.

### Category C — Reference / Supporting Data
Coaches, seeds, historical upset patterns. Timeless — does not need updating for 2026.

---

## EXACT FILE SPECIFICATIONS

### Category A — Historical Training Data

**`/data/historical/KenPom_Barttorvik.csv`** (Amin dataset)
- **What it is:** The primary training file. Every NCAA tournament team 2008–2025 with KenPom + Barttorvik combined metrics.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `ROUND` (training target — which round eliminated), `KADJ EM`, `KADJ O`, `KADJ D`, `KADJ T`, `BARTHAG`, `WAB`, `EFG%`, `EFG%D`, `3PT%`, `3PT%D`, `TOV%`, `TOV%D`, `OREB%`, `DREB%`, `FTR`, `FTRD`, `EXP`, `AVG HGT`, `TALENT`, `ELITE SOS`, `2PT%`, `2PT%D`, `BLK%`, `AST%`, `FT%`
- **ROUND encoding:** 64=lost R64, 32=lost R32, 16=lost S16, 8=lost E8, 4=lost F4, 2=lost championship, 1=champion, 68=First Four loss
- **Years:** 2008–2025 (2020 excluded — tournament cancelled)

**`/data/historical/Barttorvik_Neutral.csv`** (Amin dataset)
- **What it is:** Barttorvik stats for tournament teams on neutral sites only — more predictive than full-season stats for tournament games since all tournament games are neutral site.
- **Key columns used:** Same Barttorvik columns as above but computed only from neutral-site games
- **Use for:** Feature engineering — prefer neutral-site stats over full-season stats when computing matchup features

**`/data/historical/Tournament_Matchups.csv`** (Amin dataset)
- **What it is:** Every individual tournament game 2008–2025 with actual scores.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `ROUND`, `CURRENT ROUND`, `SCORE`, `BY YEAR NO`
- **Use for:** Ground truth game outcomes for training. Join pairs of rows by `BY YEAR NO` to get Team A vs Team B with scores for each game.

**`/data/historical/Tournament_Locations.csv`** (Amin dataset)
- **What it is:** Travel distance and timezone data for every team in every tournament game 2008–2025.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `CURRENT ROUND`, `DISTANCE (MI)`, `TIME ZONES CROSSED`, `DIRECTION`
- **Use for:** Travel fatigue feature — distance traveled and time zones crossed per round

**`/data/historical/Resumes.csv`** (Amin dataset)
- **What it is:** Team resume metrics for every tournament team 2008–2025.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `ROUND`, `ELO`, `B POWER`, `Q1 W`, `Q2 W`, `Q1 PLUS Q2 W`, `Q3 Q4 L`, `BID TYPE`
- **Use for:** Bubble team flag (`BID TYPE` = Auto vs At-Large), Quad 1 win quality, ELO rating

**`/data/historical/TeamRankings.csv`** (Amin dataset)
- **What it is:** TeamRankings.com composite ratings for tournament teams 2008–2025. Contains the Luck metric.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `ROUND`, `LUCK RANK`, `LUCK RATING`, `LUCK V 1-25 WINS`, `LUCK V 1-25 LOSS`, `SOS RANK`, `SOS RATING`, `TR RATING`
- **Use for:** Luck-adjusted variance feature — teams with high luck scores overperformed and tend to regress; teams with low luck underperformed and may improve. This is the closest substitute for KenPom's proprietary Luck stat.

**`/data/historical/Shooting_Splits.csv`** (Amin dataset)
- **What it is:** Granular shot zone breakdowns for tournament teams 2010–2025.
- **Key columns used:** `YEAR`, `TEAM`, `DUNKS FG%`, `DUNKS SHARE`, `CLOSE TWOS FG%`, `CLOSE TWOS FG%D`, `THREES FG%`, `THREES SHARE`, `THREES FG%D`, `THREES D SHARE`
- **Use for:** Shot quality and 3-point style clash matchup features

**`/data/historical/KenPom_Preseason.csv`** (Amin dataset)
- **What it is:** Preseason KenPom rankings vs final rankings, showing how much each team improved or declined over the season.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `ROUND`, `PRESEASON KADJ EM`, `KADJ EM CHANGE`, `KADJ EM RANK CHANGE`
- **Use for:** Momentum feature — a team improving 20+ spots from preseason to tournament is peaking; a team declining is fading

**`/data/historical/Heat_Check_Tournament_Index.csv`** (Amin dataset)
- **What it is:** Pre-built pool value scores and bracket equity ranks 2013–2025.
- **Key columns used:** `YEAR`, `TEAM`, `SEED`, `ROUND`, `POWER`, `PATH`, `POOL VALUE`, `POOL S-RANK`
- **Use for:** Validate and cross-check pool equity module output

**`/data/historical/DEV___March_Madness.csv`** (Pilafas dataset)
- **What it is:** Master joined KenPom file — every Division I team 2002–2025 with all KenPom metrics combined into one 165-column table.
- **Key columns used:** `Season`, `Full Team Name`, `AdjEM`, `ORtg`, `DRtg`, `AdjT`, `Luck` (if present), `SOS NetRtg`, `eFGPct`, `TOPct`, `ORPct`, `FTRate`, `Experience`, `AvgHeight`, `Pre-Tournament.AdjEM`, `Seed`, `Region`, `Tournament Winner?`, `Tournament Championship?`, `Final Four?`
- **Use for:** Supplement KenPom_Barttorvik.csv with any columns that file is missing, especially pre-tournament snapshot metrics and the `Pre-Tournament.AdjEM` field which shows KenPom's ratings as they stood before the tournament started (critical — use this, not end-of-season ratings, for historical training)
- **Important:** When building training features, always use `Pre-Tournament.AdjEM` and `Pre-Tournament` columns for historical games, not the final season values, since you wouldn't have known post-tournament data at pick time

### Category B — 2026 Current Season Data

**`/data/2026/kenpom_2026.csv`** (manually scraped from kenpom.com public page)
- **What it is:** Current 2026 KenPom ratings for all 363 Division I teams, scraped from the free public main page.
- **Expected columns:** `Rank`, `Team`, `Conf`, `W-L`, `NetRtg`, `ORtg`, `DRtg`, `AdjT`, `Luck`, `SOS_NetRtg`, `SOS_ORtg`, `SOS_DRtg`, `NCSOS_NetRtg`
- **How to get if missing:** Run this scraper — the main kenpom.com page is publicly accessible without login:
  ```python
  import requests
  from bs4 import BeautifulSoup
  import pandas as pd
  
  url = "https://kenpom.com/"
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
  response = requests.get(url, headers=headers)
  soup = BeautifulSoup(response.text, 'html.parser')
  table = soup.find('table', {'id': 'ratings-table'})
  rows = []
  for tr in table.find_all('tr'):
      cells = [td.get_text(strip=True) for td in tr.find_all(['td','th'])]
      if cells:
          rows.append(cells)
  df = pd.DataFrame(rows)
  df.to_csv('/data/2026/kenpom_2026.csv', index=False)
  ```
- **If scraping fails:** The file may already exist from a manual export. Check first before scraping.

**`/data/2026/barttorvik_2026.csv`** (fetched directly from barttorvik.com)
- **What it is:** Full Barttorvik T-Rank stats for all teams in the 2026 season.
- **How to get:** Fetch directly — Bart Torvik provides free CSV downloads in this format:
  ```python
  import pandas as pd
  df = pd.read_csv("https://barttorvik.com/2026_team_results.csv", header=0)
  df.to_csv('/data/2026/barttorvik_2026.csv', index=False)
  ```
- **Key columns:** `team`, `barthag`, `adj_o`, `adj_d`, `adj_t`, `wab`, `efg_o`, `efg_d`, `tor`, `tord`, `orp`, `drp`, `ftr`, `ftrd`, `three_pt_pct`, `three_pt_pct_d`, `two_pt_pct`, `two_pt_pct_d`, `blk_pct`, `ast_pct`, `experience`, `talent`
- **If URL fails:** Try `https://barttorvik.com/trank.php?year=2026&csv=1` as alternate URL

**`/data/2026/bracket_2026.json`** (pre-built — already exists)
- **What it is:** The official 2026 NCAA tournament bracket with all 68 teams, seeds, and regions.
- **This file is already created** — do not regenerate it. Load it directly.
- **Structure:** JSON with East, West, South, Midwest regions, each containing seed/team pairs in bracket order
- **First Four notes:** West 11-seed, South 16-seed, Midwest 16-seed, Midwest 11-seed are TBD — the system should handle these gracefully by using the higher-seeded team as the default until First Four results are known

**`/data/2026/public_picks_2026.csv`** (scraped from ESPN Bracket Challenge)
- **What it is:** 2026 ESPN Bracket Challenge public pick percentages — what % of submitted brackets picked each team to win each round.
- **Expected columns:** `YEAR`, `TEAM`, `R64`, `R32`, `S16`, `E8`, `F4`, `FINALS`
- **How to get:** Scrape from ESPN:
  ```python
  # ESPN's who picked whom page - scrape this URL
  # https://fantasy.espn.com/tournament-challenge-bracket/2026/en/whopickedwhom
  # Use requests + BeautifulSoup to parse the pick percentage table
  # This data is only available during tournament week — grab it immediately
  ```
- **If unavailable:** Use flat priors based on seed — 1-seeds get 85% R64, 2-seeds 75%, etc. Flag clearly that real public pick data is missing and equity calculations are estimated.
- **Critical:** This is the only file that must be grabbed THIS WEEK. It disappears after the tournament ends.

### Category C — Reference / Supporting Data (Timeless)

**`/data/reference/Coach_Results.csv`** (Amin dataset)
- **What it is:** Every coach's historical NCAA tournament record with advanced performance metrics.
- **Key columns:** `COACH`, `PAKE` (performance above/below seed expectation), `PASE`, `GAMES`, `W`, `WIN%`, `R64`, `R32`, `S16`, `E8`, `F4`, `CHAMP`, `F4%`, `CHAMP%`
- **Use for:** Coach tournament win rate feature and coach experience index

**`/data/reference/Seed_Results.csv`** (Amin dataset)
- **What it is:** Historical win rates for every seed matchup (1v16, 2v15, etc.) across all tournaments.
- **Key columns:** `SEED`, `PAKE`, `WIN%`, `R64`, `R32`, `S16`, `E8`, `F4`, `CHAMP%`
- **Use for:** Historical seed matchup upset rate feature (e.g. 5v12 upsets happen 35% historically)

**`/data/reference/Team_Results.csv`** (Amin dataset)
- **What it is:** All-time historical tournament performance per program.
- **Key columns:** `TEAM`, `PAKE`, `PASE`, `GAMES`, `W`, `WIN%`, `F4%`, `CHAMP%`
- **Use for:** Program pedigree feature — teams with strong historical tournament track records

**`/data/reference/Conference_Results.csv`** (Amin dataset)
- **What it is:** Historical tournament performance and strength per conference.
- **Key columns:** `CONF`, `PAKE`, `PASE`, `WIN%`, `CHAMP%`
- **Use for:** Conference strength signal for seeding accuracy assessment

**`/data/reference/Upset_Seed_Info.csv`** (Amin dataset)
- **What it is:** Every upset in tournament history 2008–2025 by seed matchup and round.
- **Key columns:** `YEAR`, `CURRENT ROUND`, `SEED WON`, `SEED LOST`, `SEED DIFF`
- **Use for:** Computing exact historical upset rates by seed pairing for the upset detector

**`/data/reference/Teamsheet_Ranks.csv`** (Amin dataset)
- **What it is:** Multi-metric team rankings including BPI, NET, KPI, SOR, Quad wins 2019–2025.
- **Key columns:** `YEAR`, `TEAM`, `SEED`, `BPI`, `NET`, `KPI`, `SOR`, `Q1 W`, `Q1 L`, `Q2 W`, `Q2 L`
- **Use for:** BPI feature and selection committee metric context

---

## Architecture

Build these 8 components in order:

---

### 1. Data Pipeline (`data_pipeline.py`)

Load and clean all files listed above. For each file:
- Load from the exact path specified
- Standardize team name column to `team_name` using fuzzy matching across sources (use `fuzzywuzzy` with a threshold of 85)
- Standardize year column to `season` (integer)
- Log how many rows loaded and how many teams matched successfully

**2026 live data fetching:**
- On first run, check if `/data/2026/barttorvik_2026.csv` exists. If not, fetch from `barttorvik.com/2026_team_results.csv` and save locally.
- On first run, check if `/data/2026/kenpom_2026.csv` exists. If not, run the scraper above and save locally.
- After fetching, never re-fetch in the same session — always load from local file.

**Pre-Tournament vs End-of-Season handling:**
- For all historical training data, use `Pre-Tournament.AdjEM` from `DEV___March_Madness.csv` when available, NOT the final season AdjEM. This prevents data leakage — you must simulate only knowing what was known before the tournament.
- For 2026 predictions, use current season stats (they are effectively pre-tournament since the tournament just started).

**Output:** One master `historical_games_df` DataFrame where each row is one tournament game (2008–2025) with all features for both teams, and one `current_teams_df` DataFrame with 2026 stats for all 68 bracket teams.

---

### 2. Feature Engineering (`features.py`)

For every matchup (Team A vs Team B), generate these features from the loaded data:

**Efficiency features (from KenPom_Barttorvik + kenpom_2026):**
- AdjEM differential (A - B) using `KADJ EM` / `Pre-Tournament.AdjEM`
- BARTHAG differential (from Barttorvik)
- Offensive efficiency differential (`KADJ O`)
- Defensive efficiency differential (`KADJ D`)
- BPI differential (from Teamsheet_Ranks where available)

**Stylistic matchup features (from KenPom_Barttorvik + Shooting_Splits):**
- Tempo mismatch score: `|KADJ T_A - KADJ T_B|` — large mismatches historically favor the slower team
- 3-point rate clash: `3PTR_A` (how often A shoots threes) vs `3PT%D_B` (how well B defends threes)
- Turnover battle: `TOV%_A` vs `TOV%D_B` — teams that force turnovers vs teams that turn it over
- Rebounding battle: `OREB%_A` vs `DREB%_B` and vice versa
- Free throw disparity: `FTR_A` vs `FTRD_B`
- Shot quality clash: `DUNKS SHARE_A` vs `CLOSE TWOS FG%D_B` from Shooting_Splits

**Variance and experience features (from KenPom_Barttorvik + DEV March Madness):**
- Experience differential: `EXP_A - EXP_B`
- Height differential: `AVG HGT_A - AVG HGT_B`
- Talent differential: `TALENT_A - TALENT_B`

**Luck and momentum features (from TeamRankings + KenPom_Preseason):**
- Luck differential: `LUCK RATING_A - LUCK RATING_B` — teams with high luck tend to regress
- Luck vs top opponents: `LUCK V 1-25 WINS_A` — specifically lucky in big games
- Preseason momentum: `KADJ EM CHANGE_A - KADJ EM CHANGE_B` from KenPom_Preseason — teams improving heading into tournament
- Preseason rank delta: how many spots each team moved from preseason to tournament

**Historical and context features (from Resumes + Coach_Results + Seed_Results):**
- Seed matchup historical upset rate from `Seed_Results.csv` for this exact seed pairing
- KenPom rank vs seed discrepancy: `(SEED_A * 4) - KADJ EM RANK_A` — large positive = underseeded
- ELO differential from `Resumes.csv`
- Quad 1 wins differential: `Q1 W_A - Q1 W_B`
- Bubble flag: `BID TYPE` = "Auto" from `Resumes.csv` — auto-bid teams historically underperform
- Coach PAKE differential from `Coach_Results.csv`
- Coach tournament games experience differential
- Program historical CHAMP% from `Team_Results.csv`

**Travel and location features (from Tournament_Locations):**
- Distance traveled in miles: `DISTANCE (MI)` for each team
- Time zones crossed: `TIME ZONES CROSSED`
- Travel direction (East/West advantage)
- Relative travel disadvantage: Team A distance minus Team B distance

**Market and public features (from public_picks_2026 — 2026 only):**
- Public pick percentage for Team A at each round
- Used downstream by pool equity module — stored as feature but not used in ML win prediction directly

---

### 3. ML Model (`model.py`)

**Training data:** Load `historical_games_df` from data pipeline. Each row = one tournament game. Target: did Team A win? (binary, 1 = win, 0 = loss). Years 2008–2024 for training, 2025 held out as final validation set.

**Model ensemble (3 models):**
- XGBoost classifier — primary model
- LightGBM classifier — secondary
- Neural Network (PyTorch, 4 hidden layers: 256→128→64→32, ReLU, dropout 0.3)

**Ensemble weights:** 45% XGBoost + 35% LightGBM + 20% Neural Net

**Calibration layer (do not skip):**
- Apply Platt scaling via `sklearn.calibration.CalibratedClassifierCV` to each model after training
- Validate calibration with reliability diagrams saved to `/outputs/calibration_plots/`

**Validation:**
- 5-fold cross validation on 2008–2024 data
- Hold out 2025 completely for final out-of-sample test
- Report: accuracy, log loss, Brier score, AUC for each model and ensemble
- Benchmark against: (1) always pick higher seed, (2) Vegas closing line accuracy, (3) KenPom AdjEM only model

**Feature importance:**
- Output SHAP values for top 20 features → save to `/outputs/shap_importance.png`

**Save:** All three models + calibrators → `/models/` directory via joblib

---

### 4. Upset Detection Module (`upset_detector.py`)

Standalone rule-based module using the actual data files. For each first-round game:

Flag HIGH UPSET ALERT if 3+ of these conditions are true (all computed from real data):
- Lower seed's `KADJ EM RANK` is within 15 spots of higher seed's rank (from kenpom_2026 + KenPom_Barttorvik)
- `|KADJ T_A - KADJ T_B|` > 8 possessions (tempo mismatch from barttorvik_2026)
- Higher seed's preseason rank change is negative (fading team, from KenPom_Preseason)
- Lower seed coach `PAKE` > league average (from Coach_Results)
- Lower seed `LUCK RATING` is negative (underperformed, due for regression up, from TeamRankings)
- Lower seed's `3PT%D` rank is top 30 AND higher seed `3PTR` rank is top 30 (style clash)
- Seed matchup historical upset rate > 30% (from Seed_Results)
- Lower seed `ELO` within 50 points of higher seed (from Resumes)
- Higher seed has `Q3 Q4 L` > 3 (soft schedule losses, from Resumes)

Output: DataFrame of all first-round games sorted by upset score with triggered flags

---

### 5. Pool Equity Module (`pool_equity.py`)

Load `public_picks_2026.csv` for 2026 public pick percentages.

**Equity formula:**
```
Equity Score = (True Win Probability from ML model) / (Public Pick Percentage)
```

If public pick data unavailable, use seed-based priors and flag clearly.

**Apply equity weighting by round:**
- R64, R32: 85% win probability + 15% equity
- S16, E8: 55% win probability + 45% equity
- F4, Championship: 40% win probability + 60% equity

Output: equity-adjusted score per team per round

---

### 6. Monte Carlo Bracket Simulator (`simulator.py`)

- Load `bracket_2026.json`
- Run 50,000 simulations using calibrated ML win probabilities
- Blend equity-adjusted probabilities for rounds 3–6 based on `--risk` parameter
- Track round win %, championship win %, score distribution

---

### 7. Bracket Optimizer (`optimizer.py`)

- R1–R2: use ML win probability directly
- R3–R4: apply equity scores, target teams with equity > 1.8
- F4+: equity-weighted, minimum 12% true win probability for champion pick
- Enforce anti-chalk rules (listed below)
- Output both safe bracket (risk=0.1) and equity bracket (risk=0.6) side by side

---

### 8. Backend API (`backend/app.py`)

Build a FastAPI backend that exposes these endpoints:

```
POST /api/run-simulation
  Body: { risk: float, pool_size: int, year: int }
  Returns: Full bracket prediction with all picks, probabilities, equity scores

GET /api/bracket-data
  Returns: 2026 bracket structure from bracket_2026.json

GET /api/upset-alerts
  Returns: Upset alert DataFrame from upset_detector

GET /api/team-stats/{team_name}
  Returns: All 2026 stats for a specific team from data pipeline

GET /api/model-benchmark
  Returns: Model accuracy vs baselines
```

Run with: `uvicorn backend.app:app --reload --port 8000`

---

### 9. React Frontend (`frontend/`)

Build a production-grade, visually stunning React application. This is not a generic dashboard — it should feel like a premium sports analytics product that someone would pay for.

**Design direction:** Dark theme. Deep navy/charcoal base with electric gold/amber accents. Monospaced data typography paired with a sharp editorial display font. Feels like a Bloomberg terminal crossed with a modern sports betting interface. Every number should feel important. Animations should feel data-driven and precise, not decorative.

**Pages / Sections:**

**1. Hero / Landing**
- Animated bracket bracket graphic in the background (SVG, animated paths)
- "2026 MARCH MADNESS AI BRACKET" as the title in bold editorial type
- Risk level slider (0.0 to 1.0) and pool size input prominently displayed
- "RUN SIMULATION" button — triggers 50k simulation run via API call with loading animation

**2. Simulation Loading State**
- Animated counter showing simulations running (0 → 50,000)
- Live updating probability bars for the four #1 seeds as simulation runs
- Do not show fake progress — tie this to actual API response

**3. Interactive Bracket View**
- Full visual tournament bracket with all 64 teams laid out in the classic 4-region format
- Each game shows: Team A vs Team B, ML win probability %, equity score
- Color coding: green = model favorite, amber = upset pick, red = HIGH UPSET ALERT
- Click any team to see their full stat breakdown in a side panel
- Winning path highlighted for the predicted champion

**4. Upset Alerts Panel**
- Card-based layout showing each HIGH UPSET ALERT
- For each alert: matchup, which conditions triggered (shown as tags), upset probability, equity score
- Sort by upset confidence score

**5. Final Four + Champion Display**
- Large centered display showing the four Final Four teams with their regions
- Each team: sim win rate %, public pick %, equity score, BOLD PICK badge if contrarian
- Champion prediction displayed prominently with confidence gauge

**6. Pool Equity Dashboard**
- Scatter plot: x-axis = true win probability, y-axis = public pick %, color = equity score
- Teams in the top-left quadrant (high probability, low public) are your high-equity picks
- Hover tooltips show full team data

**7. Model Benchmark Panel**
- Bar chart comparing: This Model vs Chalk vs Vegas vs KenPom-only
- Show accuracy, log loss, Brier score, simulated pool win rate

**Tech stack:**
- React 18 + Vite
- Recharts for data visualizations
- Framer Motion for animations
- TailwindCSS for styling
- Axios for API calls

**Run with:** `npm run dev` (proxies API calls to port 8000)

---

## CLI Interface (`main.py`)

Keep the CLI as an alternative to the UI:

```bash
python main.py \
  --year 2026 \
  --risk 0.5 \
  --bracket-input data/2026/bracket_2026.json \
  --output table \
  --pool-size 1000000 \
  --show-upsets \
  --explain
```

---

## Anti-Chalk Rules (Hardcoded — enforce regardless of ML output)

1. At least one 1-seed must be eliminated before the Final Four (happened 37/40 tournaments)
2. At least one team seeded 10+ must reach the Sweet 16 (every tournament since 2008)
3. At least one 12-seed must beat a 5-seed (35% historical rate — verify against Seed_Results.csv)
4. The team with the largest KenPom rank vs seed discrepancy in the 2026 field must be flagged as an upset candidate
5. Championship picks from the #1 overall seed win less than 20% of the time — do not over-index

If the optimizer violates any of these, force a correction and print a warning message.

---

## Project Structure

```
march-madness/
├── data/
│   ├── historical/          ← Category A files (2008–2025 training data)
│   ├── 2026/                ← Category B files (current season)
│   ├── reference/           ← Category C files (timeless reference)
│   └── README.md            ← Exact instructions for every file
├── models/                  ← Saved ML models and calibrators
├── outputs/                 ← Plots, reports, bracket outputs
├── backend/
│   └── app.py               ← FastAPI backend
├── frontend/
│   ├── src/
│   └── package.json
├── data_pipeline.py
├── features.py
├── model.py
├── upset_detector.py
├── pool_equity.py
├── simulator.py
├── optimizer.py
├── main.py
├── requirements.txt
└── README.md
```

---

## Technical Requirements

- Python 3.11+
- Backend: `fastapi`, `uvicorn`, `pandas`, `numpy`, `scikit-learn`, `xgboost`, `lightgbm`, `torch`, `shap`, `requests`, `beautifulsoup4`, `fuzzywuzzy`, `joblib`, `rich`, `scipy`
- Frontend: React 18, Vite, Recharts, Framer Motion, TailwindCSS, Axios
- `requirements.txt` with pinned versions
- Full `README.md` with setup and run instructions

---

## Benchmark

Report accuracy, log loss, and simulated pool win rate for:
1. This system
2. Always-pick-higher-seed (chalk)
3. Vegas closing line accuracy
4. KenPom AdjEM-only model

The system must beat all three baselines on pool win rate simulation.
