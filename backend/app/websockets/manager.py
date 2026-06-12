from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, dict[str, WebSocket]] = {}
        self.focus: dict[str, dict[str, Any]] = {}

    async def connect(self, room_code: str, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(room_code, {})[player_id] = websocket

    def disconnect(self, room_code: str, player_id: str) -> None:
        if room_code in self.rooms:
            self.rooms[room_code].pop(player_id, None)
            if not self.rooms[room_code]:
                del self.rooms[room_code]

    async def broadcast_room(self, room_code: str, message: dict) -> None:
        conns = self.rooms.get(room_code, {})
        dead = []
        for pid, ws in conns.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(pid)
        for pid in dead:
            conns.pop(pid, None)

    def set_focus(self, room_code: str, player_id: str, payload: dict) -> None:
        self.focus.setdefault(room_code, {})[player_id] = payload

    def get_focus(self, room_code: str) -> dict | None:
        room_focus = self.focus.get(room_code, {})
        if not room_focus:
            return None
        _, data = next(iter(room_focus.items()))
        return data


ws_manager = ConnectionManager()
