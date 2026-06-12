"""Run versioned SQL migrations against Supabase Postgres."""

from __future__ import annotations

from pathlib import Path

from lib.db_url import resolve_database_url

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

MIGRATIONS_TABLE_SQL = """
create table if not exists schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);
"""


def _connect():
    db_url = resolve_database_url()
    if not db_url:
        raise RuntimeError(
            "Need DATABASE_URL or SUPABASE_DB_PASSWORD in data/.env to run migrations"
        )

    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("pip install psycopg2-binary") from exc

    return psycopg2.connect(db_url)


def _migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        raise RuntimeError(f"Migrations directory not found: {MIGRATIONS_DIR}")
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _applied_versions(cur) -> set[str]:
    cur.execute("select version from schema_migrations")
    return {row[0] for row in cur.fetchall()}


def _bootstrap_manual_schema(cur, files: list[Path], applied: set[str]) -> set[str]:
    """If schema was created manually, record the initial migration as applied."""
    if applied or not files:
        return applied

    cur.execute(
        """
        select exists (
          select 1
          from information_schema.tables
          where table_schema = 'public' and table_name = 'clubs'
        )
        """
    )
    if not cur.fetchone()[0]:
        return applied

    version = files[0].stem
    cur.execute(
        "insert into schema_migrations (version) values (%s) on conflict do nothing",
        (version,),
    )
    print(f"Detected existing schema — recorded migration {version} as applied.")
    applied.add(version)
    return applied


def run_migrations() -> list[str]:
    """Apply pending migrations. Returns versions applied this run."""
    files = _migration_files()
    if not files:
        print("No migration files found.")
        return []

    conn = _connect()
    applied_now: list[str] = []
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(MIGRATIONS_TABLE_SQL)
            applied = _applied_versions(cur)
            applied = _bootstrap_manual_schema(cur, files, applied)
            conn.commit()

            for path in files:
                version = path.stem
                if version in applied:
                    continue

                sql = path.read_text(encoding="utf-8")
                print(f"Applying migration {version}...")
                try:
                    cur.execute(sql)
                    cur.execute(
                        "insert into schema_migrations (version) values (%s)",
                        (version,),
                    )
                    conn.commit()
                    applied_now.append(version)
                    print(f"  OK {version}")
                except Exception:
                    conn.rollback()
                    raise
    finally:
        conn.close()

    if not applied_now:
        print("Database is up to date — no pending migrations.")
    else:
        print(f"Applied {len(applied_now)} migration(s).")

    return applied_now
