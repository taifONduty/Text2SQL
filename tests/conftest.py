"""
Pytest configuration and fixtures for Text2SQL Analytics System.
"""

import pytest
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.database import DatabaseManager
from src.query_validator import QueryValidator
from src.text2sql_engine import Text2SQLEngine
from src.history import query_history
from src.cache import query_cache


@pytest.fixture(scope="session")
def test_db_connection():
    """Create test database connection."""
    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_admin_user,
        password=settings.db_admin_password,
        database='postgres'
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    yield conn
    
    conn.close()


@pytest.fixture(scope="session")
def setup_test_database(test_db_connection):
    """Set up test database with schema."""
    cursor = test_db_connection.cursor()
    
    # Drop and recreate test database
    cursor.execute(f"DROP DATABASE IF EXISTS {settings.test_db_name}")
    cursor.execute(f"CREATE DATABASE {settings.test_db_name}")
    
    cursor.close()
    
    # Connect to test database and create schema
    test_conn = psycopg2.connect(settings.test_database_url)
    test_cursor = test_conn.cursor()
    
    # Create minimal schema for testing
    schema_sql = """
    CREATE TABLE IF NOT EXISTS test_table (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        value INTEGER
    );
    
    INSERT INTO test_table (name, value) VALUES
        ('Test 1', 10),
        ('Test 2', 20),
        ('Test 3', 30);
    """
    
    test_cursor.execute(schema_sql)
    test_conn.commit()
    test_cursor.close()
    test_conn.close()
    
    yield
    
    # Cleanup
    cursor = test_db_connection.cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {settings.test_db_name}")
    cursor.close()


@pytest.fixture
def db_manager():
    """Provide a database manager instance for testing."""
    manager = DatabaseManager(readonly=True)
    yield manager
    if manager.connection_pool:
        manager.close_pool()


@pytest.fixture
def query_validator():
    """Provide a query validator instance for testing."""
    return QueryValidator()


@pytest.fixture
def mock_schema_info():
    """Provide mock schema information for testing."""
    return {
        'products': [
            {'column_name': 'product_id', 'data_type': 'integer', 'is_nullable': 'NO'},
            {'column_name': 'product_name', 'data_type': 'character varying', 'is_nullable': 'NO'},
            {'column_name': 'unit_price', 'data_type': 'numeric', 'is_nullable': 'YES'}
        ],
        'categories': [
            {'column_name': 'category_id', 'data_type': 'integer', 'is_nullable': 'NO'},
            {'column_name': 'category_name', 'data_type': 'character varying', 'is_nullable': 'NO'}
        ],
        'orders': [
            {'column_name': 'order_id', 'data_type': 'integer', 'is_nullable': 'NO'},
            {'column_name': 'customer_id', 'data_type': 'character varying', 'is_nullable': 'YES'},
            {'column_name': 'order_date', 'data_type': 'date', 'is_nullable': 'YES'}
        ]
    }


@pytest.fixture
def text2sql_engine(mock_schema_info):
    """Provide a Text2SQL engine instance for testing."""
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not set")
    
    engine = Text2SQLEngine()
    engine.set_schema_context(mock_schema_info)
    return engine


@pytest.fixture
def sample_dataframe():
    """Provide a sample DataFrame for testing."""
    import pandas as pd
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'age': [25, 30, 35, 40, 45],
        'city': ['New York', 'London', 'Paris', 'Tokyo', 'Sydney']
    })
@pytest.fixture(autouse=True)
def reset_history():
    """Ensure persistent history/cache do not leak between tests."""
    query_history.clear()
    query_cache.clear()
    yield
    query_history.clear()
    query_cache.clear()
