"""
Complex query accuracy tests (5 questions).
Multi-level JOINs (4+ tables), subqueries, and advanced analytics.
"""

import pytest


class TestComplexQueries:
    """Test suite for complex analytical queries."""
    
    def test_q1_avg_order_value_by_customer_lifetime(self, text2sql_engine):
        """
        Question: What is the average order value by customer, sorted by their total lifetime value?
        Expected: Window functions or subquery with multiple aggregations
        """
        question = "What is the average order value by customer, sorted by their total lifetime value?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        assert result['error'] is None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'AVG' in sql
        assert 'CUSTOMER' in sql
        assert 'ORDER BY' in sql
    
    def test_q2_profitable_products_ordered_together(self, text2sql_engine):
        """
        Question: Which products have above-average profit margins and are frequently ordered together?
        Expected: Subquery for average, self-join for co-occurrence analysis
        """
        question = "Which products have above-average profit margins and are frequently ordered together?"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'PRODUCT' in sql
        # Complex query, so just verify it generates something
    
    def test_q3_yoy_sales_growth_by_category(self, text2sql_engine):
        """
        Question: Show the year-over-year sales growth for each product category
        Expected: Self-join or window function for YoY comparison
        """
        question = "Show the year-over-year sales growth for each product category"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'CATEGORY' in sql
        # Should involve year extraction
    
    def test_q4_customers_orders_from_all_categories(self, text2sql_engine):
        """
        Question: Identify customers who have placed orders for products from all categories
        Expected: Division operation (complex) or NOT EXISTS pattern
        """
        question = "Identify customers who have placed orders for products from all categories"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'CUSTOMER' in sql
        assert 'CATEGORY' in sql
    
    def test_q5_most_profitable_month_per_employee(self, text2sql_engine):
        """
        Question: Find the most profitable month for each employee based on their order commissions
        Expected: Window function or grouped subquery with ranking
        """
        question = "Find the most profitable month for each employee based on their order commissions"
        result = text2sql_engine.query(question, execute=False)
        
        assert result['sql_query'] is not None
        sql = result['sql_query'].upper()
        assert 'SELECT' in sql
        assert 'EMPLOYEE' in sql
        # Complex query involving commission calculations


class TestAccuracyScoring:
    """Test accuracy scoring implementation."""
    
    def calculate_accuracy_score(
        self,
        execution_success: bool,
        result_match: bool,
        query_quality_metrics: dict
    ) -> float:
        """
        Calculate accuracy score using the heuristic formula from requirements.
        
        Formula:
            accuracy_score = (
                0.20 * execution_success +
                0.40 * result_match +
                0.40 * query_quality
            )
        """
        query_quality = sum(query_quality_metrics.values()) / len(query_quality_metrics)
        
        accuracy_score = (
            0.20 * (1 if execution_success else 0) +
            0.40 * (1 if result_match else 0) +
            0.40 * query_quality
        )
        
        return accuracy_score
    
    def test_accuracy_score_perfect(self):
        """Test accuracy score calculation for perfect query."""
        metrics = {
            'uses_proper_joins': 1,
            'has_necessary_where': 1,
            'correct_group_by': 1,
            'efficient_indexing': 1,
            'execution_time': 1
        }
        
        score = self.calculate_accuracy_score(
            execution_success=True,
            result_match=True,
            query_quality_metrics=metrics
        )
        
        assert score == 1.0
    
    def test_accuracy_score_execution_only(self):
        """Test accuracy score when only execution succeeds."""
        metrics = {
            'uses_proper_joins': 0,
            'has_necessary_where': 0,
            'correct_group_by': 0,
            'efficient_indexing': 0,
            'execution_time': 0
        }
        
        score = self.calculate_accuracy_score(
            execution_success=True,
            result_match=False,
            query_quality_metrics=metrics
        )
        
        assert score == 0.20
    
    def test_accuracy_score_partial(self):
        """Test accuracy score with partial success."""
        metrics = {
            'uses_proper_joins': 1,
            'has_necessary_where': 1,
            'correct_group_by': 1,
            'efficient_indexing': 0,
            'execution_time': 0
        }
        
        score = self.calculate_accuracy_score(
            execution_success=True,
            result_match=True,
            query_quality_metrics=metrics
        )
        
        # 0.20 * 1 + 0.40 * 1 + 0.40 * (3/5) = 0.20 + 0.40 + 0.24 = 0.84
        assert abs(score - 0.84) < 0.01
