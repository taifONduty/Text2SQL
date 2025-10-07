"""
Intermediate query accuracy tests (10 questions).
Multi-table JOINs (2-3 tables), GROUP BY, and aggregations.
"""

import pytest


class TestIntermediateQueries:
    """Test suite for intermediate analytical queries."""
    
    # All 10 intermediate questions as specified in requirements
    
    def test_q1_total_revenue_per_category(self, text2sql_engine):
        """Question: What is the total revenue per product category?"""
        question = "What is the total revenue per product category?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'SUM' in sql or 'TOTAL' in sql
        assert 'CATEGORY' in sql
    
    def test_q2_employee_most_orders(self, text2sql_engine):
        """Question: Which employee has processed the most orders?"""
        question = "Which employee has processed the most orders?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'EMPLOYEE' in sql
        assert 'COUNT' in sql or 'MAX' in sql
    
    def test_q3_monthly_sales_trends_1997(self, text2sql_engine):
        """Question: Show monthly sales trends for 1997"""
        question = "Show monthly sales trends for 1997"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert '1997' in sql
        assert 'GROUP BY' in sql or 'MONTH' in sql
    
    def test_q4_top_5_customers_by_order_value(self, text2sql_engine):
        """Question: List the top 5 customers by total order value"""
        question = "List the top 5 customers by total order value"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'CUSTOMER' in sql
        assert 'LIMIT' in sql and '5' in sql
    
    def test_q5_average_order_value_by_country(self, text2sql_engine):
        """Question: What is the average order value by country?"""
        question = "What is the average order value by country?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'AVG' in sql
        assert 'COUNTRY' in sql
    
    def test_q6_out_of_stock_not_discontinued(self, text2sql_engine):
        """Question: Which products are out of stock but not discontinued?"""
        question = "Which products are out of stock but not discontinued?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'PRODUCT' in sql
        assert 'STOCK' in sql or 'DISCONTINUED' in sql
    
    def test_q7_orders_per_shipper(self, text2sql_engine):
        """Question: Show the number of orders per shipper company"""
        question = "Show the number of orders per shipper company"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'COUNT' in sql
        assert 'SHIPPER' in sql
    
    def test_q8_revenue_contribution_per_supplier(self, text2sql_engine):
        """Question: What is the revenue contribution of each supplier?"""
        question = "What is the revenue contribution of each supplier?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'SUPPLIER' in sql
        assert 'SUM' in sql or 'REVENUE' in sql
    
    def test_q9_customers_every_quarter_1997(self, text2sql_engine):
        """Question: Find customers who placed orders in every quarter of 1997"""
        question = "Find customers who placed orders in every quarter of 1997"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'CUSTOMER' in sql
        assert '1997' in sql
    
    def test_q10_avg_delivery_time_by_shipper(self, text2sql_engine):
        """Question: Calculate average delivery time by shipping company"""
        question = "Calculate average delivery time by shipping company"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'AVG' in sql
        assert 'SHIPPER' in sql or 'SHIP' in sql
