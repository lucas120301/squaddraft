#!/usr/bin/env python3
"""Run pending Supabase SQL migrations."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from lib.migrate import run_migrations

load_dotenv()


def main() -> None:
    try:
        run_migrations()
    except RuntimeError as exc:
        print(exc)
        print("\nMigrations need direct Postgres access (not the REST secret key).")
        print("Add to data/.env:")
        print("  SUPABASE_DB_PASSWORD=...   (Settings → Database)")
        sys.exit(1)
    except Exception as exc:
        print(f"Migration failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
