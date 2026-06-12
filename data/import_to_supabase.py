#!/usr/bin/env python3
"""Import CSV dataset into Supabase Postgres."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from lib.db_url import resolve_database_url
from lib.migrate import run_migrations

load_dotenv()

DATA_DIR = Path(__file__).parent
BATCH_SIZE = 500

DATASET_TABLES = ["players", "player_eras", "position_fits", "team_era_pools"]


def load_formations() -> list[dict]:
    path = DATA_DIR / "formations.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def chunked(rows: list[dict], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def prepare_rows(table: str, rows: list[dict]) -> list[dict]:
    if table == "position_fits":
        for row in rows:
            row["id"] = f"{row['player_id']}_{row['position'].lower()}"
    if table == "players":
        for row in rows:
            sec = row.get("secondary_positions", "")
            row["secondary_positions"] = (
                [p.strip() for p in sec.split("|") if p.strip()] if sec else []
            )
            for field in ("base_rating", "attack", "midfield", "defence", "goalkeeper", "consistency"):
                if field in row and row[field] != "":
                    row[field] = int(float(row[field]))
    if table == "player_eras":
        for row in rows:
            row["rating_modifier"] = int(row.get("rating_modifier") or 0)
            row["include"] = row.get("include", "true").lower() != "false"
            sec = row.get("secondary_positions", "")
            row["secondary_positions"] = (
                [p.strip() for p in sec.split("|") if p.strip()] if sec else []
            )
    if table == "team_era_pools":
        for row in rows:
            row["spin_tier"] = int(row.get("spin_tier") or 3)
            row["min_eligible_players"] = int(row.get("min_eligible_players") or 5)
            row["is_active"] = True
    return rows


def truncate_dataset(client) -> None:
    print("Truncating dataset tables (rooms unaffected)...")
    for table in reversed(DATASET_TABLES):
        try:
            client.table(table).delete().neq("id", "").execute()
        except Exception:
            # Fallback: delete all rows via filter on known column
            try:
                if table == "players":
                    client.table(table).delete().neq("slug", "").execute()
                else:
                    client.table(table).delete().gte("id", "").execute()
            except Exception as exc:
                print(f"  Warning: could not truncate {table}: {exc}")


def upsert_table(client, table: str, rows: list[dict], conflict: str = "id") -> int:
    rows = prepare_rows(table, rows)
    total = 0
    for batch in chunked(rows, BATCH_SIZE):
        client.table(table).upsert(batch, on_conflict=conflict).execute()
        total += len(batch)
        print(f"  {table}: {total}/{len(rows)}")
    return total


def table_exists(client, table: str) -> bool:
    try:
        client.table(table).select("id").limit(1).execute()
        return True
    except Exception as exc:
        if "PGRST205" in str(exc) or "Could not find the table" in str(exc):
            return False
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truncate-dataset", action="store_true")
    parser.add_argument("--migrate", action="store_true", help="Run pending SQL migrations first")
    parser.add_argument("--apply-schema", action="store_true", help=argparse.SUPPRESS)  # alias
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SECRET_KEY in data/.env")
        return

    try:
        from supabase import create_client
    except ImportError:
        print("pip install supabase python-dotenv")
        return

    client = create_client(url, key)

    run_migrate = args.migrate or args.apply_schema or not table_exists(client, "clubs")
    if run_migrate:
        if resolve_database_url():
            try:
                run_migrations()
            except RuntimeError as exc:
                print(exc)
                return
            except Exception as exc:
                print(f"Migration failed: {exc}")
                return
        elif not table_exists(client, "clubs"):
            print("Tables not found in Supabase.")
            print("Run migrations first (needs database password, not the REST secret key):")
            print("  SUPABASE_DB_PASSWORD=...   # Settings → Database")
            print("  python migrate.py")
            print("  python import_to_supabase.py --truncate-dataset")
            return

    if args.truncate_dataset:
        truncate_dataset(client)

    summary = {}

    formations = load_formations()
    if formations:
        print(f"Upserting {len(formations)} rows into formations...")
        summary["formations"] = upsert_table(client, "formations", formations, "id")

    for table, filename, conflict in [
        ("clubs", "clubs.csv", "id"),
        ("players", "players.csv", "id"),
        ("player_eras", "player_eras.csv", "id"),
        ("position_fits", "position_fits.csv", "id"),
        ("team_era_pools", "team_era_pools.csv", "id"),
    ]:
        rows = read_csv(filename)
        if not rows:
            print(f"Skipping {table} — no rows in {filename}")
            continue
        print(f"Upserting {len(rows)} rows into {table}...")
        summary[table] = upsert_table(client, table, rows, conflict)

    print("\nImport complete:")
    for table, count in summary.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
