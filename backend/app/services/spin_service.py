from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.positions import format_position_label
from app.db.models import DraftPick, Player, PlayerEra, TeamEraPool


async def get_drafted_player_ids(session: AsyncSession, room_id: str) -> set[str]:
    rows = (await session.execute(select(DraftPick.player_id).where(DraftPick.room_id == room_id))).scalars().all()
    return set(rows)


async def get_eligible_players(
    session: AsyncSession, room_id: str, club_id: str, era: str
) -> list[dict]:
    drafted = await get_drafted_player_ids(session, room_id)
    rows = (
        await session.execute(
            select(PlayerEra, Player)
            .join(Player, PlayerEra.player_id == Player.id)
            .where(
                PlayerEra.club_id == club_id,
                PlayerEra.era == era,
                PlayerEra.include == True,  # noqa: E712
            )
        )
    ).all()

    result = []
    for pe, player in rows:
        if player.id in drafted:
            continue
        era_primary = pe.primary_position or player.primary_position
        era_secondary = pe.secondary_positions if pe.secondary_positions else (player.secondary_positions or [])
        result.append(
            {
                "id": player.id,
                "name": player.name,
                "primary_position": era_primary,
                "secondary_positions": era_secondary,
                "positions_label": format_position_label(era_primary, era_secondary),
            }
        )
    result.sort(key=lambda p: p["name"])
    return result


async def generate_spin(session: AsyncSession, room_id: str, drafted: set[str] | None = None) -> dict:
    if drafted is None:
        drafted = await get_drafted_player_ids(session, room_id)

    pools = (
        await session.execute(
            select(TeamEraPool).where(
                TeamEraPool.is_active == True,  # noqa: E712
                TeamEraPool.spin_tier <= 3,
            )
        )
    ).scalars().all()

    candidates = []
    for pool in pools:
        count = len(
            (
                await session.execute(
                    select(PlayerEra.player_id).where(
                        PlayerEra.club_id == pool.club_id,
                        PlayerEra.era == pool.era,
                        PlayerEra.include == True,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        available = [
            pid
            for pid in (
                await session.execute(
                    select(PlayerEra.player_id).where(
                        PlayerEra.club_id == pool.club_id,
                        PlayerEra.era == pool.era,
                        PlayerEra.include == True,  # noqa: E712
                    )
                )
            ).scalars().all()
            if pid not in drafted
        ]
        if len(available) >= max(1, pool.min_eligible_players - 2):
            weight = max(1, 6 - pool.spin_tier)
            candidates.append((pool, weight))

    if not candidates:
        raise ValueError("No eligible spins available")

    pools_only, weights = zip(*candidates)
    chosen = random.choices(list(pools_only), weights=list(weights), k=1)[0]
    return {"club_id": chosen.club_id, "era": chosen.era}
