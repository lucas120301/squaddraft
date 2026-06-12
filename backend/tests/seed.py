"""Test-only DB seeding (in-memory SQLite)."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.formations import FORMATIONS
from app.db.models import Club, Formation, Player, PlayerEra, PositionFit, TeamEraPool

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

POSITIONS = [
    "GK", "LB", "RB", "CB", "LWB", "RWB", "DM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST"
]


def _read_csv(name: str) -> list[dict]:
    path = FIXTURES_DIR / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _default_fits(primary: str, secondary: list[str]) -> dict[str, int]:
    fits = {p: 20 for p in POSITIONS}
    fits[primary] = 97
    for s in secondary:
        if s in fits:
            fits[s] = max(fits[s], 82)
    if primary == "GK":
        fits["GK"] = 98
    for p in POSITIONS:
        if p == primary:
            continue
        if p in secondary:
            continue
        if primary in {"CB", "LB", "RB"} and p in {"CB", "LB", "RB", "LWB", "RWB"}:
            fits[p] = max(fits[p], 65)
        if primary in {"CM", "DM", "CAM"} and p in {"CM", "DM", "CAM", "LM", "RM"}:
            fits[p] = max(fits[p], 60)
        if primary in {"ST", "LW", "RW"} and p in {"ST", "LW", "RW", "CAM"}:
            fits[p] = max(fits[p], 55)
    return fits


async def seed_all(session: AsyncSession) -> None:
    for fid, data in FORMATIONS.items():
        session.add(Formation(id=fid, name=data["name"], slots=data["slots"], is_active=True))

    for row in _read_csv("clubs.csv"):
        session.add(
            Club(
                id=row["id"],
                name=row["name"],
                short_name=row.get("short_name") or row["name"],
                slug=row["slug"],
                is_active=True,
            )
        )

    for row in _read_csv("players.csv"):
        secondary = [p.strip() for p in row.get("secondary_positions", "").split("|") if p.strip()]
        session.add(
            Player(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                primary_position=row["primary_position"],
                secondary_positions=secondary,
                base_rating=int(row["base_rating"]),
                attack=int(row["attack"]) if row.get("attack") else None,
                midfield=int(row["midfield"]) if row.get("midfield") else None,
                defence=int(row["defence"]) if row.get("defence") else None,
                goalkeeper=int(row["goalkeeper"]) if row.get("goalkeeper") else None,
                consistency=int(row.get("consistency") or 75),
            )
        )
        fits = _default_fits(row["primary_position"], secondary)
        for pos, fit in fits.items():
            session.add(
                PositionFit(
                    id=f"{row['id']}_{pos.lower()}",
                    player_id=row["id"],
                    position=pos,
                    fit=fit,
                )
            )

    for row in _read_csv("player_eras.csv"):
        secondary = [p.strip() for p in row.get("secondary_positions", "").split("|") if p.strip()]
        session.add(
            PlayerEra(
                id=row["id"],
                player_id=row["player_id"],
                club_id=row["club_id"],
                era=row["era"],
                primary_position=row.get("primary_position") or None,
                secondary_positions=secondary,
                rating_modifier=int(row.get("rating_modifier") or 0),
                include=row.get("include", "true").lower() != "false",
            )
        )

    for row in _read_csv("team_era_pools.csv"):
        session.add(
            TeamEraPool(
                id=row["id"],
                club_id=row["club_id"],
                era=row["era"],
                spin_tier=int(row.get("spin_tier") or 3),
                is_active=True,
                min_eligible_players=int(row.get("min_eligible_players") or 5),
            )
        )

    await session.commit()
