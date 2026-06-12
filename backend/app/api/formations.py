from fastapi import APIRouter

from app.core.formations import FORMATIONS

router = APIRouter(prefix="/formations", tags=["formations"])


@router.get("")
async def list_formations():
    return {
        "formations": [
            {"id": fid, "name": data["name"], "slots": data["slots"]}
            for fid, data in FORMATIONS.items()
        ]
    }
