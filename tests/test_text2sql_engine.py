"""
Integration tests for Text2SQL engine.
Tests natural language to SQL conversion and execution.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.text2sql_engine import Text2SQLEngine


class TestText2SQLEngine:
    """Test suite for Text2SQLEngine class."""
    
    def test_engine_initialization_without_api_key(self):
        """Test that engine requires API key."""
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = ""
            
            with pytest.raises(ValueError, match="API key"):
                Text2SQLEngine()
    
    def test_set_schema_context(self, mock_schema_info):
        """Test setting schema context."""
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            with patch('google.generativeai.configure'):
                with patch('google.generativeai.GenerativeModel'):
                    engine = Text2SQLEngine()
                    engine.set_schema_context(mock_schema_info)
                    
                    assert engine.schema_context is not None
                    assert 'products' in engine.schema_context
                    assert 'categories' in engine.schema_context
    
    def test_generate_sql_without_schema_context(self):
        """Test that generate_sql requires schema context."""
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            with patch('google.generativeai.configure'):
                with patch('google.generativeai.GenerativeModel'):
                    engine = Text2SQLEngine()
                    
                    with pytest.raises(ValueError, match="Schema context"):
                        engine.generate_sql("Show all products")
    
    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    def test_generate_sql_success(self, mock_configure, mock_model, mock_schema_info):
        """Test successful SQL generation."""
        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = "```sql\nSELECT * FROM products;\n```"
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_model_instance
        
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            engine = Text2SQLEngine()
            engine.set_schema_context(mock_schema_info)
            
            sql_query, metadata = engine.generate_sql("Show all products")
            
            assert "SELECT" in sql_query
            assert "products" in sql_query
            assert metadata['question'] == "Show all products"
    
    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    def test_extract_sql_from_code_block(self, mock_configure, mock_model):
        """Test extracting SQL from markdown code block."""
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            engine = Text2SQLEngine()
            
            response_text = "```sql\nSELECT * FROM products;\n```"
            sql = engine._extract_sql_from_response(response_text)
            
            assert sql == "SELECT * FROM products;"
    
    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    def test_extract_sql_from_plain_text(self, mock_configure, mock_model):
        """Test extracting SQL from plain text response."""
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            engine = Text2SQLEngine()
            
            response_text = "SELECT * FROM categories;"
            sql = engine._extract_sql_from_response(response_text)
            
            assert sql == "SELECT * FROM categories;"
    
    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    def test_generate_sql_with_invalid_query_retries(self, mock_configure, mock_model, mock_schema_info):
        """Test that invalid queries trigger retries."""
        # First response is invalid (INSERT), second is valid
        mock_response_invalid = Mock()
        mock_response_invalid.text = "INSERT INTO products VALUES (1, 'Test');"
        
        mock_response_valid = Mock()
        mock_response_valid.text = "SELECT * FROM products;"
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.side_effect = [
            mock_response_invalid,
            mock_response_valid
        ]
        mock_model.return_value = mock_model_instance
        
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            engine = Text2SQLEngine()
            engine.set_schema_context(mock_schema_info)
            
            sql_query, metadata = engine.generate_sql("Show products", max_retries=2)
            
            assert "SELECT" in sql_query
            assert metadata['attempts'] == 2
    
    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    @patch('src.text2sql_engine.DatabaseManager')
    def test_query_end_to_end(self, mock_db, mock_configure, mock_model, mock_schema_info):
        """Test end-to-end query processing."""
        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = "SELECT * FROM products LIMIT 10;"
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_model_instance
        
        # Mock database response
        mock_db_instance = Mock()
        mock_db_instance.execute_query.return_value = (
            [{'product_id': 1, 'product_name': 'Test'}],
            ['product_id', 'product_name']
        )
        mock_db.return_value = mock_db_instance
        
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            engine = Text2SQLEngine()
            engine.set_schema_context(mock_schema_info)
            
            result = engine.query("Show all products", execute=True)
            
            assert result['sql_query'] is not None
            assert result['results'] is not None
            assert result['row_count'] == 1
            assert result['error'] is None
    
    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    def test_query_without_execution(self, mock_configure, mock_model, mock_schema_info):
        """Test query generation without execution."""
        mock_response = Mock()
        mock_response.text = "SELECT * FROM products;"
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_model_instance
        
        with patch('src.text2sql_engine.settings') as mock_settings:
            mock_settings.gemini_api_key = "test_key"
            
            engine = Text2SQLEngine()
            engine.set_schema_context(mock_schema_info)
            
            result = engine.query("Show all products", execute=False)
            
            assert result['sql_query'] is not None
            assert result['results'] is None
            assert result['execution_time'] is None

