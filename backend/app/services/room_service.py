from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.formations import FORMATIONS, get_formation_slots
from app.core.security import generate_client_token, generate_room_code, hash_token
from app.db.models import (
    Club,
    DraftPick,
    Player,
    PlayerEra,
    PositionFit,
    Room,
    RoomPlayer,
    SimulationResult,
    TeamEraPool,
    TeamEvaluation,
)
from app.services.evaluation_service import SlotAssignment, draft_value, evaluate_team
from app.services.simulation_service import make_seed, simulate_record
from app.services.spin_service import generate_spin, get_eligible_players
from app.websockets.manager import ws_manager


def active_player_id(room: Room) -> str | None:
    order = room.draft_order or []
    if not order:
        return None
    count = len(order)
    idx = room.current_pick_index
    round_index = idx // count
    index_in_round = idx % count
    if round_index % 2 == 0:
        return order[index_in_round]
    return order[count - 1 - index_in_round]


def total_picks(room: Room, player_count: int) -> int:
    return room.total_rounds * player_count


def spin_round_number(room: Room) -> int:
    order = room.draft_order or []
    if not order:
        return 1
    return room.current_pick_index // len(order) + 1


def is_round_start(room: Room) -> bool:
    order = room.draft_order or []
    if not order:
        return True
    return room.current_pick_index % len(order) == 0


def personal_pick_number(room_player_id: str, room: Room) -> int:
    order = room.draft_order or []
    count = len(order)
    picks_made = 0
    for i in range(room.current_pick_index):
        round_index = i // count
        index_in_round = i % count
        if round_index % 2 == 0:
            pid = order[index_in_round]
        else:
            pid = order[count - 1 - index_in_round]
        if pid == room_player_id:
            picks_made += 1
    return picks_made + 1


async def create_room(session: AsyncSession, nickname: str, max_players: int = 6) -> tuple[Room, RoomPlayer, str]:
    code = generate_room_code()
    while (await session.execute(select(Room).where(Room.code == code))).scalar_one_or_none():
        code = generate_room_code()

    token = generate_client_token()
    room = Room(code=code, max_players=max_players, pick_timer_seconds=settings.pick_timer_seconds)
    session.add(room)
    await session.flush()

    player = RoomPlayer(
        room_id=room.id,
        nickname=nickname,
        team_name=nickname,
        client_token_hash=hash_token(token, settings.client_token_secret),
        is_host=True,
        draft_position=0,
    )
    session.add(player)
    room.host_room_player_id = player.id
    await session.commit()
    await session.refresh(room)
    await session.refresh(player)
    return room, player, token


async def join_room(session: AsyncSession, code: str, nickname: str) -> tuple[Room, RoomPlayer, str]:
    room = (await session.execute(select(Room).where(Room.code == code.upper()))).scalar_one_or_none()
    if not room:
        raise ValueError("Room not found")
    if room.status != "lobby":
        raise ValueError("Room is not in lobby")
    existing = (
        await session.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.nickname == nickname)
        )
    ).scalar_one_or_none()
    if existing:
        raise ValueError("Nickname taken")

    humans = (
        await session.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.is_bot == False)  # noqa: E712
        )
    ).scalars().all()
    if len(humans) >= room.max_players:
        raise ValueError("Room is full")

    token = generate_client_token()
    player = RoomPlayer(
        room_id=room.id,
        nickname=nickname,
        team_name=nickname,
        client_token_hash=hash_token(token, settings.client_token_secret),
    )
    session.add(player)
    await session.commit()
    await session.refresh(room)
    await session.refresh(player)
    state = await build_room_state(session, room, None)
    await ws_manager.broadcast_room(room.code, {"type": "room_state", "payload": state})
    return room, player, token


async def update_lobby(
    session: AsyncSession, room: Room, player: RoomPlayer, formation_id: str | None, team_name: str | None
) -> RoomPlayer:
    if room.status != "lobby":
        raise ValueError("Can only update lobby before draft")
    if formation_id:
        if formation_id not in FORMATIONS:
            raise ValueError("Invalid formation")
        player.formation_id = formation_id
    if team_name is not None:
        player.team_name = team_name.strip() or player.nickname
    await session.commit()
    await session.refresh(player)
    state = await build_room_state(session, room, None)
    await ws_manager.broadcast_room(room.code, {"type": "room_state", "payload": state})
    return player


async def start_draft(session: AsyncSession, room: Room, host: RoomPlayer) -> Room:
    if not host.is_host:
        raise ValueError("Only host can start draft")
    if room.status != "lobby":
        raise ValueError("Draft already started")

    players = (
        await session.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.is_bot == False)  # noqa: E712
        )
    ).scalars().all()
    if len(players) < 2:
        raise ValueError("Need at least 2 players")
    for p in players:
        if not p.formation_id:
            raise ValueError(f"{p.nickname} has not selected a formation")

    order = [p.id for p in players]
    random.shuffle(order)
    for i, pid in enumerate(order):
        rp = next(p for p in players if p.id == pid)
        rp.draft_position = i

    room.draft_order = order
    room.status = "drafting"
    room.current_pick_index = 0
    room.pick_timer_seconds = settings.pick_timer_seconds
    room.current_spin_club_id = None
    room.current_spin_era = None
    room.spin_revealed = False
    room.current_pick_deadline = None

    await session.commit()
    await session.refresh(room)
    await ws_manager.broadcast_room(room.code, {"type": "draft_started", "payload": await build_room_state(session, room, None)})
    return room


async def get_player_fits(
    session: AsyncSession,
    player_id: str,
    positions: list[str],
    *,
    club_id: str | None = None,
    era: str | None = None,
) -> dict[str, int]:
    from app.core.positions import default_fits

    era_row = None
    if club_id and era:
        era_row = (
            await session.execute(
                select(PlayerEra).where(
                    PlayerEra.player_id == player_id,
                    PlayerEra.club_id == club_id,
                    PlayerEra.era == era,
                )
            )
        ).scalar_one_or_none()

    if era_row and era_row.primary_position:
        computed = default_fits(era_row.primary_position, era_row.secondary_positions or [])
        return {pos: computed.get(pos, 0) for pos in positions}

    rows = (
        await session.execute(
            select(PositionFit).where(PositionFit.player_id == player_id, PositionFit.position.in_(positions))
        )
    ).scalars().all()
    fits = {r.position: r.fit for r in rows}
    player = (await session.execute(select(Player).where(Player.id == player_id))).scalar_one()
    for pos in positions:
        fits.setdefault(pos, 100 if pos == player.primary_position else 30)
    return fits


async def reveal_spin(session: AsyncSession, room: Room, actor: RoomPlayer) -> dict:
    if room.status != "drafting":
        raise ValueError("Not in draft")
    if active_player_id(room) != actor.id:
        raise ValueError("Not your turn")
    if room.spin_revealed:
        raise ValueError("Spin already revealed")

    drafted = set(
        (await session.execute(select(DraftPick.player_id).where(DraftPick.room_id == room.id))).scalars().all()
    )
    spin = await generate_spin(session, room.id, drafted)
    room.current_spin_club_id = spin["club_id"]
    room.current_spin_era = spin["era"]
    room.spin_revealed = True
    room.current_pick_deadline = datetime.now(timezone.utc) + timedelta(seconds=room.pick_timer_seconds)

    await session.commit()
    await session.refresh(room)
    state = await build_room_state(session, room, None)
    await ws_manager.broadcast_room(room.code, {"type": "spin_revealed", "payload": state})
    return state


async def make_pick(
    session: AsyncSession,
    room: Room,
    actor: RoomPlayer,
    player_id: str,
    slot_id: str,
    was_auto: bool = False,
) -> dict:
    if room.status != "drafting":
        raise ValueError("Not in draft")
    active_id = active_player_id(room)
    if active_id != actor.id:
        raise ValueError("Not your turn")
    if not room.spin_revealed:
        raise ValueError("Spin must be revealed before picking")
    if not actor.formation_id:
        raise ValueError("No formation selected")

    slots = get_formation_slots(actor.formation_id)
    slot = next((s for s in slots if s["slot_id"] == slot_id), None)
    if not slot:
        raise ValueError("Invalid slot")

    existing_slots = (
        await session.execute(
            select(DraftPick).where(DraftPick.room_id == room.id, DraftPick.room_player_id == actor.id)
        )
    ).scalars().all()
    if any(p.slot_id == slot_id for p in existing_slots):
        raise ValueError("Slot already filled")
    if any(p.player_id == player_id for p in existing_slots):
        raise ValueError("Player already on your team")

    dup = (
        await session.execute(
            select(DraftPick).where(DraftPick.room_id == room.id, DraftPick.player_id == player_id)
        )
    ).scalar_one_or_none()
    if dup:
        raise ValueError("Player already drafted")

    eligible = await get_eligible_players(
        session, room.id, room.current_spin_club_id, room.current_spin_era
    )
    if player_id not in {p["id"] for p in eligible}:
        raise ValueError("Player not on current board")

    fits = await get_player_fits(
        session,
        player_id,
        [slot["position"]],
        club_id=room.current_spin_club_id,
        era=room.current_spin_era,
    )
    fit = fits.get(slot["position"], 0)
    if fit <= 0:
        raise ValueError("Cannot play in that slot")

    player = (await session.execute(select(Player).where(Player.id == player_id))).scalar_one()
    pe = (
        await session.execute(
            select(PlayerEra).where(
                PlayerEra.player_id == player_id,
                PlayerEra.club_id == room.current_spin_club_id,
                PlayerEra.era == room.current_spin_era,
            )
        )
    ).scalar_one_or_none()
    modifier = pe.rating_modifier if pe else 0
    dv = draft_value(player.base_rating, modifier)

    order = room.draft_order or []
    count = len(order)
    round_index = room.current_pick_index // count

    pick = DraftPick(
        room_id=room.id,
        room_player_id=actor.id,
        pick_index=room.current_pick_index,
        round_index=round_index,
        spin_club_id=room.current_spin_club_id,
        spin_era=room.current_spin_era,
        player_id=player_id,
        slot_id=slot_id,
        player_era_id=pe.id if pe else None,
        draft_value=dv,
        was_auto_pick=was_auto,
    )
    session.add(pick)

    room.current_pick_index += 1
    player_count = len(order)
    if room.current_pick_index >= total_picks(room, player_count):
        room.status = "simulating"
        room.draft_completed_at = datetime.now(timezone.utc)
        room.current_pick_deadline = None
        await session.flush()
        await run_simulation(session, room)
        room.status = "complete"
    else:
        if is_round_start(room):
            room.current_spin_club_id = None
            room.current_spin_era = None
            room.spin_revealed = False
            room.current_pick_deadline = None
        else:
            room.current_pick_deadline = datetime.now(timezone.utc) + timedelta(seconds=room.pick_timer_seconds)

    await session.commit()
    await session.refresh(room)
    state = await build_room_state(session, room, None)
    await ws_manager.broadcast_room(room.code, {"type": "pick_made", "payload": state})
    if room.status == "complete":
        await ws_manager.broadcast_room(room.code, {"type": "simulation_complete", "payload": state})
    return state


async def run_simulation(session: AsyncSession, room: Room) -> None:
    players = (await session.execute(select(RoomPlayer).where(RoomPlayer.room_id == room.id))).scalars().all()
    completed_at = room.draft_completed_at.isoformat() if room.draft_completed_at else ""
    seed = make_seed(room.id, completed_at, settings.simulation_version)
    room.simulation_seed = str(seed)
    room.simulation_version = settings.simulation_version

    results_for_sort = []
    for idx, rp in enumerate(players):
        picks = (
            await session.execute(
                select(DraftPick).where(DraftPick.room_id == room.id, DraftPick.room_player_id == rp.id)
            )
        ).scalars().all()
        slots = get_formation_slots(rp.formation_id)
        slot_pos = {s["slot_id"]: s["position"] for s in slots}
        assignments = []
        player_attrs = {}
        for pick in picks:
            player = (await session.execute(select(Player).where(Player.id == pick.player_id))).scalar_one()
            pe = None
            if pick.player_era_id:
                pe = (await session.execute(select(PlayerEra).where(PlayerEra.id == pick.player_era_id))).scalar_one_or_none()
            modifier = pe.rating_modifier if pe else 0
            pos = slot_pos[pick.slot_id]
            fits = await get_player_fits(
                session,
                pick.player_id,
                [pos],
                club_id=pe.club_id if pe else None,
                era=pe.era if pe else None,
            )
            fit = fits.get(pos, 0)
            assignments.append(
                SlotAssignment(
                    slot_id=pick.slot_id,
                    position=pos,
                    player_id=pick.player_id,
                    draft_value=float(pick.draft_value),
                    fit=fit,
                )
            )
            player_attrs[pick.player_id] = {
                "base_rating": player.base_rating,
                "rating_modifier": modifier,
                "attack": player.attack,
                "midfield": player.midfield,
                "defence": player.defence,
            }

        eval_result = evaluate_team(rp.formation_id, assignments, player_attrs)
        session.add(
            TeamEvaluation(
                room_id=room.id,
                room_player_id=rp.id,
                formation_id=rp.formation_id,
                internal_team_strength=eval_result["team_strength"],
                internal_attack_score=eval_result["attack_score"],
                internal_midfield_score=eval_result["midfield_score"],
                internal_defence_score=eval_result["defence_score"],
                internal_gk_score=eval_result["gk_score"],
                internal_balance_score=eval_result["balance_score"],
            )
        )

        sim = simulate_record(eval_result["team_strength"], seed, idx)
        session.add(
            SimulationResult(
                room_id=room.id,
                room_player_id=rp.id,
                internal_team_strength=sim["internal_team_strength"],
                internal_season_strength=sim["internal_season_strength"],
                internal_expected_points=sim["internal_expected_points"],
                internal_points=sim["internal_points"],
                wins=sim["wins"],
                draws=sim["draws"],
                losses=sim["losses"],
            )
        )
        results_for_sort.append((rp, sim))


async def build_room_state(session: AsyncSession, room: Room, viewer_id: str | None) -> dict:
    players = (
        await session.execute(select(RoomPlayer).where(RoomPlayer.room_id == room.id).order_by(RoomPlayer.joined_at))
    ).scalars().all()
    picks = (
        await session.execute(select(DraftPick).where(DraftPick.room_id == room.id).order_by(DraftPick.pick_index))
    ).scalars().all()

    club_names = {}
    if room.current_spin_club_id:
        club = (await session.execute(select(Club).where(Club.id == room.current_spin_club_id))).scalar_one_or_none()
        if club:
            club_names[club.id] = club.name

    player_count = len(room.draft_order or []) or 1
    available = []
    if (
        room.status == "drafting"
        and room.spin_revealed
        and room.current_spin_club_id
        and room.current_spin_era
    ):
        available = await get_eligible_players(session, room.id, room.current_spin_club_id, room.current_spin_era)

    active_id = active_player_id(room) if room.status == "drafting" else None
    player_payload = []
    for p in players:
        pp = {
            "id": p.id,
            "nickname": p.nickname,
            "team_name": p.team_name or p.nickname,
            "formation_id": p.formation_id,
            "is_host": p.is_host,
            "normal_rerolls_left": p.normal_rerolls_left,
            "late_lifelines_left": p.late_lifelines_left,
            "picks": [],
        }
        for pick in picks:
            if pick.room_player_id != p.id:
                continue
            pl = (await session.execute(select(Player).where(Player.id == pick.player_id))).scalar_one()
            pp["picks"].append(
                {
                    "player_id": pick.player_id,
                    "name": pl.name,
                    "primary_position": pl.primary_position,
                    "slot_id": pick.slot_id,
                    "pick_index": pick.pick_index,
                }
            )
        player_payload.append(pp)

    records = []
    if room.status == "complete":
        sims = (
            await session.execute(
                select(SimulationResult, RoomPlayer)
                .join(RoomPlayer, SimulationResult.room_player_id == RoomPlayer.id)
                .where(SimulationResult.room_id == room.id)
            )
        ).all()
        records = sorted(
            [
                {
                    "room_player_id": sim.SimulationResult.room_player_id,
                    "team_name": sim.RoomPlayer.team_name or sim.RoomPlayer.nickname,
                    "nickname": sim.RoomPlayer.nickname,
                    "wins": sim.SimulationResult.wins,
                    "draws": sim.SimulationResult.draws,
                    "losses": sim.SimulationResult.losses,
                    "record": f"{sim.SimulationResult.wins}-{sim.SimulationResult.draws}-{sim.SimulationResult.losses}",
                    "_sort": sim.SimulationResult.internal_points,
                }
                for sim in sims
            ],
            key=lambda r: (-r["_sort"], -r["wins"], r["losses"]),
        )
        for r in records:
            r.pop("_sort", None)

    deadline_secs = None
    if room.current_pick_deadline:
        deadline = room.current_pick_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        delta = deadline - datetime.now(timezone.utc)
        deadline_secs = max(0, int(delta.total_seconds()))

    return {
        "room": {
            "code": room.code,
            "status": room.status,
            "current_pick_index": room.current_pick_index,
            "pick_timer_seconds": room.pick_timer_seconds,
            "timer_seconds_remaining": deadline_secs,
            "total_rounds": room.total_rounds,
            "spin_revealed": room.spin_revealed,
            "spin_round": spin_round_number(room) if room.status == "drafting" else None,
            "player_count": player_count if room.status == "drafting" else None,
        },
        "players": player_payload,
        "draft_order": room.draft_order or [],
        "active_room_player_id": active_id,
        "current_spin": {
            "club_id": room.current_spin_club_id,
            "club_name": club_names.get(room.current_spin_club_id, room.current_spin_club_id),
            "era": room.current_spin_era,
        }
        if room.spin_revealed and room.current_spin_club_id
        else None,
        "available_players": available,
        "records": records,
        "viewer_id": viewer_id,
    }
