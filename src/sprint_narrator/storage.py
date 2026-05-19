import json
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".config" / "sprint-narrator" / "history.db"


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the summaries table if it doesn't exist."""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_range TEXT NOT NULL,
            sources TEXT NOT NULL,
            narrative TEXT NOT NULL,
            raw_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_summary(
    date_range: str, sources: list[str], narrative: str, raw_data: dict | None = None
) -> None:
    """Archive a sprint summary."""
    init_db()
    conn = _get_connection()
    conn.execute(
        "INSERT INTO summaries (date_range, sources, narrative, raw_data) VALUES (?, ?, ?, ?)",
        (date_range, ", ".join(sources), narrative, json.dumps(raw_data) if raw_data else None),
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 10) -> list[dict]:
    """Retrieve past sprint summaries."""
    init_db()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT date_range, sources, narrative, created_at FROM summaries ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
