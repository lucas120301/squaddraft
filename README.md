# PL Era Draft

Premier League era draft party game — formation-first snake draft with hidden season simulation.

## What's in the repo

| Included | Not in git (generated locally) |
|---|---|
| App code (`backend/`, `frontend/`) | `data/players.csv`, `player_eras.csv`, `position_fits.csv`, `team_era_pools.csv` |
| SQL migrations (`supabase/migrations/`) | `data/raw/`, `data/reports/`, scraper caches |
| Source config (`data/clubs.csv`, `data/config/`, `data/formations.json`) | `.env`, `.venv`, `node_modules`, `.next` |
| Test fixtures (`backend/tests/fixtures/`) | |

Run `python build_dataset.py` after scraping to regenerate the dataset CSVs, then `import_to_supabase.py` to load Supabase.

## Quick start

### 1. Database (one-time)

```bash
cd data
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # SUPABASE_URL, SUPABASE_SECRET_KEY, DATABASE_URL
python migrate.py
python import_to_supabase.py --truncate-dataset
```

See [data/README.md](data/README.md) for the scrape/rebuild pipeline.

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Set DATABASE_URL to the same Supabase Postgres URI as data/.env
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000

## Stack

- **Frontend:** Next.js, TypeScript, Tailwind, Zustand
- **Backend:** FastAPI, Python 3.11+, SQLAlchemy + asyncpg
- **Database:** Supabase Postgres (`supabase/migrations/` + CSV import)

## Cloud deploy (AWS)

Terraform + GitHub Actions scaffold lives in [`infra/`](infra/DEPLOY.md):

- **Terraform** — ECR, ECS Fargate, ALB, SSM secrets
- **GitHub Actions** — CI tests + OIDC deploy (no long-lived AWS keys)
- **Database** — keep Supabase; no RDS required for v1

See [infra/DEPLOY.md](infra/DEPLOY.md) for setup steps.
