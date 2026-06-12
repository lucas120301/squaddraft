from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.formations import fit_label, get_formation_slots
from app.db.database import get_session
from app.db.models import Room, RoomPlayer
from app.api.rooms import get_authenticated_player
from app.services.room_service import get_player_fits

router = APIRouter(prefix="/rooms", tags=["draft"])


@router.get("/{code}/draft/fits")
async def api_slot_fits(
    player_id: str = Query(...),
    slot_ids: str = Query(...),
    auth: tuple[Room, RoomPlayer] = Depends(get_authenticated_player),
    session: AsyncSession = Depends(get_session),
):
    room, player = auth
    if not player.formation_id:
        return {"fits": []}
    slots = get_formation_slots(player.formation_id)
    slot_map = {s["slot_id"]: s for s in slots}
    result = []
    for sid in slot_ids.split(","):
        sid = sid.strip()
        slot = slot_map.get(sid)
        if not slot:
            continue
        fits = await get_player_fits(
            session,
            player_id,
            [slot["position"]],
            club_id=room.current_spin_club_id,
            era=room.current_spin_era,
        )
        fit = fits.get(slot["position"], 0)
        result.append({"slot_id": sid, "position": slot["position"], "label": fit_label(fit), "can_play": fit > 0})
    return {"fits": result}
