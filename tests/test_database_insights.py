"""
Unit tests for database execution plan insights.
"""

from src.database import DatabaseManager


def test_generate_plan_insights_seq_scan():
    manager = DatabaseManager(connection_url="postgresql://user:pass@localhost:5432/db")
    plan = {
        "Node Type": "Seq Scan",
        "Relation Name": "orders",
        "Plans": [
            {
                "Node Type": "Index Scan",
                "Relation Name": "customers",
            }
        ],
    }

    suggestions = manager._generate_plan_insights(plan)
    assert any("orders" in suggestion for suggestion in suggestions)
