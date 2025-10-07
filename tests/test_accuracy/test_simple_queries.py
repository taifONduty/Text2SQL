"""
Simple query accuracy tests (5 questions).
Single table SELECT with WHERE clauses.
"""

import pytest


class TestSimpleQueries:
    """Test suite for simple analytical queries."""
    
    def test_q1_non_discontinued_products(self, text2sql_engine):
        """
        Question: How many products are currently not discontinued?
        Expected: Single numeric value (count of products where discontinued = false)
        """
        question = "How many products are currently not discontinued?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        
        # Verify query characteristics
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'COUNT' in sql or 'DISCONTINUED' in sql
        assert 'PRODUCT' in sql
    
    def test_q2_customers_from_germany(self, text2sql_engine):
        """
        Question: List all customers from Germany
        Expected: Rows with customer information where country = 'Germany'
        """
        question = "List all customers from Germany"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'CUSTOMER' in sql
        assert 'GERMANY' in sql or 'WHERE' in sql
    
    def test_q3_most_expensive_product(self, text2sql_engine):
        """
        Question: What is the unit price of the most expensive product?
        Expected: Single row with maximum unit_price
        """
        question = "What is the unit price of the most expensive product?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'PRODUCT' in sql
        assert 'PRICE' in sql
        assert 'MAX' in sql or 'ORDER BY' in sql
    
    def test_q4_orders_shipped_in_1997(self, text2sql_engine):
        """
        Question: Show all orders shipped in 1997
        Expected: Orders where shipped_date is in year 1997
        """
        question = "Show all orders shipped in 1997"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'ORDER' in sql
        assert '1997' in sql or 'SHIPPED' in sql
    
    def test_q5_sales_representative_employees(self, text2sql_engine):
        """
        Question: Which employee has the job title 'Sales Representative'?
        Expected: Employees where title = 'Sales Representative'
        """
        question = "Which employee has the job title 'Sales Representative'?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'EMPLOYEE' in sql
        assert 'TITLE' in sql or 'SALES' in sql

