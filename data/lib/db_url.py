"""Resolve Supabase Postgres connection strings from env vars."""

from __future__ import annotations

import os
import re
from urllib.parse import quote_plus


def project_ref_from_url(supabase_url: str) -> str | None:
    match = re.search(r"https://([^.]+)\.supabase\.co", supabase_url.strip())
    return match.group(1) if match else None


def resolve_database_url() -> str | None:
    """Return a Postgres URI for schema migrations.

    Accepts either a full DATABASE_URL or SUPABASE_URL + SUPABASE_DB_PASSWORD.
    """
    direct = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if direct:
        return direct

    password = os.environ.get("SUPABASE_DB_PASSWORD")
    ref = project_ref_from_url(os.environ.get("SUPABASE_URL", ""))
    if not password or not ref:
        return None

    return (
        f"postgresql://postgres:{quote_plus(password)}"
        f"@db.{ref}.supabase.co:5432/postgres"
    )
