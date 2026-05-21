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
        "SELECT date_range, sources, narrative, created_at"
        " FROM summaries ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_trends_data(limit: int = 5) -> list[dict]:
    """Retrieve parsed raw_data from recent summaries for trend analysis.

    Skips entries with missing or malformed raw_data.
    Returns oldest-first for chronological trend display.
    """
    init_db()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT date_range, raw_data, created_at FROM summaries ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    results: list[dict] = []
    for row in rows:
        raw = row["raw_data"]
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        results.append(
            {
                "date_range": row["date_range"],
                "created_at": row["created_at"],
                **data,
            }
        )

    # Return oldest-first for chronological display
    results.reverse()
    return results
