import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_join_and_lobby():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/rooms", json={"nickname": "Lucas"})
        assert r.status_code == 200
        data = r.json()
        code = data["room_code"]

        r2 = await client.post(f"/api/v1/rooms/{code}/join", json={"nickname": "Maya"})
        assert r2.status_code == 200

        headers = {
            "X-Room-Player-Id": data["room_player_id"],
            "X-Client-Token": data["client_token"],
        }
        r3 = await client.put(
            f"/api/v1/rooms/{code}/lobby",
            json={"formation_id": "4-3-3", "team_name": "Lucas FC"},
            headers=headers,
        )
        assert r3.status_code == 200


@pytest.mark.asyncio
async def test_record_from_points_valid():
    from app.services.simulation_service import record_from_points

    wins, draws, losses = record_from_points(98)
    assert wins * 3 + draws == 98
    assert wins + draws + losses == 38


@pytest.mark.asyncio
async def test_hidden_data_not_in_room_state():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/rooms", json={"nickname": "Test"})
        code = r.json()["room_code"]
        state = await client.get(f"/api/v1/rooms/{code}")
        text = state.text.lower()
        assert "base_rating" not in text
        assert "draft_value" not in text
        assert "internal_" not in text
