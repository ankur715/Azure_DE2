"""
In-memory conversation context, keyed by session id.

Deliberately simple (a dict, lost on restart) — this is a demo. For
multi-instance deployment, swap this for a shared store (Redis, a DB table)
without changing the interface used by app.py.
"""
import threading
import time
from dataclasses import dataclass, field

_MAX_TURNS_KEPT = 6
_SESSION_TTL_SECONDS = 60 * 60


@dataclass
class Turn:
    question: str
    sql: str
    answer: str
    timestamp: float = field(default_factory=time.time)


class ConversationStore:
    def __init__(self):
        self._sessions: dict[str, list[Turn]] = {}
        self._lock = threading.Lock()

    def add_turn(self, session_id: str, question: str, sql: str, answer: str) -> None:
        with self._lock:
            turns = self._sessions.setdefault(session_id, [])
            turns.append(Turn(question=question, sql=sql, answer=answer))
            self._sessions[session_id] = turns[-_MAX_TURNS_KEPT:]

    def context_text(self, session_id: str) -> str:
        with self._lock:
            turns = self._sessions.get(session_id, [])
            now = time.time()
            turns = [t for t in turns if now - t.timestamp < _SESSION_TTL_SECONDS]
        if not turns:
            return ""
        lines = []
        for t in turns:
            lines.append(f"Q: {t.question}\nSQL: {t.sql}\nA: {t.answer}")
        return "\n\n".join(lines)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


store = ConversationStore()
