"""
FastAPI application exposing the Text2SQL analytics capabilities over HTTP.
"""

from __future__ import annotations

import time
import logging
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .cache import query_cache
from .database import DatabaseManager
from .history import query_history
from .text2sql_engine import Text2SQLEngine


logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    """Incoming payload for the query endpoint."""

    question: str = Field(..., min_length=3, description="Natural language analytics question.")
    execute: bool = Field(True, description="Execute the generated SQL against PostgreSQL.")
    max_retries: int = Field(
        2,
        ge=0,
        le=5,
        description="Maximum retries for regenerating SQL when validation fails.",
    )


class QueryResponse(BaseModel):
    """Response payload for the query endpoint."""

    question: str
    sql_query: Optional[str]
    results: Optional[List[Dict[str, Any]]]
    columns: Optional[List[str]]
    row_count: int = 0
    execution_time: Optional[float]
    error: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Response payload for the health endpoint."""

    status: str
    database: bool
    engine_ready: bool


class ExplainRequest(BaseModel):
    """Payload for execution plan analysis."""

    sql_query: str = Field(..., description="Validated SELECT query to analyze.")
    analyze: bool = Field(
        False,
        description="Run EXPLAIN ANALYZE (executes the query) when true.",
    )


class ExplainResponse(BaseModel):
    plan: Dict[str, Any]
    insights: List[str]


class HistoryEntry(BaseModel):
    question: str
    sql_query: Optional[str]
    success: bool
    row_count: int
    execution_time: Optional[float]
    cached: bool
    created_at: str


class MetricsResponse(BaseModel):
    database_stats: Dict[str, Any] = Field(default_factory=dict)
    session_states: List[Dict[str, Any]] = Field(default_factory=list)


app = FastAPI(
    title="Text2SQL Analytics API",
    description="Convert natural language questions to normalized SQL queries and results.",
    version=__version__,
)

_engine: Optional[Text2SQLEngine] = None
_schema_cache: Optional[Dict[str, Any]] = None
_startup_lock = Lock()


def get_engine() -> Text2SQLEngine:
    """Provide an initialized Text2SQLEngine instance."""
    if _engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text2SQL engine not initialized yet.",
        )
    return _engine


@app.on_event("startup")
def bootstrap_engine() -> None:
    """Initialize Text2SQLEngine and cache schema context once."""
    global _engine, _schema_cache

    if _engine is not None:
        return

    with _startup_lock:
        if _engine is not None:
            return

        try:
            db_manager = DatabaseManager(readonly=True)
            schema_info = db_manager.get_schema_info()

            engine = Text2SQLEngine()
            engine.set_schema_context(schema_info)

            _schema_cache = schema_info
            _engine = engine
            logger.info("FastAPI startup complete: schema loaded (%s tables)", len(schema_info))
        except Exception as exc:
            logger.exception("Failed to initialize Text2SQL engine: %s", exc)
            raise


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Basic health endpoint reporting engine readiness and database connectivity."""
    db_ok = False
    try:
        DatabaseManager(readonly=True).test_connection()
        db_ok = True
    except Exception as exc:  # pragma: no cover - visibility only
        logger.warning("Health check database connection failed: %s", exc)

    return HealthResponse(
        status="ok" if db_ok and _engine is not None else "degraded",
        database=db_ok,
        engine_ready=_engine is not None,
    )


@app.get("/schema", response_model=Dict[str, Any], tags=["Metadata"])
def get_schema() -> Dict[str, Any]:
    """Return cached schema information provided to the LLM."""
    if _schema_cache is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Schema not initialized."
        )
    return _schema_cache


@app.post("/v1/query", response_model=QueryResponse, tags=["Query"])
def execute_question(request: QueryRequest, engine: Text2SQLEngine = Depends(get_engine)) -> QueryResponse:
    """Convert a question to SQL, optionally execute it, and return results."""
    try:
        result = engine.query(
            question=request.question,
            execute=request.execute,
            max_retries=request.max_retries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error processing question via API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error processing question.",
        ) from exc

    return QueryResponse(**result)


@app.post("/v1/explain", response_model=ExplainResponse, tags=["Query"])
def explain_sql(request: ExplainRequest) -> ExplainResponse:
    """Return execution plan and heuristic insights for a SQL statement."""
    manager = DatabaseManager(readonly=True)
    try:
        plan = manager.explain_query(request.sql_query, analyze=request.analyze)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to generate execution plan: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate execution plan.",
        ) from exc

    return ExplainResponse(**plan)


@app.get("/history/recent", response_model=List[HistoryEntry], tags=["History"])
def recent_history(limit: int = 20) -> List[HistoryEntry]:
    """Return the most recent query executions."""
    records = query_history.recent(limit=limit)
    serialized: List[HistoryEntry] = []
    for record in records:
        serialized.append(
            HistoryEntry(
                question=record["question"],
                sql_query=record.get("sql_query"),
                success=bool(record.get("success", 0)),
                row_count=record.get("row_count") or 0,
                execution_time=record.get("execution_time"),
                cached=bool(record.get("cached", 0)),
                created_at=record.get("created_at"),
            )
        )
    return serialized


class TopQuestion(BaseModel):
    question: str
    frequency: int


@app.get("/history/top", response_model=List[TopQuestion], tags=["History"])
def top_questions(limit: int = 5) -> List[TopQuestion]:
    """Return most frequently asked questions."""
    top = query_history.top_questions(limit=limit)
    return [TopQuestion(question=q, frequency=f) for q, f in top]


@app.get("/metrics", response_model=MetricsResponse, tags=["Monitoring"])
def metrics() -> MetricsResponse:
    """Expose raw performance metrics for programmatic consumption."""
    manager = DatabaseManager(readonly=True)
    stats = manager.get_performance_metrics()
    return MetricsResponse(
        database_stats=stats.get("database_stats", {}),
        session_states=stats.get("session_states", []),
    )


def _render_dashboard_html(metrics: MetricsResponse) -> str:
    db_stats = metrics.database_stats
    session_states = metrics.session_states
    top = query_history.top_questions(limit=5)
    avg_time = query_history.average_execution_time()

    session_rows = "".join(
        f"<tr><td>{row.get('state', 'unknown')}</td><td>{row.get('sessions', 0)}</td></tr>"
        for row in session_states
    )
    top_rows = "".join(f"<li>{question} ({freq} executions)</li>" for question, freq in top) or "<li>No data yet</li>"

    avg_time_display = f"{avg_time:.3f}s" if avg_time is not None else "N/A"

    return f"""
    <html>
        <head>
            <title>Text2SQL Performance Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; background-color: #f5f5f5; }}
                h1 {{ color: #333; }}
                .card {{ background: #fff; padding: 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
                th {{ background-color: #fafafa; }}
            </style>
        </head>
        <body>
            <h1>Database Performance Dashboard</h1>
            <div class="card">
                <h2>Cache Status</h2>
                <p>Backend: <strong>{query_cache.backend()}</strong></p>
            </div>
            <div class="card">
                <h2>Database Statistics</h2>
                <table>
                    <tbody>
                        {"".join(f"<tr><th>{key}</th><td>{value}</td></tr>" for key, value in db_stats.items()) or "<tr><td colspan='2'>No data</td></tr>"}
                    </tbody>
                </table>
            </div>
            <div class="card">
                <h2>Session States</h2>
                <table>
                    <thead><tr><th>State</th><th>Sessions</th></tr></thead>
                    <tbody>{session_rows or "<tr><td colspan='2'>No active sessions</td></tr>"}</tbody>
                </table>
            </div>
            <div class="card">
                <h2>Query Insights</h2>
                <p>Average Execution Time: <strong>{avg_time_display}</strong></p>
                <p>Top Questions:</p>
                <ul>{top_rows}</ul>
            </div>
        </body>
    </html>
    """


@app.get("/dashboard", response_class=HTMLResponse, tags=["Monitoring"])
def dashboard() -> HTMLResponse:
    """Human-friendly dashboard summarizing performance metrics."""
    metrics_payload = metrics()
    html = _render_dashboard_html(metrics_payload)
    return HTMLResponse(content=html)
