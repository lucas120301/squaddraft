#!/usr/bin/env python3
"""Transform scraped FBref data into game CSVs with derived ratings."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from lib.era import ERAS, MIN_ERA_MINUTES, season_code_to_end_year, season_to_era
from lib.positions import (
    POSITIONS,
    default_fits,
    is_valid_player_name,
    parse_fbref_positions,
    position_weights,
    resolve_era_position,
    slugify,
)

DATA_DIR = Path(__file__).parent
RAW_PATH = DATA_DIR / "raw" / "fbref" / "player_seasons.parquet"
REPORT_DIR = DATA_DIR / "reports"

CLUB_MAP: dict[str, str] = json.loads((DATA_DIR / "config" / "club_map.json").read_text())
SPIN_CONFIG: dict = json.loads((DATA_DIR / "config" / "spin_config.json").read_text())
SPIN_CLUBS: set[str] = set(SPIN_CONFIG.get("clubs") or [])
SPIN_EXCLUDE_ERAS: set[str] = set(SPIN_CONFIG.get("exclude_eras") or [])


def spin_pool_tier(top_rating: float, avg_rating: float) -> int:
    """1 = elite spin, 5 = too weak for the wheel."""
    if top_rating >= 90 and avg_rating >= 77:
        return 1
    if top_rating >= 87 and avg_rating >= 75.5:
        return 2
    if top_rating >= 84 and avg_rating >= 74.5:
        return 3
    if top_rating >= 80 and avg_rating >= 73:
        return 4
    return 5


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    cols_lower = {str(c).lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
        for k, v in cols_lower.items():
            if cand.lower() in k.replace(" ", "_"):
                return v
    return None


def load_and_merge() -> pd.DataFrame:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Run scrape_fbref.py first. Missing {RAW_PATH}")

    raw = pd.read_parquet(RAW_PATH)
    # Keep standard as base; merge others
    std = raw[raw["stat_type"] == "standard"].copy() if "stat_type" in raw.columns else raw.copy()
    if std.empty:
        raise RuntimeError("No standard stats in raw data")

    player_col = _find_col(std, "player")
    team_col = _find_col(std, "team")
    season_col = _find_col(std, "season")
    pos_col = _find_col(std, "pos")
    min_col = _find_col(std, "minutes", "playing_time_min", "min")
    gls_col = _find_col(std, "gls", "performance_gls", "goals", "performance_gls")
    ast_col = _find_col(std, "ast", "performance_ast", "assists", "performance_ast")

    if not all([player_col, team_col, season_col]):
        raise RuntimeError(f"Missing required columns. Found: {list(std.columns)}")

    std = std.rename(
        columns={
            player_col: "player",
            team_col: "team",
            season_col: "season",
            **({pos_col: "pos"} if pos_col else {}),
            **({min_col: "minutes"} if min_col else {}),
            **({gls_col: "gls"} if gls_col else {}),
            **({ast_col: "ast"} if ast_col else {}),
        }
    )
    std["minutes"] = _num(std.get("minutes", pd.Series(0, index=std.index)))
    std["gls"] = _num(std.get("gls", pd.Series(0, index=std.index)))
    std["ast"] = _num(std.get("ast", pd.Series(0, index=std.index)))
    if "pos" not in std.columns:
        std["pos"] = "MF"

    keys = ["player", "team", "season"]
    merged = std[keys + ["pos", "minutes", "gls", "ast"]].copy()

    for stat_type in ("shooting", "misc", "keeper"):
        part = raw[raw["stat_type"] == stat_type].copy() if "stat_type" in raw.columns else pd.DataFrame()
        if part.empty:
            continue
        pc = _find_col(part, "player")
        tc = _find_col(part, "team")
        sc = _find_col(part, "season")
        if not all([pc, tc, sc]):
            continue
        part = part.rename(columns={pc: "player", tc: "team", sc: "season"})
        extra_cols = [c for c in part.columns if c not in keys + ["stat_type"]]
        part = part[keys + extra_cols]
        merged = merged.merge(part, on=keys, how="left", suffixes=("", f"_{stat_type}"))

    def _norm_season(val):
        if pd.isna(val):
            return None
        s = str(val)
        if len(s) == 4 and not s.startswith("19") and not s.startswith("20"):
            return season_code_to_end_year(s)
        try:
            v = int(float(s))
            if 1990 <= v <= 2030:
                return v
        except ValueError:
            pass
        return season_code_to_end_year(s)

    merged["season"] = merged["season"].apply(_norm_season)
    merged["club_id"] = merged["team"].map(CLUB_MAP)
    merged["era"] = merged["season"].apply(lambda s: season_to_era(int(s)) if pd.notna(s) else None)
    merged = merged[merged["club_id"].notna() & merged["era"].notna()].copy()
    return merged


def aggregate_era_rows(df: pd.DataFrame) -> pd.DataFrame:
    npxg_col = _find_col(df, "npxg", "expected_npxg", "npxg_shooting")
    tkl_col = _find_col(df, "tkl", "performance_tkl", "misc_tkl")
    int_col = _find_col(df, "int", "performance_int", "misc_int")
    blocks_col = _find_col(df, "blocks", "performance_blocks", "misc_blocks")
    prgc_col = _find_col(df, "prgc", "progression_prgc", "carries_prgc")
    save_pct_col = _find_col(df, "save%", "keepersave%", "keeper_save%")
    cs_col = _find_col(df, "cs", "performance_cs", "keeper_cs")
    ga_col = _find_col(df, "ga", "performance_ga", "keeper_ga")

    for col_name, var in [
        ("npxg", npxg_col),
        ("tkl", tkl_col),
        ("int", int_col),
        ("blocks", blocks_col),
        ("prgc", prgc_col),
        ("save_pct", save_pct_col),
        ("cs", cs_col),
        ("ga", ga_col),
    ]:
        df[col_name] = _num(df[var]) if var else 0.0

    df["nineties"] = df["minutes"] / 90.0
    df["ga_per90"] = df.apply(lambda r: r["ga"] / r["nineties"] if r["nineties"] > 0 else 0, axis=1)
    df["def_actions_per90"] = df.apply(
        lambda r: (r["tkl"] + r["int"] + r["blocks"]) / r["nineties"] if r["nineties"] > 0 else 0, axis=1
    )
    df["g_plus_a_per90"] = df.apply(
        lambda r: (r["gls"] + r["ast"]) / r["nineties"] if r["nineties"] > 0 else 0, axis=1
    )
    df["npxg_per90"] = df.apply(lambda r: r["npxg"] / r["nineties"] if r["nineties"] > 0 else 0, axis=1)
    df["ast_per90"] = df.apply(lambda r: r["ast"] / r["nineties"] if r["nineties"] > 0 else 0, axis=1)

    def _dominant_pos(sub: pd.DataFrame) -> str:
        votes: Counter[str] = Counter()
        for _, row in sub.iterrows():
            votes[str(row["pos"])] += int(row["minutes"])
        return votes.most_common(1)[0][0] if votes else "MF"

    grouped = []
    for keys, sub in df.groupby(["player", "club_id", "era"]):
        grouped.append(
            {
                "player": keys[0],
                "club_id": keys[1],
                "era": keys[2],
                "minutes": int(sub["minutes"].sum()),
                "gls": sub["gls"].sum(),
                "ast": sub["ast"].sum(),
                "npxg": sub["npxg"].sum(),
                "tkl": sub["tkl"].sum(),
                "int": sub["int"].sum(),
                "blocks": sub["blocks"].sum(),
                "prgc": sub["prgc"].sum(),
                "ga": sub["ga"].sum(),
                "cs": sub["cs"].sum(),
                "save_pct": sub["save_pct"].mean(),
                "pos": _dominant_pos(sub),
                "seasons_played": sub["season"].nunique(),
            }
        )
    agg = pd.DataFrame(grouped)
    agg["nineties"] = agg["minutes"] / 90.0
    agg["g_plus_a_per90"] = (agg["gls"] + agg["ast"]) / agg["nineties"].replace(0, 1)
    agg["npxg_per90"] = agg["npxg"] / agg["nineties"].replace(0, 1)
    agg["ast_per90"] = agg["ast"] / agg["nineties"].replace(0, 1)
    agg["def_actions_per90"] = (agg["tkl"] + agg["int"] + agg["blocks"]) / agg["nineties"].replace(0, 1)
    agg["ga_per90"] = agg["ga"] / agg["nineties"].replace(0, 1)
    agg = agg[agg["minutes"] >= MIN_ERA_MINUTES].copy()
    return agg


def percentile_score(series: pd.Series) -> pd.Series:
    if len(series) == 0:
        return series
    ranks = series.rank(pct=True, method="average")
    return (50 + ranks * 49).clip(1, 99).round().astype(int)


def compute_ratings(agg: pd.DataFrame) -> pd.DataFrame:
    records = []
    for era in ERAS:
        era_df = agg[agg["era"] == era].copy()
        if era_df.empty:
            continue

        era_df["attack_raw"] = era_df["g_plus_a_per90"] * 0.6 + era_df["npxg_per90"] * 0.4
        era_df["midfield_raw"] = era_df["ast_per90"] * 0.6 + (era_df["prgc"] / era_df["nineties"].replace(0, 1)) * 0.4
        era_df["defence_raw"] = era_df["def_actions_per90"]
        era_df["gk_raw"] = era_df["save_pct"] * 0.5 + era_df["cs"] / era_df["seasons_played"].replace(0, 1) * 10 - era_df["ga_per90"] * 2

        era_df["attack"] = percentile_score(era_df["attack_raw"])
        era_df["midfield"] = percentile_score(era_df["midfield_raw"])
        era_df["defence"] = percentile_score(era_df["defence_raw"])
        era_df["goalkeeper"] = percentile_score(era_df["gk_raw"].clip(lower=0))

        for _, row in era_df.iterrows():
            if not is_valid_player_name(str(row["player"]), minutes=int(row["minutes"])):
                continue
            primary, secondary = resolve_era_position(
                str(row["pos"]),
                player=str(row["player"]),
                gls_per90=float(row["gls"] / max(row["nineties"], 0.01)),
                ast_per90=float(row["ast_per90"]),
                ga_per90=float(row["g_plus_a_per90"]),
                minutes=int(row["minutes"]),
            )
            aw, mw, dw, gw = position_weights(primary)
            era_score = (
                row["attack"] * aw + row["midfield"] * mw + row["defence"] * dw + row["goalkeeper"] * gw
            )
            records.append(
                {
                    "player": row["player"],
                    "club_id": row["club_id"],
                    "era": era,
                    "primary_position": primary,
                    "secondary_positions": secondary,
                    "minutes": int(row["minutes"]),
                    "seasons_played": int(row["seasons_played"]),
                    "attack": int(row["attack"]),
                    "midfield": int(row["midfield"]),
                    "defence": int(row["defence"]),
                    "goalkeeper": int(row["goalkeeper"]),
                    "era_score": float(era_score),
                }
            )

    return pd.DataFrame(records)


def build_players_tables(ratings: pd.DataFrame) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    players_map: dict[str, dict] = {}
    player_eras: list[dict] = []
    position_fits_rows: list[dict] = []

    peak_scores: dict[str, float] = {}
    for player_name, grp in ratings.groupby("player"):
        peak_scores[player_name] = grp["era_score"].max()

    # Global primary = position from era with most minutes (not first row seen).
    player_primary: dict[str, tuple[str, list[str]]] = {}
    for player_name, grp in ratings.groupby("player"):
        top = grp.sort_values("minutes", ascending=False).iloc[0]
        player_primary[player_name] = (top["primary_position"], top["secondary_positions"])

    for _, row in ratings.iterrows():
        pid = slugify(row["player"])
        if pid not in players_map:
            primary, secondary = player_primary[row["player"]]
            peak = peak_scores[row["player"]]
            best = ratings[ratings["player"] == row["player"]].sort_values("era_score", ascending=False).iloc[0]
            base_rating = int(max(1, min(99, round(peak))))
            consistency = min(99, 70 + int(row["seasons_played"]) * 3)
            players_map[pid] = {
                "id": pid,
                "name": row["player"],
                "slug": pid,
                "primary_position": primary,
                "secondary_positions": "|".join(secondary),
                "base_rating": base_rating,
                "attack": int(best["attack"]),
                "midfield": int(best["midfield"]),
                "defence": int(best["defence"]),
                "goalkeeper": int(best["goalkeeper"]),
                "consistency": consistency,
            }
            fits = default_fits(primary, secondary)
            for pos, fit in fits.items():
                position_fits_rows.append({"player_id": pid, "position": pos, "fit": fit})

        modifier = int(max(-15, min(10, round(row["era_score"] - peak_scores[row["player"]]))))
        era_id = f"{pid}_{row['club_id']}_{row['era'].replace('-', '_')}"
        player_eras.append(
            {
                "id": era_id,
                "player_id": pid,
                "club_id": row["club_id"],
                "era": row["era"],
                "primary_position": row["primary_position"],
                "secondary_positions": "|".join(row["secondary_positions"]),
                "rating_modifier": modifier,
                "include": "true",
            }
        )

    # Deduplicate position fits (keep max fit per player+position)
    fit_best: dict[tuple[str, str], int] = {}
    for r in position_fits_rows:
        key = (r["player_id"], r["position"])
        fit_best[key] = max(fit_best.get(key, 0), r["fit"])
    position_fits_rows = [
        {"player_id": pid, "position": pos, "fit": fit} for (pid, pos), fit in fit_best.items()
    ]

    era_mods: dict[tuple[str, str, str], int] = {}
    for pe in player_eras:
        era_mods[(pe["player_id"], pe["club_id"], pe["era"])] = pe["rating_modifier"]

    pools: list[dict] = []
    for (club_id, era), grp in ratings.groupby(["club_id", "era"]):
        if SPIN_CLUBS and club_id not in SPIN_CLUBS:
            continue
        if era in SPIN_EXCLUDE_ERAS:
            continue
        count = len(grp)
        if count < 5:
            continue
        effective = []
        for _, row in grp.iterrows():
            pid = slugify(row["player"])
            base = players_map[pid]["base_rating"]
            mod = era_mods.get((pid, club_id, era), 0)
            effective.append(base + mod)
        top_rating = max(effective)
        avg_rating = sum(effective) / len(effective)
        tier = spin_pool_tier(top_rating, avg_rating)
        if tier > 3:
            continue
        pools.append(
            {
                "id": f"{club_id}_{era.replace('-', '_')}",
                "club_id": club_id,
                "era": era,
                "spin_tier": tier,
                "min_eligible_players": min(count, 5),
                "is_active": "true",
            }
        )

    return list(players_map.values()), player_eras, position_fits_rows, pools


def write_csv(name: str, rows: list[dict], fieldnames: list[str]) -> None:
    path = DATA_DIR / name
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path}")


def write_report(ratings: pd.DataFrame, players: list[dict], pools: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# Dataset Summary\n"]
    lines.append(f"- Unique players: {len(players)}")
    lines.append(f"- Player-era rows: {len(ratings)}")
    lines.append(f"- Team-era pools: {len(pools)}\n")

    lines.append("## Players per club+era (top pools)\n")
    counts = ratings.groupby(["club_id", "era"]).size().sort_values(ascending=False)
    for (club, era), n in counts.head(30).items():
        lines.append(f"- {club} {era}: {n}")

    lines.append("\n## Top 10 rated per era\n")
    for era in ERAS:
        top = ratings[ratings["era"] == era].nlargest(10, "era_score")
        lines.append(f"\n### {era}\n")
        for _, r in top.iterrows():
            lines.append(f"- {r['player']} ({r['club_id']}) — score {r['era_score']:.1f}")

    (REPORT_DIR / "dataset_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Report -> {REPORT_DIR / 'dataset_summary.md'}")


def build(dry_run: bool = False) -> dict:
    merged = load_and_merge()
    agg = aggregate_era_rows(merged)
    ratings = compute_ratings(agg)
    if ratings.empty:
        raise RuntimeError("No qualified player-era rows after filtering")

    players, player_eras, position_fits, pools = build_players_tables(ratings)
    summary = {
        "players": len(players),
        "player_eras": len(player_eras),
        "position_fits": len(position_fits),
        "pools": len(pools),
    }
    print(json.dumps(summary, indent=2))

    if dry_run:
        return summary

    write_csv(
        "players.csv",
        players,
        ["id", "name", "slug", "primary_position", "secondary_positions", "base_rating", "attack", "midfield", "defence", "goalkeeper", "consistency"],
    )
    write_csv(
        "player_eras.csv",
        player_eras,
        ["id", "player_id", "club_id", "era", "primary_position", "secondary_positions", "rating_modifier", "include"],
    )
    write_csv("position_fits.csv", position_fits, ["player_id", "position", "fit"])
    write_csv(
        "team_era_pools.csv",
        pools,
        ["id", "club_id", "era", "spin_tier", "min_eligible_players", "is_active"],
    )
    write_report(ratings, players, pools)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    build(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
