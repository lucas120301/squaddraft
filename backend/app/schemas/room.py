from pydantic import BaseModel, Field


class CreateRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)
    max_players: int = Field(default=6, ge=2, le=6)


class JoinRoomRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=24)


class LobbyUpdateRequest(BaseModel):
    formation_id: str | None = None
    team_name: str | None = None


class PickRequest(BaseModel):
    player_id: str
    slot_id: str


class RerollRequest(BaseModel):
    reroll_type: str = "normal"


class LifelineChooseRequest(BaseModel):
    club_id: str
    era: str
