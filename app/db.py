import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import DATABASE_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


def now():
    return datetime.now(timezone.utc).isoformat()


def _postgres_url():
    # Render sometimes supplies postgres://; psycopg accepts postgresql://.
    if DATABASE_URL.startswith("postgres://"):
        return DATABASE_URL.replace("postgres://", "postgresql://", 1)
    return DATABASE_URL


class PostgresConnection:
    """Small compatibility wrapper for existing SQLite-style '?' queries."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=()):
        query = query.replace("?", "%s")
        return self.connection.execute(query, params)

    def commit(self):
        self.connection.commit()


@contextmanager
def connect():
    if USE_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        con = psycopg.connect(_postgres_url(), row_factory=dict_row)
        try:
            yield PostgresConnection(con)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    else:
        Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(DATABASE_PATH), timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def init_db():
    if USE_POSTGRES:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS novels (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                idea TEXT NOT NULL,
                genre TEXT NOT NULL DEFAULT 'mystery',
                target_chapters INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                next_chapter INTEGER NOT NULL DEFAULT 1,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chapters (
                id BIGSERIAL PRIMARY KEY,
                novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
                chapter_no INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                created_at TEXT NOT NULL,
                UNIQUE(novel_id, chapter_no)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS requests (
                idempotency_key TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                chapter_no INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error TEXT
            )
            """,
        ]
        with connect() as con:
            for statement in statements:
                con.execute(statement)
    else:
        Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
        with connect() as con:
            con.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS novels (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                idea TEXT NOT NULL,
                genre TEXT NOT NULL DEFAULT 'mystery',
                target_chapters INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                next_chapter INTEGER NOT NULL DEFAULT 1,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
                chapter_no INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                created_at TEXT NOT NULL,
                UNIQUE(novel_id, chapter_no)
            );
            CREATE TABLE IF NOT EXISTS requests (
                idempotency_key TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                chapter_no INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error TEXT
            );
            """)


def rowdict(row):
    return dict(row) if row else None


def novel_with_chapters(novel_id):
    with connect() as con:
        n = con.execute(
            "SELECT * FROM novels WHERE id=?", (novel_id,)
        ).fetchone()
        if not n:
            return None

        chapters = con.execute(
            """
            SELECT chapter_no,title,content,status,created_at
            FROM chapters
            WHERE novel_id=?
            ORDER BY chapter_no
            """,
            (novel_id,),
        ).fetchall()

        out = dict(n)
        out["chapters"] = [dict(c) for c in chapters]
        out["completed_chapters"] = len(chapters)
        out["progress_percent"] = round(
            len(chapters) * 100 / max(1, out["target_chapters"]), 1
        )
        return out
