import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .config import DATABASE_PATH

def now():
    return datetime.now(timezone.utc).isoformat()

def init_db():
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
        con.commit()

@contextmanager
def connect():
    con = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def rowdict(row):
    return dict(row) if row else None

def novel_with_chapters(novel_id):
    with connect() as con:
        n = con.execute("SELECT * FROM novels WHERE id=?", (novel_id,)).fetchone()
        if not n:
            return None
        chapters = con.execute(
            "SELECT chapter_no,title,content,status,created_at FROM chapters WHERE novel_id=? ORDER BY chapter_no",
            (novel_id,)
        ).fetchall()
        out = dict(n)
        out["chapters"] = [dict(c) for c in chapters]
        out["completed_chapters"] = len(chapters)
        out["progress_percent"] = round(len(chapters) * 100 / max(1, out["target_chapters"]), 1)
        return out
