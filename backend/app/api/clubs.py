from fastapi import APIRouter
from sqlalchemy import select

from app.db.database import get_session
from app.db.models import Club
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

router = APIRouter(prefix="/clubs", tags=["clubs"])


@router.get("")
async def list_clubs(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Club).where(Club.is_active == True).order_by(Club.name))).scalars().all()
    return {
        "clubs": [
            {"id": c.id, "name": c.name, "short_name": c.short_name or c.name}
            for c in rows
        ]
    }
