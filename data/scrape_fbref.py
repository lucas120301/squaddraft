#!/usr/bin/env python3
"""Scrape Premier League player season stats from FBref via soccerdata."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd

from lib.era import PL_SEASONS, season_code_to_end_year

DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw" / "fbref"
STAT_TYPES = ["standard", "shooting", "misc", "keeper"]


def _setup_soccerdata() -> None:
    os.environ.setdefault("SOCCERDATA_DIR", str(DATA_DIR / ".soccerdata"))


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join(str(c) for c in col if str(c) not in ("", "nan")).strip("_") for col in df.columns
        ]
    return df.reset_index()


def _normalize_df(df: pd.DataFrame, stat_type: str) -> pd.DataFrame:
    df = _flatten_columns(df.copy())
    rename = {}
    for col in df.columns:
        lc = col.lower()
        if lc in ("player", "team", "season", "league", "pos", "nation", "age", "born"):
            rename[col] = lc
        if lc.endswith("_min") or lc == "playing_time_min" or (lc == "min" and "minutes" not in rename.values()):
            rename[col] = "minutes"
    df = df.rename(columns=rename)
    if "season" in df.columns:
        df["season"] = df["season"].apply(season_code_to_end_year)
    df["stat_type"] = stat_type
    return df


def scrape_season(season: int, fbref, delay: float = 2.0) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for stat_type in STAT_TYPES:
        try:
            df = fbref.read_player_season_stats(stat_type=stat_type)
            if df is not None and not df.empty:
                frames[stat_type] = _normalize_df(df, stat_type)
                print(f"  season {season} {stat_type}: {len(frames[stat_type])} rows")
        except Exception as exc:
            print(f"  season {season} {stat_type}: {exc}")
        time.sleep(delay)
    return frames


def scrape_all(seasons: list[int] | None = None, delay: float = 2.0) -> Path:
    _setup_soccerdata()
    import soccerdata as sd

    seasons = seasons or PL_SEASONS
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "player_seasons.parquet"
    all_rows: list[pd.DataFrame] = []

    for i, season in enumerate(seasons):
        cache_file = RAW_DIR / f"season_{season}.json"
        if cache_file.exists():
            print(f"[{i+1}/{len(seasons)}] season {season} — cache hit")
            payload = json.loads(cache_file.read_text())
            for stat_type, records in payload.items():
                if records:
                    df = pd.DataFrame(records)
                    all_rows.append(df)
            continue

        print(f"[{i+1}/{len(seasons)}] season {season} — fetching...")
        fbref = sd.FBref(leagues="ENG-Premier League", seasons=season)
        frames = scrape_season(season, fbref, delay=delay)
        season_payload: dict[str, list] = {}
        for stat_type, df in frames.items():
            season_payload[stat_type] = df.to_dict(orient="records")
            all_rows.append(df)
        if season_payload:
            cache_file.write_text(json.dumps(season_payload, default=str))
        time.sleep(delay)

    if not all_rows:
        raise RuntimeError("No data scraped")

    combined = pd.concat(all_rows, ignore_index=True)
    combined.to_parquet(out_path, index=False)
    print(f"Saved {len(combined)} rows to {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape FBref PL player stats via soccerdata")
    parser.add_argument("--seasons", type=str, default="", help="Comma-separated end-years")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between stat-type requests")
    args = parser.parse_args()
    seasons = [int(s) for s in args.seasons.split(",") if s.strip()] if args.seasons else None
    scrape_all(seasons=seasons, delay=args.delay)


if __name__ == "__main__":
    main()
