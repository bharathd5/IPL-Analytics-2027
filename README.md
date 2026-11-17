# SUPERR INTELLIGENCE: Pressure Performance Analytics System

SupeRR Selector Season 2, Round 1: *Identify the Most Reliable Players Under Pressure*.

The system measures how IPL and T20I batters and bowlers (2022–2026) perform in high-pressure situations compared with their own
usual level and with comparable players in the same state. It ranks the players who deliver **most consistently** when it matters.

## Quick start on Windows (no typing)

1. Install Python 3.11, 3.12 or 3.13 from python.org (tick **"Add python.exe to PATH"**).
2. Unzip this folder anywhere (not inside OneDrive), open it, and double-click:
   - `1_setup.bat`: installs the packages (once)
   - `2_run_dashboard.bat`: opens the dashboard in your browser
   - `3_rebuild_outputs_optional.bat`: re-runs the full analysis from `data/raw` (3–10 min). **Not needed** to use
     the dashboard, because the finished results are already in `outputs/`.

Same thing from a terminal inside this folder:
```
python -m pip install -r requirements.txt
python -m streamlit run app/Home.py
python -m src.pipeline        # optional rebuild
```

## Quick start

```bash
pip install -r requirements.txt
python -m src.preflight           # checks Python, packages, raw files and write access
python -m src.pipeline            # 3-10 min: rebuilds every output (use --quick for a 40-draw bootstrap)
streamlit run app/Home.py         # dashboard at http://localhost:8501
```

Raw CSVs live in `data/raw/`. The pipeline writes:

| Output | Content |
|---|---|
| `data/processed/master_ball_by_ball.parquet` / `.csv.gz` | **Single master file**: every delivery with match, competition, team and player context, match state, resource values, win probability, both pressure indices and components, expected values, contributions and pressure flags |
| `outputs/FINAL_TOP10_BATTERS.csv`, `FINAL_TOP10_BOWLERS.csv` | **Submission top-10 lists** |
| `outputs/ipl2027_status`, `rr_*` | IPL 2027 retention status, RR squad, phase coverage, needs, targets and the 6-slot plan |
| `outputs/batter_rankings*.{parquet,csv}`, `bowler_rankings*` | Full eligible leaderboards with every component, bootstrap interval, P(top 10), scenario ranks |
| `outputs/batter_innings.parquet`, `bowler_spells.parquet` | Per-match pressure innings and spells (consistency rules applied) |
| `outputs/batters_all.parquet`, `bowlers_all.parquet` | Career aggregates for **every** player (overall explorer) |
| `outputs/bat_zones`, `bowl_zones`, `wickets`, `matchups`, `over_sequence` | Feature tables (venue/zone strengths, wicket clusters, recovery after quick wickets, innings split, match-ups, in-match bounce-back) |
| `outputs/sensitivity*.parquet`, `validation_by_level.parquet`, `resource_table.parquet`, `summary.json` | Reliability and validation evidence |

## Deploy

Free public hosting on Streamlit Community Cloud: see [DEPLOY.md](DEPLOY.md).

## Presentation

`deliverables/SupeRR_Pressure_Reliability.pptx`: 32-slide deck (methodology, top 10s, evidence, reliability, RR 2027 auction).
Rebuild it with `node deliverables/build_deck.js` (needs `pptxgenjs`).

## Dashboard (SUPERR INTELLIGENCE)

A dark war-room layout: every chart sits in a numbered panel with its own header, filters live in one bar at the top of
each page, and the dashboard only reads pipeline outputs.

| Section | Pages |
|---|---|
| **IPL 2027 Auction** | **RR Auction War Room**: Rajasthan Royals' 19-player retained squad profiled under pressure, phase-by-phase gaps, need weights, a 6-slot plan (≤3 overseas, confirmed releases), bowling/batting shortlists, an impact simulator and a wildcard watch list · **Retention Tracker**: all ten franchises' purse and slots and every named player's status with pressure ratings |
| **War Room** | **Command Centre**: KPI strip, batter and bowler selection boards (rating, pressure vs normal, form arrow, P(top 10), reliability), clutch matrix, auto-generated intel feed, form movers, season pressure pulse · **Scenario Simulator**: enter a live match state, read batting and bowling pressure and win probability from matched historical deliveries, and get best-fit batters and bowlers for that exact context (optionally from one team's pool) · **Pressure XI Builder**: auto-picks an XI from any pool with a spinner quota, lets you swap players, and checks phase coverage and gaps · **Player Duel**: two candidates head-to-head on every pressure measure |
| Analytics | Overview · Pressure Analysis |
| Rankings | Batter Rankings · Bowler Rankings · Match-Up Analysis |
| Players | Pressure Player Explorer · Overall Player Explorer · Performance Lab |
| Model | Model Reliability · Methodology |

Tests: `python tests/test_pages.py` (every page renders) and `python tests/test_interactions.py` (main widgets).

## Code map

```
src/config.py      every threshold & weight (single source of truth)
src/data_prep.py   clean · de-duplicate · validate · merge
src/state.py       ball-by-ball match state before each delivery
src/models.py      empirical resource table + cross-fitted win probability
src/pressure.py    Batting & Bowling Pressure Index (0-100) + holdout validation
src/expected.py    pre-match form + expected runs / wickets → Pressure Contribution
src/metrics.py     innings/spell tables, consistency, baselines, shrinkage, rating
src/features.py    owner feature tables (zones, wickets, match-ups, over sequence)
src/pipeline.py    orchestration, eligibility, bootstrap, sensitivity, outputs
src/ipl2027_data.py retention-day status (17 Nov 2026) with sources and flagged conflicts
src/auction.py     RR squad needs, auction targets, 6-slot plan (python -m src.auction)
src/preflight.py   environment check with a fix for every problem
app/Home.py        Streamlit entry (st.navigation) · app/views/* pages · app/components/* UI toolkit + theme · app/assets/* logo
tests/             headless AppTest checks for every page and the main widgets
```

## Method in one paragraph

Before every ball, the system rebuilds the match state: balls left, wickets, target, RRR/CRR, momentum, collapse and partnership.
It values that state with a **DLS-style resource table learned from this data**. Two **separate pressure indices** follow, one for the
batting side and one for the bowling side (Paper 2), each built from resource-adjusted difficulty, rate, wickets, balls, stage, closeness and
partnership context. Each index is scaled by stakes (knockout, Super 4, DLS), dampened in dead games and converted to a 0–100 percentile.
Index ≥ 67 (top tercile) or any knockout ball counts as a pressure ball. Players are then rated on six shrunk, z-scored components:
**consistency on pressure balls** (35%: 20+ run impact innings, SR-156 / beat-the-situation qualifying innings, 1+ / 2+ wicket and dot-reliable
spells, stability), **contribution vs expected** (20%, Papers 3 & 5), **delta vs own baseline** (15%), **win probability added** (15%),
**team-relative standout** (10%) and **knockout impact** (5%). Eligibility: active in 2026, not a Pakistan player, minimum sample.
Reliability comes from a 300-draw bootstrap and 12 sensitivity scenarios. See the dashboard's *Methodology* page for full detail.
