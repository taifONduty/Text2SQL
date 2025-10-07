"""
Database connection and operations management.
Handles PostgreSQL connections with security and connection pooling.
"""

import json
import logging
import signal
from contextlib import contextmanager
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor

from .config import settings
from .query_validator import QueryValidator


logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Exception raised when query execution times out."""


def timeout_handler(signum, frame):
    """Signal handler for query timeout."""
    raise TimeoutException("Query execution timed out")


class DatabaseManager:
    """Manages PostgreSQL database connections and operations."""
    
    def __init__(self, connection_url: Optional[str] = None, readonly: bool = True):
        """
        Initialize database manager.
        
        Args:
            connection_url: Database connection URL (optional, uses settings if not provided)
            readonly: Whether to use read-only connection (default: True)
        """
        self.connection_url = connection_url or (
            settings.readonly_database_url if readonly else settings.database_url
        )
        self.readonly = readonly
        self.query_validator = QueryValidator()
        self.connection_pool: Optional[pool.SimpleConnectionPool] = None
        self.logger = logging.getLogger(__name__)
    
    def initialize_pool(self, minconn: int = 1, maxconn: int = 10):
        """
        Initialize connection pool.
        
        Args:
            minconn: Minimum number of connections
            maxconn: Maximum number of connections
        """
        try:
            self.connection_pool = pool.SimpleConnectionPool(
                minconn,
                maxconn,
                self.connection_url
            )
            self.logger.info("Connection pool initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection from the pool.
        
        Yields:
            Database connection
        """
        if not self.connection_pool:
            self.initialize_pool()
        
        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)
    
    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        timeout: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Execute a SQL query with timeout and validation.
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            timeout: Query timeout in seconds (default: from settings)
        
        Returns:
            Tuple of (results as list of dicts, column names)
        
        Raises:
            ValueError: If query validation fails
            TimeoutException: If query execution times out
            psycopg2.Error: For database errors
        """
        # Validate query
        is_valid, error_msg = self.query_validator.validate(query)
        if not is_valid:
            self.logger.error(f"Query validation failed: {error_msg}")
            raise ValueError(f"Invalid query: {error_msg}")
        
        # Sanitize query
        query = self.query_validator.sanitize(query)
        
        # Set timeout
        query_timeout = timeout or settings.query_timeout
        
        results = []
        columns = []
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    # Set statement timeout
                    cursor.execute(f"SET statement_timeout = {query_timeout * 1000}")
                    
                    # Execute query
                    self.logger.info(f"Executing query: {query[:100]}...")
                    cursor.execute(query, params)
                    
                    # Fetch results with row limit
                    rows = cursor.fetchmany(settings.max_result_rows)
                    
                    # Get column names
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        results = [dict(row) for row in rows]
                    
                    self.logger.info(f"Query executed successfully. Rows returned: {len(results)}")
                    
                except psycopg2.errors.QueryCanceled:
                    self.logger.error(f"Query timeout after {query_timeout} seconds")
                    raise TimeoutException(f"Query execution exceeded {query_timeout} seconds")

                except Exception as e:
                    self.logger.error(f"Query execution error: {e}")
                    raise
        
        return results, columns

    def explain_query(self, query: str, analyze: bool = False) -> Dict[str, Any]:
        """
        Generate execution plan for a validated query and provide simple insights.
        """
        is_valid, error_msg = self.query_validator.validate(query)
        if not is_valid:
            raise ValueError(f"Invalid query: {error_msg}")

        sanitized = self.query_validator.sanitize(query).rstrip(";")
        explain_clause = "EXPLAIN (FORMAT JSON{})".format(", ANALYZE" if analyze else "")
        explain_sql = f"{explain_clause} {sanitized}"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(explain_sql)
                plan_rows = cursor.fetchall()

        if not plan_rows:
            raise RuntimeError("Failed to obtain execution plan.")

        plan_json = plan_rows[0]["QUERY PLAN"]
        if isinstance(plan_json, str):
            plan_data = json.loads(plan_json)[0]
        else:
            plan_data = plan_json[0]

        return {
            "plan": plan_data,
            "insights": self._generate_plan_insights(plan_data),
        }

    def _generate_plan_insights(self, plan: Dict[str, Any]) -> List[str]:
        suggestions: List[str] = []

        def _traverse(node: Dict[str, Any]) -> None:
            node_type = node.get("Node Type")
            relation = node.get("Relation Name")

            if node_type == "Seq Scan" and relation:
                suggestions.append(f"Consider adding an index on table '{relation}' to avoid sequential scans.")

            if node.get("Actual Total Time") and node["Actual Total Time"] > 1000:
                suggestions.append(
                    f"Node '{node_type}' took {node['Actual Total Time']:.2f}ms. Investigate predicates and indexing."
                )

            if node.get("Plans"):
                for child in node["Plans"]:
                    _traverse(child)

        _traverse(plan)
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in seen:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
        return unique_suggestions
    
    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get database schema information.
        
        Returns:
            Dictionary with schema information
        """
        schema_query = """
        SELECT 
            t.table_name,
            array_agg(
                json_build_object(
                    'column_name', c.column_name,
                    'data_type', c.data_type,
                    'is_nullable', c.is_nullable
                ) ORDER BY c.ordinal_position
            ) as columns
        FROM information_schema.tables t
        JOIN information_schema.columns c 
            ON t.table_name = c.table_name
        WHERE t.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
        GROUP BY t.table_name
        ORDER BY t.table_name
        """
        
        # Use admin connection for schema queries
        admin_db = DatabaseManager(settings.admin_database_url, readonly=False)
        results, _ = admin_db.execute_query(schema_query)
        
        return {row['table_name']: row['columns'] for row in results}
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1;")
                    result = cursor.fetchone()
                    self.logger.info("Database connection test successful")
                    return result is not None
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            return False
    
    def close_pool(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
            except psycopg2.pool.PoolError:
                self.logger.debug("Connection pool already closed.")
            self.connection_pool = None
            self.logger.info("Connection pool closed")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Return basic performance metrics for dashboard display."""
        metrics: Dict[str, Any] = {}

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        numbackends,
                        xact_commit,
                        xact_rollback,
                        blks_hit,
                        blks_read,
                        tup_returned,
                        tup_fetched,
                        tup_inserted,
                        tup_updated,
                        tup_deleted
                    FROM pg_stat_database
                    WHERE datname = current_database()
                    """
                )
                stats = cursor.fetchone()
                if stats:
                    metrics["database_stats"] = dict(stats)

                cursor.execute(
                    """
                    SELECT state, COUNT(*) AS sessions
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY state
                    """
                )
                metrics["session_states"] = [dict(row) for row in cursor.fetchall()]

        return metrics


def get_database_manager(readonly: bool = True) -> DatabaseManager:
    """
    Get a database manager instance.
    
    Args:
        readonly: Whether to use read-only connection
    
    Returns:
        DatabaseManager instance
    """
    return DatabaseManager(readonly=readonly)
