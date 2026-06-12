import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.types import UUIDList

ROOM_STATUS = Enum(
    "lobby",
    "drafting",
    "simulating",
    "complete",
    "abandoned",
    name="room_status",
    create_type=False,
)

def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    primary_position: Mapped[str] = mapped_column(String, nullable=False)
    secondary_positions: Mapped[list] = mapped_column(JSON, default=list)
    base_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    attack: Mapped[int | None] = mapped_column(Integer)
    midfield: Mapped[int | None] = mapped_column(Integer)
    defence: Mapped[int | None] = mapped_column(Integer)
    goalkeeper: Mapped[int | None] = mapped_column(Integer)
    consistency: Mapped[int] = mapped_column(Integer, default=75)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlayerEra(Base):
    __tablename__ = "player_eras"
    __table_args__ = (UniqueConstraint("player_id", "club_id", "era"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.id"), nullable=False)
    club_id: Mapped[str] = mapped_column(String, ForeignKey("clubs.id"), nullable=False)
    era: Mapped[str] = mapped_column(String, nullable=False)
    primary_position: Mapped[str | None] = mapped_column(String)
    secondary_positions: Mapped[list] = mapped_column(JSON, default=list)
    rating_modifier: Mapped[int] = mapped_column(Integer, default=0)
    include: Mapped[bool] = mapped_column(Boolean, default=True)


class PositionFit(Base):
    __tablename__ = "position_fits"
    __table_args__ = (UniqueConstraint("player_id", "position"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.id"), nullable=False)
    position: Mapped[str] = mapped_column(String, nullable=False)
    fit: Mapped[int] = mapped_column(Integer, nullable=False)


class TeamEraPool(Base):
    __tablename__ = "team_era_pools"
    __table_args__ = (UniqueConstraint("club_id", "era"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    club_id: Mapped[str] = mapped_column(String, ForeignKey("clubs.id"), nullable=False)
    era: Mapped[str] = mapped_column(String, nullable=False)
    spin_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    min_eligible_players: Mapped[int] = mapped_column(Integer, default=5)


class Formation(Base):
    __tablename__ = "formations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slots: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(ROOM_STATUS, default="lobby")
    host_room_player_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    max_players: Mapped[int] = mapped_column(Integer, default=6)
    total_rounds: Mapped[int] = mapped_column(Integer, default=11)
    pick_timer_seconds: Mapped[int] = mapped_column(Integer, default=30)
    current_pick_index: Mapped[int] = mapped_column(Integer, default=0)
    current_spin_club_id: Mapped[str | None] = mapped_column(String, ForeignKey("clubs.id"))
    current_spin_era: Mapped[str | None] = mapped_column(String)
    spin_revealed: Mapped[bool] = mapped_column(Boolean, default=False)
    current_pick_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    draft_order: Mapped[list] = mapped_column(UUIDList, default=list)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    simulation_seed: Mapped[str | None] = mapped_column(String)
    simulation_version: Mapped[str | None] = mapped_column(String)
    draft_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    players: Mapped[list["RoomPlayer"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    picks: Mapped[list["DraftPick"]] = relationship(back_populates="room", cascade="all, delete-orphan")


class RoomPlayer(Base):
    __tablename__ = "room_players"
    __table_args__ = (UniqueConstraint("room_id", "nickname"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rooms.id"), nullable=False)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    team_name: Mapped[str | None] = mapped_column(String)
    formation_id: Mapped[str | None] = mapped_column(String, ForeignKey("formations.id"))
    client_token_hash: Mapped[str] = mapped_column(String, nullable=False)
    draft_position: Mapped[int | None] = mapped_column(Integer)
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_difficulty: Mapped[str | None] = mapped_column(String)
    normal_rerolls_left: Mapped[int] = mapped_column(Integer, default=1)
    late_lifelines_left: Mapped[int] = mapped_column(Integer, default=1)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship(back_populates="players")
    picks: Mapped[list["DraftPick"]] = relationship(back_populates="room_player")


class DraftPick(Base):
    __tablename__ = "draft_picks"
    __table_args__ = (
        UniqueConstraint("room_id", "pick_index"),
        UniqueConstraint("room_id", "player_id"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rooms.id"), nullable=False)
    room_player_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("room_players.id"), nullable=False)
    pick_index: Mapped[int] = mapped_column(Integer, nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    spin_club_id: Mapped[str] = mapped_column(String, ForeignKey("clubs.id"), nullable=False)
    spin_era: Mapped[str] = mapped_column(String, nullable=False)
    player_id: Mapped[str] = mapped_column(String, ForeignKey("players.id"), nullable=False)
    slot_id: Mapped[str] = mapped_column(String, nullable=False)
    player_era_id: Mapped[str | None] = mapped_column(String, ForeignKey("player_eras.id"))
    draft_value: Mapped[int] = mapped_column(Integer, nullable=False)
    was_auto_pick: Mapped[bool] = mapped_column(Boolean, default=False)
    used_reroll: Mapped[bool] = mapped_column(Boolean, default=False)
    picked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship(back_populates="picks")
    room_player: Mapped["RoomPlayer"] = relationship(back_populates="picks")


class RerollEvent(Base):
    __tablename__ = "reroll_events"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rooms.id"), nullable=False)
    room_player_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("room_players.id"), nullable=False)
    pick_index: Mapped[int] = mapped_column(Integer, nullable=False)
    old_club_id: Mapped[str | None] = mapped_column(String, ForeignKey("clubs.id"))
    old_era: Mapped[str | None] = mapped_column(String)
    new_club_id: Mapped[str | None] = mapped_column(String, ForeignKey("clubs.id"))
    new_era: Mapped[str | None] = mapped_column(String)
    reroll_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeamEvaluation(Base):
    __tablename__ = "team_evaluations"
    __table_args__ = (UniqueConstraint("room_id", "room_player_id"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rooms.id"), nullable=False)
    room_player_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("room_players.id"), nullable=False)
    formation_id: Mapped[str] = mapped_column(String, ForeignKey("formations.id"), nullable=False)
    internal_team_strength: Mapped[float | None] = mapped_column(Numeric)
    internal_attack_score: Mapped[float | None] = mapped_column(Numeric)
    internal_midfield_score: Mapped[float | None] = mapped_column(Numeric)
    internal_defence_score: Mapped[float | None] = mapped_column(Numeric)
    internal_gk_score: Mapped[float | None] = mapped_column(Numeric)
    internal_balance_score: Mapped[float | None] = mapped_column(Numeric)


class SimulationResult(Base):
    __tablename__ = "simulation_results"
    __table_args__ = (UniqueConstraint("room_id", "room_player_id"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    room_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("rooms.id"), nullable=False)
    room_player_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("room_players.id"), nullable=False)
    internal_team_strength: Mapped[float] = mapped_column(Numeric, nullable=False)
    internal_season_strength: Mapped[float] = mapped_column(Numeric, nullable=False)
    internal_expected_points: Mapped[int] = mapped_column(Integer, nullable=False)
    internal_points: Mapped[int] = mapped_column(Integer, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False)
    draws: Mapped[int] = mapped_column(Integer, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, nullable=False)


def player_to_public(player: Player, spin_club_id: str | None = None, spin_era: str | None = None) -> dict[str, Any]:
    data = {
        "id": player.id,
        "name": player.name,
        "primary_position": player.primary_position,
        "secondary_positions": player.secondary_positions or [],
    }
    if spin_club_id and spin_era:
        data["spin"] = {"club_id": spin_club_id, "era": spin_era}
    return data
