# PL Era Draft — Data Pipeline

Scrapes Premier League player stats from [FBref](https://fbref.com) via [soccerdata](https://soccerdata.readthedocs.io/) (requires Chrome for Cloudflare), derives internal ratings, and loads Supabase.

## Setup

```bash
cd data
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Required in `data/.env`:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` + `SUPABASE_SECRET_KEY` | REST API — upsert CSV rows |
| `DATABASE_URL` | Direct Postgres — run SQL migrations |

## Database setup

```bash
python migrate.py
python import_to_supabase.py --truncate-dataset
```

Migrations live in `supabase/migrations/`. The import script loads `formations.json` plus the CSV dataset.

## Run full pipeline

```bash
export SOCCERDATA_DIR="$(pwd)/.soccerdata"
python run_pipeline.py --scrape --build --import
```

Or step by step:

```bash
python scrape_fbref.py
python build_dataset.py
python migrate.py
python import_to_supabase.py --truncate-dataset
```

## Eligibility

- 20 clubs from `clubs.csv`
- 7 five-year eras (1992-1995 … 2020-2025)
- Players with **450+ minutes** in a club+era window
- Ratings derived from stats percentiles (not FIFA/SoFIFA)

## Outputs (generated locally — not committed to git)

| File | Description |
|---|---|
| `formations.json` | Formation presets (seeded to Supabase) — **committed** |
| `players.csv` | Unique players with base_rating + area scores |
| `player_eras.csv` | Club+era rows with rating_modifier |
| `position_fits.csv` | Per-position fit scores |
| `team_era_pools.csv` | Spin pools (≥5 eligible players) |
| `reports/dataset_summary.md` | Review artifact |

Source files kept in git: `clubs.csv`, `config/`, pipeline scripts.

## Notes

- Scraping uses soccerdata + headless Chrome; set `SOCCERDATA_DIR` inside `data/` to avoid permission issues.
- Re-scraping uses per-season JSON cache in `raw/fbref/season_*.json`.
- Backend reads from Supabase only — no local CSV seeding at startup.
