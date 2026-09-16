"""
Audit log: every question, the SQL that was generated and actually run,
execution metrics, and outcome. SQLite file, separate from the analytical
data — this is operational logging, not part of the gold schema.
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    session_id TEXT,
    username TEXT,
    role TEXT,
    question TEXT,
    domains TEXT,
    generated_sql TEXT,
    validated_sql TEXT,
    status TEXT NOT NULL,
    error TEXT,
    row_count INTEGER,
    duration_ms INTEGER,
    answer TEXT
)
"""


@contextmanager
def _conn():
    c = sqlite3.connect(settings.LOG_DB_PATH)
    try:
        c.execute(_SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


@dataclass
class LogEntry:
    session_id: str
    username: str
    role: str
    question: str
    domains: list[str] = field(default_factory=list)
    generated_sql: str = ""
    validated_sql: str = ""
    status: str = "error"  # "success" | "validation_error" | "execution_error" | "no_query"
    error: str = ""
    row_count: int = 0
    duration_ms: int = 0
    answer: str = ""


def log(entry: LogEntry) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO query_log
               (timestamp, session_id, username, role, question, domains, generated_sql,
                validated_sql, status, error, row_count, duration_ms, answer)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(), entry.session_id, entry.username, entry.role, entry.question,
                json.dumps(entry.domains), entry.generated_sql, entry.validated_sql,
                entry.status, entry.error, entry.row_count, entry.duration_ms, entry.answer,
            ),
        )


def recent(limit: int = 50) -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM query_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
