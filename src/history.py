"""
Persistent query history tracking with lightweight learning insights.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import settings


logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    sql_query TEXT,
    success INTEGER NOT NULL,
    row_count INTEGER,
    execution_time REAL,
    cached INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_history_question ON query_history(question);
"""


class QueryHistoryManager:
    """Stores query executions and provides simple learning aids."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path or settings.history_store_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(
        self,
        question: str,
        sql_query: Optional[str],
        success: bool,
        row_count: int,
        execution_time: Optional[float],
        cached: bool,
        error: Optional[str],
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO query_history (
                    question, sql_query, success, row_count, execution_time, cached, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.strip(),
                    sql_query,
                    1 if success else 0,
                    row_count,
                    execution_time,
                    1 if cached else 0,
                    error,
                ),
            )
            conn.commit()

    def lookup(self, question: str) -> Optional[Dict[str, Any]]:
        """Return the most recent successful entry for the same question."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT sql_query, row_count, execution_time, cached, created_at
                FROM query_history
                WHERE question = ?
                  AND success = 1
                  AND sql_query IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (question.strip(),),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT question, sql_query, success, row_count, execution_time, cached, created_at
                FROM query_history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def top_questions(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Return most frequently asked questions."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT question, COUNT(*) AS frequency
                FROM query_history
                GROUP BY question
                ORDER BY frequency DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [(row["question"], row["frequency"]) for row in cursor.fetchall()]

    def average_execution_time(self) -> Optional[float]:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT AVG(execution_time) AS avg_time
                FROM query_history
                WHERE execution_time IS NOT NULL
                """,
            )
            row = cursor.fetchone()
            return row["avg_time"] if row and row["avg_time"] is not None else None

    def clear(self) -> None:
        """Remove all history entries (primarily for testing)."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM query_history")
            conn.commit()


# Global instance for convenience
query_history = QueryHistoryManager()
