# Live Bracket & Real Upset Alerts — Design Spec

## Overview

Add a "Live Bracket" tab to the March Madness predictor app that shows actual tournament results, tracks bracket progress round by round, and computes upset alerts for real upcoming matchups using the existing 11-condition upset detection system.

This is completely separate from the existing prediction/simulation system. The two systems share underlying data (team stats, Vegas lines, coach records) and logic (upset_detector.py) but serve different purposes: predictions are pre-tournament planning; live bracket is in-tournament tracking.

## Data Layer

### `data/2026/results_2026.json`

Single source of truth for actual tournament outcomes. Manually updated as games complete.

```json
{
  "year": 2026,
  "last_updated": "2026-03-20T20:00:00",
  "first_four": [
    {
      "region": "West",
      "seed": 11,
      "team_a": "Texas",
      "team_b": "NC State",
      "score_a": 79,
      "score_b": 71,
      "winner": "Texas",
      "status": "final"
    }
  ],
  "rounds": {
    "64": [
      {
        "region": "East",
        "seed_a": 1,
        "seed_b": 16,
        "team_a": "Duke",
        "team_b": "Siena",
        "score_a": 71,
        "score_b": 65,
        "winner": "Duke",
        "status": "final"
      }
    ],
    "32": [],
    "16": [],
    "8": [],
    "4": [],
    "2": []
  }
}
```

**Game statuses:**
- `final` — game completed, winner determined
- `in_progress` — game currently being played (score may be partial). Counts as "incomplete" for progress. Cannot be flagged as an upset.
- `upcoming` — matchup known but game not started

**Overtime:** Tracked via boolean `"overtime": true` field on game objects. Scores remain numeric (`score_a`, `score_b`).

**Matchup derivation:** R32 matchups are derived from R64 winners using standard bracket seeding order (1v16 winner plays 8v9 winner, etc.). The backend computes these — the JSON only stores R64 games and completed later-round games. Next-round matchups only appear in the API response when BOTH feeder games are `final`. If only one feeder game is complete, that slot shows as `null` / TBD in the response.

**First Four handling:** The person updating the JSON is responsible for listing the correct First Four winner as the team in the R64 entry (e.g., Howard beat UMBC → R64 shows Michigan vs Howard). The backend does not derive First Four → R64 mappings.

**Error handling:** If `results_2026.json` does not exist or is malformed, the endpoints return `{"error": "Tournament results not yet available", "rounds": {}}` with HTTP 200 (not 500) so the frontend can show a graceful empty state.

## Backend

### New endpoints (all under `/api/live/`)

#### `GET /api/live/bracket`

Returns the full live bracket state:

```json
{
  "last_updated": "2026-03-20T20:00:00",
  "current_round": 64,
  "current_round_label": "Round of 64",
  "progress": { "completed": 28, "total": 32, "pct": 87.5 },
  "first_four": [...],
  "rounds": {
    "64": [... all 32 games with status/scores ...],
    "32": [... derived matchups from R64 winners, status "upcoming" ...]
  },
  "upsets": [
    {
      "round": 64,
      "winner": "VCU",
      "winner_seed": 11,
      "loser": "North Carolina",
      "loser_seed": 6,
      "score": "82-78 OT",
      "region": "South"
    }
  ]
}
```

**Logic:**
1. Load `results_2026.json`
2. For each completed round, pair winners into next-round matchups using bracket seeding rules
3. Determine `current_round` (lowest round number with incomplete games)
4. Compute `progress` for the current round
5. Flag upsets (lower seed beat higher seed) from completed games
6. Return everything

**Bracket seeding rules** (standard NCAA bracket order per region):
- R64 game pairs: (1v16, 8v9) → R32; (5v12, 4v13) → R32; (6v11, 3v14) → R32; (7v10, 2v15) → R32
- Same pairing logic continues through subsequent rounds
- Final Four: East vs South, West vs Midwest (matching existing simulator.py)

#### `GET /api/live/upset-alerts`

Runs the existing `upset_detector.py` against actual upcoming matchups for the next round.

```json
{
  "round": 32,
  "round_label": "Round of 32",
  "total_games": 16,
  "high_alerts": 4,
  "alerts": [
    {
      "region": "South",
      "round": 32,
      "team_a": "VCU",
      "seed_a": 11,
      "team_b": "Illinois",
      "seed_b": 3,
      "upset_score": 5,
      "max_score": 11,
      "high_alert": true,
      "flags": ["kenpom_gap_close", "tempo_mismatch", "fav_luck_high", ...],
      "ml_upset_prob": 0.35,
      "vegas_spread": -4.5
    }
  ],
  "round_summary": {
    "total_flags": 28,
    "avg_score": 2.8,
    "high_alert_pct": 25.0
  }
}
```

**Logic:**
1. Call `/api/live/bracket` logic to get next-round matchups
2. Filter to matchups where both teams are known (both feeder games complete)
3. Build a `projected_picks` list from these real matchups (same format as optimizer picks: `{round, region, team_a, team_b, seed_a, seed_b}`)
4. Call `detect_upsets()` with `projected_picks=real_matchups` — the function's R32+ branch handles these identically to optimizer-projected picks
5. Filter the returned DataFrame to only the target round (ignore R64 results which are always generated from bracket structure)
6. Return alerts using the same response format as existing `/api/upset-alerts` endpoint (same field names: `favorite`, `underdog`, `higher_seed`, `lower_seed`, individual boolean flag columns) so the frontend can share transformation logic

**Integration with `detect_upsets()`:** The function accepts `projected_picks` (list of pick dicts) for R32+ matchups. We construct this list from actual R64 winners rather than optimizer projections. The function always generates R64 alerts from bracket structure — we simply filter those out and return only the target round's alerts. No modifications to `upset_detector.py` needed.

**Data loading:** This endpoint requires `_get_state()` for `current_teams_df`, `coach_results`, `seed_results`, `upset_seed_info`, and `vegas_lines`. It reuses the same lazy-loaded state as existing endpoints. The `/api/live/bracket` endpoint does NOT need `_get_state()` — it only reads `results_2026.json`.

## Frontend

### Tab System

Add a tab bar at the top of `App.jsx`, above the current Hero section:

```
[ Predictions ]  [ Live Bracket ]
```

- **Predictions tab:** Shows everything that exists now (Hero, simulation results, bracket, upsets, equity, benchmark)
- **Live Bracket tab:** Shows the new live tracking UI

Tabs are simple state toggle in App.jsx. No routing changes needed. The active tab determines which content renders below. The TabBar is defined inline in App.jsx (matching the existing NavBar pattern). When the Live Bracket tab is active, the prediction NavBar is hidden.

### Live Bracket Tab Components

#### 1. `LiveHeader.jsx` — Tournament Progress

Shows at the top of the live bracket tab:
- Current round name and progress bar ("Round of 64: 28/32 games complete")
- Last updated timestamp
- Count of upsets so far

Simple, informational. Styled consistently with existing Hero section.

#### 2. `LiveBracketView.jsx` — Visual Bracket

Read-only bracket visualization showing actual results. Built as its own component (not extending `InteractiveBracket.jsx` — that component is tightly coupled to override/equity logic). Uses a simpler table/card-based layout per region rather than full SVG bracket, keeping implementation scope manageable. Key features:

- **Completed games:** Show both teams with scores, winner highlighted in green
- **Upset results:** Winner highlighted in orange/red with an upset indicator
- **In-progress games:** Pulsing border or indicator, partial scores shown
- **Upcoming games (known matchups):** Both teams shown but muted/grayed
- **Unknown matchups:** Show "TBD" placeholder

No click-to-override functionality (that stays in the predictions tab). This is view-only.

#### 3. `LiveUpsetAlerts.jsx` — Next Round Upset Triggers

The core differentiator. Shows upset alerts for **real upcoming games**, not predictions.

Reuses the same card-based layout from existing `UpsetAlerts.jsx`:
- Each alert card shows the matchup, seeds, region
- Triggered conditions listed with explanations
- HIGH ALERT badge for score >= 3
- Round summary stats at top

Key difference from prediction alerts: these are based on who actually won, so matchups are real. For example, after R64 completes, if 11-seed VCU beat 6-seed UNC, the R32 alerts show VCU vs 3-seed Illinois with upset triggers computed on that real matchup.

#### 4. `LiveResultsTable.jsx` — Completed Games Table

Collapsible, round-by-round table of completed results:
- Columns: Region, Seeds, Teams, Score, Upset flag
- Grouped by round (R64, R32, etc.)
- Sortable by region or upset status
- Similar styling to existing `BracketView.jsx` stats table

### Component Hierarchy

```
App.jsx
├── TabBar (new)
├── [Predictions Tab] — existing content unchanged
│   ├── Hero
│   ├── NavBar
│   └── Results sections...
└── [Live Bracket Tab]
    ├── LiveHeader
    ├── LiveBracketView
    ├── LiveUpsetAlerts
    └── LiveResultsTable
```

### API Hook

New hook in `hooks/useApi.js`:

```js
function useLiveBracket() {
  // fetches /api/live/bracket on mount
}

function useLiveUpsetAlerts() {
  // fetches /api/live/upset-alerts on mount
}
```

Same pattern as existing `useSimulation()` and `useUpsetAlerts()` hooks.

## Data: Initial Results (as of March 20, 8pm ET)

The `results_2026.json` file will be populated with all known results:

### First Four (March 18)
| Region | Seed | Winner | Loser | Score |
|--------|------|--------|-------|-------|
| West | 11 | Texas | NC State | TBD |
| South | 16 | Prairie View A&M | Lehigh | 67-55 |
| Midwest | 16 | Howard | UMBC | TBD |
| Midwest | 11 | Miami (OH) | SMU | 89-79 |

### Round of 64 — Thursday March 19 (16 games, all final)
| Region | Seeds | Winner | Loser | Score | Upset? |
|--------|-------|--------|-------|-------|--------|
| East | 1v16 | Duke | Siena | 71-65 | No |
| East | 8v9 | TCU | Ohio State | 66-64 | Yes (9>8) |
| East | 6v11 | Louisville | South Florida | 83-79 | No |
| East | 3v14 | Michigan State | North Dakota State | 92-67 | No |
| South | 5v12 | Vanderbilt | McNeese | 78-68 | No |
| South | 4v13 | Nebraska | Troy | 76-47 | No |
| South | 6v11 | VCU | North Carolina | 82-78 OT | Yes |
| South | 3v14 | Illinois | Penn | 105-70 | No |
| South | 7v10 | Texas A&M | Saint Mary's | 63-50 | Yes |
| South | 2v15 | Houston | Idaho | 78-47 | No |
| West | 5v12 | High Point | Wisconsin | 83-82 | Yes |
| West | 4v13 | Arkansas | Hawai'i | 97-78 | No |
| West | 6v11 | Texas | BYU | 79-71 | Yes |
| West | 3v14 | Gonzaga | Kennesaw State | 73-64 | No |
| Midwest | 1v16 | Michigan | Howard | 101-80 | No |
| Midwest | 8v9 | Saint Louis | Georgia | 102-77 | Yes (9>8) |

### Round of 64 — Friday March 20 (completed by 8pm ET)
| Region | Seeds | Winner | Loser | Score | Upset? |
|--------|-------|--------|-------|-------|--------|
| West | 1v16 | Arizona | LIU | 92-58 | No |
| West | 8v9 | Utah State | Villanova | 86-76 | Yes (9>8) |
| Midwest | 2v15 | Iowa State | Tennessee State | 108-74 | No |
| Midwest | 3v14 | Virginia | Wright State | 82-73 | No |
| Midwest | 4v13 | Alabama | Hofstra | 90-70 | No |
| Midwest | 5v12 | Texas Tech | Akron | 91-71 | No |
| Midwest | 6v11 | Tennessee | Miami (OH) | 78-56 | No |
| Midwest | 7v10 | Kentucky | Santa Clara | 89-84 OT | No |

### Friday Evening (in progress / upcoming at 8pm ET)
| Region | Seeds | Teams | Status |
|--------|-------|-------|--------|
| South | 8v9 | Clemson vs Iowa | in_progress |
| East | 5v12 | St. John's vs Northern Iowa | in_progress |
| East | 7v10 | UCLA vs UCF | in_progress |
| West | 2v15 | Purdue vs Queens | in_progress |
| South | 1v16 | Florida vs Prairie View A&M | upcoming |
| East | 4v13 | Kansas vs Cal Baptist | upcoming |
| East | 2v15 | UConn vs Furman | upcoming |
| West | 7v10 | Miami (FL) vs Missouri | upcoming |

## What doesn't change

- All existing prediction/simulation endpoints and UI untouched
- `upset_detector.py` stays as-is; we call its existing functions with different inputs
- No new npm dependencies
- Same Tailwind styling, color scheme, component patterns
- `optimizer.py`, `simulator.py`, `model.py` unchanged

## File changes summary

### New files
- `data/2026/results_2026.json` — actual game results
- `frontend/src/components/LiveHeader.jsx`
- `frontend/src/components/LiveBracketView.jsx`
- `frontend/src/components/LiveUpsetAlerts.jsx`
- `frontend/src/components/LiveResultsTable.jsx`

### Modified files
- `backend/app.py` — add `/api/live/bracket` and `/api/live/upset-alerts` endpoints
- `frontend/src/App.jsx` — add tab system, render live bracket tab
- `frontend/src/hooks/useApi.js` — add `useLiveBracket()` and `useLiveUpsetAlerts()` hooks
