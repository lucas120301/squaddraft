import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rooms import get_authenticated_player
from app.core.config import settings
from app.core.security import verify_token
from app.db.database import SessionLocal, get_session
from app.db.models import Room, RoomPlayer
from app.services.draft_service import process_expired_timers
from app.services.room_service import build_room_state
from app.websockets.manager import ws_manager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clubs, draft, fits, formations, rooms


async def timer_loop() -> None:
    while True:
        async with SessionLocal() as session:
            await process_expired_timers(session)
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(timer_loop())
    yield
    task.cancel()


app = FastAPI(title="PL Era Draft API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rooms.router, prefix="/api/v1")
app.include_router(draft.router, prefix="/api/v1")
app.include_router(fits.router, prefix="/api/v1")
app.include_router(formations.router, prefix="/api/v1")
app.include_router(clubs.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/rooms/{code}")
async def websocket_room(
    websocket: WebSocket,
    code: str,
    room_player_id: str,
    client_token: str,
):
    async with SessionLocal() as session:
        room = (await session.execute(select(Room).where(Room.code == code.upper()))).scalar_one_or_none()
        if not room:
            await websocket.close(code=4004)
            return
        player = (
            await session.execute(
                select(RoomPlayer).where(RoomPlayer.id == room_player_id, RoomPlayer.room_id == room.id)
            )
        ).scalar_one_or_none()
        if not player or not verify_token(client_token, player.client_token_hash, settings.client_token_secret):
            await websocket.close(code=4001)
            return

    await ws_manager.connect(code.upper(), room_player_id, websocket)
    try:
        async with SessionLocal() as session:
            room = (await session.execute(select(Room).where(Room.code == code.upper()))).scalar_one()
            state = await build_room_state(session, room, room_player_id)
        await websocket.send_json({"type": "room_state", "payload": state})

        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")
            if mtype == "heartbeat":
                await websocket.send_json({"type": "heartbeat", "payload": {"ok": True}})
            elif mtype == "view_player":
                payload = msg.get("payload", {})
                ws_manager.set_focus(code.upper(), room_player_id, payload)
                await ws_manager.broadcast_room(
                    code.upper(),
                    {"type": "active_view_update", "payload": {"focused_player_id": payload.get("player_id")}},
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(code.upper(), room_player_id)
