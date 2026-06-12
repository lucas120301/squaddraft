from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import Room, RoomPlayer
from app.api.rooms import get_authenticated_player
from app.schemas.room import LifelineChooseRequest, PickRequest, RerollRequest
from app.services.draft_service import choose_lifeline, lifeline_options, reroll_spin
from app.services.room_service import build_room_state, make_pick, reveal_spin

router = APIRouter(prefix="/rooms", tags=["draft"])


@router.post("/{code}/draft/spin")
async def api_spin(
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    try:
        return await reveal_spin(session, room, player)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{code}/draft/pick")
async def api_pick(
    body: PickRequest,
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    try:
        state = await make_pick(session, room, player, body.player_id, body.slot_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return state


@router.post("/{code}/draft/reroll")
async def api_reroll(
    body: RerollRequest,
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    try:
        return await reroll_spin(session, room, player, body.reroll_type)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{code}/draft/lifeline")
async def api_lifeline(
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    try:
        return await lifeline_options(session, room, player)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{code}/draft/lifeline/choose")
async def api_lifeline_choose(
    body: LifelineChooseRequest,
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    try:
        return await choose_lifeline(session, room, player, body.club_id, body.era)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
