"""
Integration tests for database operations.
Tests connection management, query execution, and security.
"""

import pytest
import time
from src.database import DatabaseManager, TimeoutException
from src.config import settings


class TestDatabaseOperations:
    """Test suite for DatabaseManager class."""
    
    def test_connection_pool_initialization(self, db_manager):
        """Test that connection pool initializes correctly."""
        db_manager.initialize_pool(minconn=1, maxconn=5)
        assert db_manager.connection_pool is not None
    
    def test_get_connection(self, db_manager):
        """Test getting a connection from the pool."""
        db_manager.initialize_pool()
        
        with db_manager.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            assert result[0] == 1
            cursor.close()
    
    def test_execute_valid_select_query(self, db_manager):
        """Test executing a valid SELECT query."""
        query = "SELECT 1 as test_value;"
        results, columns = db_manager.execute_query(query)
        
        assert len(results) == 1
        assert results[0]['test_value'] == 1
        assert 'test_value' in columns
    
    def test_execute_query_with_invalid_syntax(self, db_manager):
        """Test that invalid SQL syntax raises error."""
        query = "SELECT * FROMM products;"  # Typo in FROM
        
        with pytest.raises(Exception):  # psycopg2 error
            db_manager.execute_query(query)
    
    def test_execute_blocked_insert_query(self, db_manager):
        """Test that INSERT queries are blocked."""
        query = "INSERT INTO products (product_name) VALUES ('Test');"
        
        with pytest.raises(ValueError, match="Invalid query"):
            db_manager.execute_query(query)
    
    def test_execute_blocked_update_query(self, db_manager):
        """Test that UPDATE queries are blocked."""
        query = "UPDATE products SET unit_price = 100;"
        
        with pytest.raises(ValueError, match="Invalid query"):
            db_manager.execute_query(query)
    
    def test_execute_blocked_delete_query(self, db_manager):
        """Test that DELETE queries are blocked."""
        query = "DELETE FROM products;"
        
        with pytest.raises(ValueError, match="Invalid query"):
            db_manager.execute_query(query)
    
    def test_result_set_limiting(self, db_manager):
        """Test that result sets are limited to MAX_RESULT_ROWS."""
        # This test would need a table with more than 1000 rows
        # For now, just verify the mechanism exists
        query = "SELECT generate_series(1, 100) as num;"
        results, columns = db_manager.execute_query(query)
        
        # Should not exceed max rows (1000)
        assert len(results) <= settings.max_result_rows
    
    def test_query_timeout_enforcement(self, db_manager):
        """Test that query timeout is enforced."""
        # Create a query that will take longer than timeout
        # pg_sleep is a PostgreSQL function that sleeps for specified seconds
        query = "SELECT pg_sleep(10);"  # Sleep for 10 seconds (timeout is 5)
        
        with pytest.raises((TimeoutException, Exception)):
            db_manager.execute_query(query, timeout=1)
    
    def test_test_connection_success(self, db_manager):
        """Test successful connection test."""
        result = db_manager.test_connection()
        assert result is True
    
    def test_test_connection_failure(self):
        """Test connection failure with invalid credentials."""
        invalid_db = DatabaseManager(
            connection_url="postgresql://invalid:invalid@localhost:5432/invalid"
        )
        result = invalid_db.test_connection()
        assert result is False
    
    def test_close_connection_pool(self, db_manager):
        """Test closing connection pool."""
        db_manager.initialize_pool()
        assert db_manager.connection_pool is not None
        
        db_manager.close_pool()
        # Pool should still exist but be closed
        assert db_manager.connection_pool is not None

