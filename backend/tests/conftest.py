import os

os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
import app.db.database as db_module
from tests.seed import seed_all


@pytest.fixture(autouse=True)
async def setup_db(monkeypatch):
    test_url = "sqlite+aiosqlite:///:memory:"
    monkeypatch.setattr(settings, "database_url", test_url)

    new_engine = create_async_engine(test_url, echo=False)
    db_module.engine = new_engine
    db_module.SessionLocal = async_sessionmaker(new_engine, expire_on_commit=False)

    async with new_engine.begin() as conn:
        from app.db.models import Base

        await conn.run_sync(Base.metadata.create_all)

    async with db_module.SessionLocal() as session:
        await seed_all(session)


@pytest.fixture
def transport():
    return ASGITransport(app=__import__("app.main", fromlist=["app"]).app)
