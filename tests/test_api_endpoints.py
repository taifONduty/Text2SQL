"""
Lightweight tests for FastAPI endpoints with dependency overrides.
"""

from fastapi.testclient import TestClient

from src.api import app, get_engine
from src.history import query_history


class DummyEngine:
    def query(self, question: str, execute: bool = True, max_retries: int = 2):
        return {
            "question": question,
            "sql_query": "SELECT 1;",
            "results": [{"value": 1}] if execute else None,
            "columns": ["value"] if execute else None,
            "row_count": 1 if execute else 0,
            "execution_time": 0.01 if execute else None,
            "error": None,
            "metadata": {"cache_hit": False},
        }


class DummyDatabaseManager:
    def __init__(self, *args, **kwargs):
        pass

    def explain_query(self, sql_query: str, analyze: bool = False):
        return {"plan": {"Node Type": "Seq Scan", "Relation Name": "orders"}, "insights": ["test insight"]}

    def get_performance_metrics(self):
        return {
            "database_stats": {"numbackends": 1},
            "session_states": [{"state": "active", "sessions": 2}],
        }

    def test_connection(self):
        return True


client = TestClient(app)
app.dependency_overrides[get_engine] = lambda: DummyEngine()


def test_query_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.DatabaseManager", DummyDatabaseManager)
    response = client.post("/v1/query", json={"question": "Ping?", "execute": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sql_query"] == "SELECT 1;"


def test_explain_endpoint(monkeypatch):
    monkeypatch.setattr("src.api.DatabaseManager", DummyDatabaseManager)
    response = client.post("/v1/explain", json={"sql_query": "SELECT 1;"})
    assert response.status_code == 200
    assert response.json()["insights"] == ["test insight"]


def test_history_endpoints(monkeypatch):
    monkeypatch.setattr("src.api.DatabaseManager", DummyDatabaseManager)
    query_history.record(
        question="Test?",
        sql_query="SELECT 1;",
        success=True,
        row_count=1,
        execution_time=0.01,
        cached=False,
        error=None,
    )

    response = client.get("/history/recent")
    assert response.status_code == 200
    assert len(response.json()) >= 1

    response = client.get("/history/top")
    assert response.status_code == 200
    assert response.json()[0]["question"] == "Test?"


def test_metrics_and_dashboard(monkeypatch):
    monkeypatch.setattr("src.api.DatabaseManager", DummyDatabaseManager)
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    data = metrics_response.json()
    assert data["database_stats"]["numbackends"] == 1

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert "Database Performance Dashboard" in dashboard_response.text
