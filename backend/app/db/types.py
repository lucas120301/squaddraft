"""Cross-dialect column types for Postgres (Supabase) and SQLite (tests)."""

from __future__ import annotations

from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator


class UUIDList(TypeDecorator):
    """Postgres uuid[] in production, JSON array in SQLite tests."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Uuid(as_uuid=False)))
        return dialect.type_descriptor(JSON())
