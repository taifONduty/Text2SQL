"""
Tests for query history manager persistence and insights.
"""

from pathlib import Path

from src.history import QueryHistoryManager


def test_history_record_and_lookup(tmp_path):
    history_path = tmp_path / "history.db"
    manager = QueryHistoryManager(db_path=str(history_path))

    manager.record(
        question="What is the revenue?",
        sql_query="SELECT * FROM revenue;",
        success=True,
        row_count=10,
        execution_time=0.5,
        cached=False,
        error=None,
    )

    lookup = manager.lookup("What is the revenue?")
    assert lookup is not None
    assert lookup["sql_query"] == "SELECT * FROM revenue;"

    top = manager.top_questions(limit=1)
    assert top == [("What is the revenue?", 1)]

    avg_time = manager.average_execution_time()
    assert avg_time == 0.5

    recent = manager.recent(limit=5)
    assert len(recent) == 1
