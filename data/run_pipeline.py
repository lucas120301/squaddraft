#!/usr/bin/env python3
"""Orchestrate scrape -> build -> Supabase import."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent


def run(cmd: list[str], extra_env: dict | None = None) -> None:
    print(f"\n>> {' '.join(cmd)}")
    env = os.environ.copy()
    env.setdefault("SOCCERDATA_DIR", str(DATA_DIR / ".soccerdata"))
    if extra_env:
        env.update(extra_env)
    subprocess.run(cmd, cwd=DATA_DIR, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="PL Era Draft data pipeline")
    parser.add_argument("--scrape", action="store_true", help="Scrape FBref data")
    parser.add_argument("--build", action="store_true", help="Build CSVs from raw data")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Import CSVs to Supabase")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--import-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build preview only, no CSV write/import")
    parser.add_argument("--seasons", type=str, default="", help="Limit scrape seasons, e.g. 2021,2022,2023")
    parser.add_argument("--truncate-dataset", action="store_true", help="Clear dataset tables before import")
    args = parser.parse_args()

    do_scrape = args.scrape or args.scrape_only or (not args.build_only and not args.import_only and not args.scrape and not args.build and not args.do_import)
    do_build = args.build or args.build_only or (not args.scrape_only and not args.import_only and not args.scrape and not args.build and not args.do_import)
    do_import = args.do_import or args.import_only or (not args.scrape_only and not args.build_only and not args.scrape and not args.build and not args.do_import)

    py = sys.executable

    if do_scrape:
        cmd = [py, "scrape_fbref.py"]
        if args.seasons:
            cmd += ["--seasons", args.seasons]
        run(cmd)

    if do_build:
        cmd = [py, "build_dataset.py"]
        if args.dry_run:
            cmd.append("--dry-run")
        run(cmd)

    if do_import and not args.dry_run:
        run([py, "migrate.py"])
        cmd = [py, "import_to_supabase.py"]
        if args.truncate_dataset:
            cmd.append("--truncate-dataset")
        run(cmd)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
