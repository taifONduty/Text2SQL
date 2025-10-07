"""
Unit tests for SQL query validator and sanitizer.
Tests security restrictions and SQL injection prevention.
"""

import pytest
from src.query_validator import QueryValidator, validate_query


class TestQueryValidator:
    """Test suite for QueryValidator class."""
    
    def test_allow_simple_select(self, query_validator):
        """Test that simple SELECT queries are allowed."""
        query = "SELECT * FROM products;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is True
        assert error is None
    
    def test_allow_select_with_joins(self, query_validator):
        """Test that SELECT queries with JOINs are allowed."""
        query = """
        SELECT p.product_name, c.category_name 
        FROM products p
        JOIN categories c ON p.category_id = c.category_id;
        """
        is_valid, error = query_validator.validate(query)
        assert is_valid is True
        assert error is None
    
    def test_allow_select_with_aggregations(self, query_validator):
        """Test that SELECT queries with aggregations are allowed."""
        query = "SELECT category_id, COUNT(*), AVG(unit_price) FROM products GROUP BY category_id;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is True
        assert error is None
    
    def test_block_insert_statements(self, query_validator):
        """Test that INSERT statements are blocked."""
        query = "INSERT INTO products (product_name) VALUES ('Test');"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'INSERT' in error
    
    def test_block_update_statements(self, query_validator):
        """Test that UPDATE statements are blocked."""
        query = "UPDATE products SET unit_price = 100 WHERE product_id = 1;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'UPDATE' in error
    
    def test_block_delete_statements(self, query_validator):
        """Test that DELETE statements are blocked."""
        query = "DELETE FROM products WHERE product_id = 1;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'DELETE' in error
    
    def test_block_drop_statements(self, query_validator):
        """Test that DROP statements are blocked."""
        query = "DROP TABLE products;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'DROP' in error
    
    def test_block_create_statements(self, query_validator):
        """Test that CREATE statements are blocked."""
        query = "CREATE TABLE test (id INT);"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'CREATE' in error
    
    def test_block_alter_statements(self, query_validator):
        """Test that ALTER statements are blocked."""
        query = "ALTER TABLE products ADD COLUMN test VARCHAR(100);"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'ALTER' in error
    
    def test_sql_injection_prevention_union(self, query_validator):
        """Test SQL injection prevention for UNION attacks."""
        query = "SELECT * FROM products WHERE product_id = 1 UNION SELECT * FROM pg_user;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
    
    def test_sql_injection_prevention_or_equals(self, query_validator):
        """Test SQL injection prevention for OR '1'='1' attacks."""
        query = "SELECT * FROM products WHERE name = '' OR '1'='1';"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
    
    def test_sql_injection_prevention_comment_attack(self, query_validator):
        """Test SQL injection prevention for comment-based attacks."""
        query = "SELECT * FROM products; --DROP TABLE products;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
    
    def test_block_system_schema_access_pg_catalog(self, query_validator):
        """Test that pg_catalog access is blocked."""
        query = "SELECT * FROM pg_catalog.pg_tables;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'pg_catalog' in error or 'system schema' in error.lower()
    
    def test_block_system_schema_access_information_schema(self, query_validator):
        """Test that information_schema access is blocked."""
        query = "SELECT * FROM information_schema.columns;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'information_schema' in error or 'system schema' in error.lower()
    
    def test_block_multiple_statements(self, query_validator):
        """Test that multiple statements are blocked."""
        query = "SELECT * FROM products; SELECT * FROM categories;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'multiple' in error.lower()
    
    def test_empty_query(self, query_validator):
        """Test that empty queries are rejected."""
        query = ""
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'empty' in error.lower()
    
    def test_sanitize_removes_comments(self, query_validator):
        """Test that sanitize removes SQL comments."""
        query = "SELECT * FROM products; -- this is a comment"
        sanitized = query_validator.sanitize(query)
        assert '--' not in sanitized
        assert 'comment' not in sanitized
    
    def test_sanitize_removes_block_comments(self, query_validator):
        """Test that sanitize removes block comments."""
        query = "SELECT * /* comment */ FROM products;"
        sanitized = query_validator.sanitize(query)
        assert '/*' not in sanitized
        assert '*/' not in sanitized
    
    def test_extract_table_names(self, query_validator):
        """Test extraction of table names from query."""
        query = """
        SELECT p.product_name, c.category_name 
        FROM products p
        JOIN categories c ON p.category_id = c.category_id;
        """
        tables = query_validator.extract_table_names(query)
        assert 'products' in tables
        assert 'categories' in tables
        assert len(tables) == 2
    
    def test_allow_with_clause(self, query_validator):
        """Test that WITH (CTE) clauses are allowed."""
        query = """
        WITH product_stats AS (
            SELECT category_id, AVG(unit_price) as avg_price
            FROM products
            GROUP BY category_id
        )
        SELECT * FROM product_stats;
        """
        is_valid, error = query_validator.validate(query)
        assert is_valid is True
        assert error is None
    
    def test_allow_subqueries(self, query_validator):
        """Test that subqueries are allowed."""
        query = """
        SELECT product_name 
        FROM products 
        WHERE unit_price > (SELECT AVG(unit_price) FROM products);
        """
        is_valid, error = query_validator.validate(query)
        assert is_valid is True
        assert error is None
    
    def test_block_grant_statements(self, query_validator):
        """Test that GRANT statements are blocked."""
        query = "GRANT SELECT ON products TO public;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'GRANT' in error
    
    def test_block_revoke_statements(self, query_validator):
        """Test that REVOKE statements are blocked."""
        query = "REVOKE SELECT ON products FROM public;"
        is_valid, error = query_validator.validate(query)
        assert is_valid is False
        assert 'REVOKE' in error

