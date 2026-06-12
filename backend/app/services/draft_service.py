from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.formations import get_formation_slots
from app.db.models import DraftPick, Player, PlayerEra, Room, RoomPlayer, RerollEvent
from app.services.evaluation_service import draft_value
from app.services.room_service import active_player_id, get_player_fits, is_round_start, make_pick, personal_pick_number
from app.services.spin_service import generate_spin, get_eligible_players
from app.websockets.manager import ws_manager


async def reroll_spin(session: AsyncSession, room: Room, actor: RoomPlayer, reroll_type: str = "normal") -> dict:
    if room.status != "drafting":
        raise ValueError("Not in draft")
    if active_player_id(room) != actor.id:
        raise ValueError("Not your turn")
    if not room.spin_revealed:
        raise ValueError("Spin first before rerolling")
    if not is_round_start(room):
        raise ValueError("Cannot reroll after picks in this round")

    if reroll_type == "normal":
        if actor.normal_rerolls_left <= 0:
            raise ValueError("No rerolls left")
        actor.normal_rerolls_left -= 1
    else:
        raise ValueError("Use lifeline endpoint for late lifeline")

    old_club, old_era = room.current_spin_club_id, room.current_spin_era
    drafted = set(
        (await session.execute(select(DraftPick.player_id).where(DraftPick.room_id == room.id))).scalars().all()
    )
    spin = await generate_spin(session, room.id, drafted)
    room.current_spin_club_id = spin["club_id"]
    room.current_spin_era = spin["era"]

    room.current_pick_deadline = datetime.now(timezone.utc) + timedelta(seconds=room.pick_timer_seconds)

    session.add(
        RerollEvent(
            room_id=room.id,
            room_player_id=actor.id,
            pick_index=room.current_pick_index,
            old_club_id=old_club,
            old_era=old_era,
            new_club_id=spin["club_id"],
            new_era=spin["era"],
            reroll_type=reroll_type,
        )
    )
    await session.commit()
    from app.services.room_service import build_room_state

    state = await build_room_state(session, room, None)
    await ws_manager.broadcast_room(room.code, {"type": "spin_updated", "payload": state})
    return state


async def lifeline_options(session: AsyncSession, room: Room, actor: RoomPlayer) -> dict:
    if room.status != "drafting":
        raise ValueError("Not in draft")
    if active_player_id(room) != actor.id:
        raise ValueError("Not your turn")
    if not room.spin_revealed:
        raise ValueError("Spin first before using lifeline")
    if not is_round_start(room):
        raise ValueError("Cannot use lifeline after picks in this round")
    if actor.late_lifelines_left <= 0:
        raise ValueError("No lifelines left")
    if personal_pick_number(actor.id, room) < 8:
        raise ValueError("Lifeline available from pick 8")

    drafted = set(
        (await session.execute(select(DraftPick.player_id).where(DraftPick.room_id == room.id))).scalars().all()
    )
    opts = []
    seen = {(room.current_spin_club_id, room.current_spin_era)}
    while len(opts) < 2:
        spin = await generate_spin(session, room.id, drafted)
        key = (spin["club_id"], spin["era"])
        if key not in seen:
            seen.add(key)
            opts.append(spin)
    return {"options": opts}


async def choose_lifeline(session: AsyncSession, room: Room, actor: RoomPlayer, club_id: str, era: str) -> dict:
    if actor.late_lifelines_left <= 0:
        raise ValueError("No lifelines left")
    actor.late_lifelines_left -= 1
    old_club, old_era = room.current_spin_club_id, room.current_spin_era
    room.current_spin_club_id = club_id
    room.current_spin_era = era
    room.current_pick_deadline = datetime.now(timezone.utc) + timedelta(seconds=room.pick_timer_seconds)
    session.add(
        RerollEvent(
            room_id=room.id,
            room_player_id=actor.id,
            pick_index=room.current_pick_index,
            old_club_id=old_club,
            old_era=old_era,
            new_club_id=club_id,
            new_era=era,
            reroll_type="lifeline",
        )
    )
    await session.commit()
    from app.services.room_service import build_room_state

    state = await build_room_state(session, room, None)
    await ws_manager.broadcast_room(room.code, {"type": "spin_updated", "payload": state})
    return state


async def auto_pick(session: AsyncSession, room: Room) -> None:
    if room.status != "drafting":
        return
    if not room.spin_revealed:
        return
    active_id = active_player_id(room)
    if not active_id:
        return
    actor = (await session.execute(select(RoomPlayer).where(RoomPlayer.id == active_id))).scalar_one()

    eligible = await get_eligible_players(session, room.id, room.current_spin_club_id, room.current_spin_era)
    if not eligible:
        return

    slots = get_formation_slots(actor.formation_id)
    filled = {
        p.slot_id
        for p in (await session.execute(select(DraftPick).where(DraftPick.room_player_id == actor.id))).scalars().all()
    }
    open_slots = [s for s in slots if s["slot_id"] not in filled]

    best = None
    for pl in eligible:
        player = (await session.execute(select(Player).where(Player.id == pl["id"]))).scalar_one()
        pe = (
            await session.execute(
                select(PlayerEra).where(
                    PlayerEra.player_id == pl["id"],
                    PlayerEra.club_id == room.current_spin_club_id,
                    PlayerEra.era == room.current_spin_era,
                )
            )
        ).scalar_one_or_none()
        modifier = pe.rating_modifier if pe else 0
        dv = draft_value(player.base_rating, modifier)
        for slot in open_slots:
            fits = await get_player_fits(
                session,
                pl["id"],
                [slot["position"]],
                club_id=room.current_spin_club_id,
                era=room.current_spin_era,
            )
            fit = fits.get(slot["position"], 0)
            if fit <= 0:
                continue
            score = dv * (fit / 100)
            if best is None or score > best[0]:
                best = (score, pl["id"], slot["slot_id"])

    if best:
        _, player_id, slot_id = best
        await make_pick(session, room, actor, player_id, slot_id, was_auto=True)


async def process_expired_timers(session: AsyncSession) -> None:
    rooms = (
        await session.execute(
            select(Room).where(Room.status == "drafting", Room.current_pick_deadline != None)  # noqa: E711
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for room in rooms:
        if not room.current_pick_deadline:
            continue
        deadline = room.current_pick_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline <= now:
            await auto_pick(session, room)
