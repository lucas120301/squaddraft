import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_full_draft_flow_two_players():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/v1/rooms", json={"nickname": "A"})
        a = r1.json()
        code = a["room_code"]

        r2 = await client.post(f"/api/v1/rooms/{code}/join", json={"nickname": "B"})
        b = r2.json()

        headers_a = {"X-Room-Player-Id": a["room_player_id"], "X-Client-Token": a["client_token"]}
        headers_b = {"X-Room-Player-Id": b["room_player_id"], "X-Client-Token": b["client_token"]}

        await client.put(f"/api/v1/rooms/{code}/lobby", json={"formation_id": "4-3-3"}, headers=headers_a)
        await client.put(f"/api/v1/rooms/{code}/lobby", json={"formation_id": "4-4-2"}, headers=headers_b)

        state = await client.post(f"/api/v1/rooms/{code}/start", headers=headers_a)
        assert state.status_code == 200
        data = state.json()
        assert data["room"]["status"] == "drafting"
        assert data["room"]["spin_revealed"] is False
        assert data["current_spin"] is None
        assert data["available_players"] == []

        active_id = data["active_room_player_id"]
        headers = headers_a if active_id == a["room_player_id"] else headers_b

        spin = await client.post(f"/api/v1/rooms/{code}/draft/spin", headers=headers)
        assert spin.status_code == 200
        spin_data = spin.json()
        assert spin_data["room"]["spin_revealed"] is True
        assert spin_data["current_spin"] is not None
        assert len(spin_data["available_players"]) > 0
        first_spin = spin_data["current_spin"]

        player = spin_data["available_players"][0]
        formation = "4-3-3" if active_id == a["room_player_id"] else "4-4-2"
        slots = (await client.get("/api/v1/formations")).json()["formations"]
        slot = next(f for f in slots if f["id"] == formation)["slots"][0]["slot_id"]

        pick = await client.post(
            f"/api/v1/rooms/{code}/draft/pick",
            json={"player_id": player["id"], "slot_id": slot},
            headers=headers,
        )
        assert pick.status_code == 200
        after_pick = pick.json()
        assert after_pick["current_spin"] == first_spin
        assert after_pick["room"]["spin_revealed"] is True

        second_active = after_pick["active_room_player_id"]
        headers2 = headers_a if second_active == a["room_player_id"] else headers_b
        pick2 = await client.post(
            f"/api/v1/rooms/{code}/draft/pick",
            json={"player_id": after_pick["available_players"][0]["id"], "slot_id": slot},
            headers=headers2,
        )
        assert pick2.status_code == 200
        round2 = pick2.json()
        assert round2["room"]["spin_revealed"] is False
        assert round2["current_spin"] is None

        assert all(p["id"] != player["id"] for p in after_pick["available_players"])
