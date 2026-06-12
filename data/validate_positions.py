#!/usr/bin/env python3
"""Sanity-check era positions for well-known players and flag suspicious CB tags."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent

# Players fans will notice if wrong — (name substring, expected roles per era substring or None)
SPOT_CHECKS: list[tuple[str, list[str]]] = [
    ("Ashley Young", ["LW", "LB", "CB"]),
    ("Andrew Robertson", ["LB"]),
    ("Trent Alexander-Arnold", ["LB", "RB"]),
    ("Mohamed Salah", ["LW", "RW", "ST"]),
    ("Harry Kane", ["ST"]),
    ("Raheem Sterling", ["LW", "RW", "ST"]),
    ("Bukayo Saka", ["RW", "LW", "CAM", "CM"]),
    ("Virgil van Dijk", ["CB"]),
    ("Kyle Walker", ["LB", "RB", "CB"]),
    ("John Terry", ["CB"]),
    ("Rio Ferdinand", ["CB"]),
    ("Gareth Bale", ["LW", "RW", "ST", "CM"]),
    ("Eden Hazard", ["LW", "RW", "CAM", "ST"]),
    ("Jamie Vardy", ["ST", "LW"]),  # early Leicester era is ambiguous in FBref
    ("Aaron Wan-Bissaka", ["LB", "RB", "CB"]),
    ("Kyle Walker-Peters", ["LB", "RB"]),
]

# Career attack rating can be high for full-backs — only flag CB tags that look like wingers.
SUSPICIOUS_ATTACK_CB_ALLOWED = {
    "Ashley Young",  # played CB at Villa late career
    "Joël Matip",
    "Abel Xavier",
    "Scott Minto",
    "Gerry Taggart",
    "Julian Dicks",
    "Ryan Fredericks",
}

SUSPICIOUS_ATTACK_CB_ATTACK = 85  # career attack rating


def load() -> tuple[dict, list[dict]]:
    players = {r["id"]: r for r in csv.DictReader(open(DATA_DIR / "players.csv"))}
    eras = list(csv.DictReader(open(DATA_DIR / "player_eras.csv")))
    return players, eras


def main() -> None:
    players, eras = load()
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in eras:
        p = players.get(row["player_id"])
        if p:
            by_name[p["name"]].append(row)

    print("=== Spot checks ===")
    failed = 0
    for name, allowed in SPOT_CHECKS:
        rows = [r for n, rs in by_name.items() if name.lower() in n.lower() for r in rs]
        if not rows:
            print(f"  MISSING {name}")
            failed += 1
            continue
        for r in sorted(rows, key=lambda x: x["era"]):
            pos = r["primary_position"]
            ok = pos in allowed
            mark = "ok" if ok else "BAD"
            if not ok:
                failed += 1
            print(f"  [{mark}] {name:28} {r['club_id']:16} {r['era']} -> {pos}")

    era_prim = Counter(r["primary_position"] for r in eras)
    print("\n=== Era position distribution ===")
    for pos, n in era_prim.most_common():
        print(f"  {pos}: {n}")

    suspicious = []
    for r in eras:
        if r["primary_position"] != "CB":
            continue
        p = players.get(r["player_id"])
        if not p:
            continue
        atk = int(p.get("attack") or 0)
        if atk >= SUSPICIOUS_ATTACK_CB_ATTACK and p["name"] not in SUSPICIOUS_ATTACK_CB_ALLOWED:
            suspicious.append((atk, p["name"], r["club_id"], r["era"]))

    suspicious.sort(reverse=True)
    print(f"\n=== High-attack (>{SUSPICIOUS_ATTACK_CB_ATTACK}) players tagged CB in an era: {len(suspicious)} ===")
    for row in suspicious[:15]:
        print(f"  atk={row[0]} {row[1]} @ {row[2]} {row[3]}")

    pools = {(r["club_id"], r["era"]) for r in csv.DictReader(open(DATA_DIR / "team_era_pools.csv"))}
    era_rb = sum(1 for r in eras if (r["club_id"], r["era"]) in pools and r["primary_position"] == "RB")
    def pool_has_wide_defenders(club_id: str, era: str) -> bool:
        for r in eras:
            if r["club_id"] != club_id or r["era"] != era:
                continue
            sec = [s for s in (r.get("secondary_positions") or "").split("|") if s]
            if r["primary_position"] in {"LB", "RB"}:
                return True
            if "LB" in sec or "RB" in sec:
                return True
        return False

    pools_with_rb = sum(1 for k in pools if pool_has_wide_defenders(k[0], k[1]))
    print(f"\n=== RB coverage ===")
    print(f"  Era rows with RB primary: {era_rb}")
    print(f"  Spin pools with LB/RB options: {pools_with_rb}/{len(pools)}")
    if pools_with_rb < len(pools):
        failed += 1

    mononyms = sorted(p["name"] for p in players.values() if len(p["name"].strip().split()) < 2)
    print(f"\n=== Mononym players kept: {len(mononyms)} ===")
    for name in mononyms[:12]:
        print(f"  {name}")
    if len(mononyms) > 12:
        print(f"  ... +{len(mononyms) - 12} more")

    print(f"\nSpot check failures: {failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
