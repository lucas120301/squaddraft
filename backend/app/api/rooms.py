from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.formations import FORMATIONS
from app.core.security import verify_token
from app.db.database import get_session
from app.db.models import Room, RoomPlayer
from app.schemas.room import CreateRoomRequest, JoinRoomRequest, LobbyUpdateRequest
from app.services.room_service import build_room_state, create_room, join_room, start_draft, update_lobby

router = APIRouter(prefix="/rooms", tags=["rooms"])


async def get_authenticated_player(
    code: str,
    x_room_player_id: str = Header(),
    x_client_token: str = Header(),
    session: AsyncSession = Depends(get_session),
) -> tuple[Room, RoomPlayer]:
    room = (await session.execute(select(Room).where(Room.code == code.upper()))).scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    player = (
        await session.execute(
            select(RoomPlayer).where(RoomPlayer.id == x_room_player_id, RoomPlayer.room_id == room.id)
        )
    ).scalar_one_or_none()
    if not player or not verify_token(x_client_token, player.client_token_hash, settings.client_token_secret):
        raise HTTPException(401, "Unauthorized")
    return room, player


@router.post("")
async def api_create_room(body: CreateRoomRequest, session: AsyncSession = Depends(get_session)):
    room, player, token = await create_room(session, body.nickname, body.max_players)
    return {
        "room_id": room.id,
        "room_code": room.code,
        "room_player_id": player.id,
        "client_token": token,
    }


@router.post("/{code}/join")
async def api_join_room(code: str, body: JoinRoomRequest, session: AsyncSession = Depends(get_session)):
    try:
        room, player, token = await join_room(session, code, body.nickname)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "room_id": room.id,
        "room_code": room.code,
        "room_player_id": player.id,
        "client_token": token,
    }


@router.get("/{code}")
async def api_get_room(code: str, session: AsyncSession = Depends(get_session)):
    room = (await session.execute(select(Room).where(Room.code == code.upper()))).scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    return await build_room_state(session, room, None)


@router.put("/{code}/lobby")
async def api_update_lobby(
    body: LobbyUpdateRequest,
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    try:
        await update_lobby(session, room, player, body.formation_id, body.team_name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"saved": True, "formation_id": player.formation_id, "team_name": player.team_name}


@router.post("/{code}/start")
async def api_start_draft(
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, host = auth
    try:
        room = await start_draft(session, room, host)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return await build_room_state(session, room, host.id)


@router.get("/{code}/results")
async def api_results(code: str, session: AsyncSession = Depends(get_session)):
    room = (await session.execute(select(Room).where(Room.code == code.upper()))).scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    state = await build_room_state(session, room, None)
    return {"records": state.get("records", [])}
