"""
Unit tests for data normalization pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile

from src.data_loader import DataNormalizationPipeline


class TestDataNormalizationPipeline:
    """Test suite for DataNormalizationPipeline class."""
    
    def test_load_valid_excel_file(self, tmp_path):
        """Test loading a valid Excel file."""
        # Create a temporary Excel file
        excel_path = tmp_path / "test_data.xlsx"
        
        with pd.ExcelWriter(excel_path) as writer:
            df1 = pd.DataFrame({'id': [1, 2, 3], 'name': ['A', 'B', 'C']})
            df2 = pd.DataFrame({'id': [1, 2], 'value': [10, 20]})
            df1.to_excel(writer, sheet_name='Sheet1', index=False)
            df2.to_excel(writer, sheet_name='Sheet2', index=False)
        
        pipeline = DataNormalizationPipeline(str(excel_path))
        dataframes = pipeline.load_excel_file()
        
        assert len(dataframes) == 2
        assert 'Sheet1' in dataframes
        assert 'Sheet2' in dataframes
        assert len(dataframes['Sheet1']) == 3
        assert len(dataframes['Sheet2']) == 2
    
    def test_load_nonexistent_file(self):
        """Test loading a nonexistent file raises error."""
        pipeline = DataNormalizationPipeline("nonexistent.xlsx")
        
        with pytest.raises(FileNotFoundError):
            pipeline.load_excel_file()
    
    def test_validate_data_types(self):
        """Test data type validation and conversion."""
        df = pd.DataFrame({
            'ID': [1, 2, 3],
            'Name': ['A', 'B', 'C'],
            'Price': ['10.5', '20.0', '30.5'],
            'Order Date': ['2024-01-01', '2024-01-02', '2024-01-03']
        })
        
        pipeline = DataNormalizationPipeline("dummy.xlsx")
        validated_df = pipeline.validate_data_types(df, 'test_table')
        
        # Check column names are lowercase with underscores
        assert 'id' in validated_df.columns
        assert 'name' in validated_df.columns
        assert 'price' in validated_df.columns
        assert 'order_date' in validated_df.columns
        
        # Check date conversion
        assert pd.api.types.is_datetime64_any_dtype(validated_df['order_date'])
    
    def test_handle_missing_values_keep(self):
        """Test handling missing values with keep strategy."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['A', None, 'C'],
            'value': [10, 20, None]
        })
        
        pipeline = DataNormalizationPipeline("dummy.xlsx")
        result_df = pipeline.handle_missing_values(df, strategy='keep')
        
        assert result_df.isnull().sum().sum() == 2
    
    def test_handle_missing_values_drop(self):
        """Test handling missing values with drop strategy."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['A', None, 'C'],
            'value': [10, 20, 30]
        })
        
        pipeline = DataNormalizationPipeline("dummy.xlsx")
        result_df = pipeline.handle_missing_values(df, strategy='drop')
        
        assert len(result_df) == 2  # Should drop row with None
        assert result_df.isnull().sum().sum() == 0
    
    def test_detect_duplicates(self):
        """Test duplicate row detection and removal."""
        df = pd.DataFrame({
            'id': [1, 2, 2, 3],
            'name': ['A', 'B', 'B', 'C']
        })
        
        pipeline = DataNormalizationPipeline("dummy.xlsx")
        result_df, duplicates_count = pipeline.detect_duplicates(df, 'test_table')
        
        assert len(result_df) == 3
        assert duplicates_count == 1
    
    def test_detect_no_duplicates(self):
        """Test with no duplicates present."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['A', 'B', 'C']
        })
        
        pipeline = DataNormalizationPipeline("dummy.xlsx")
        result_df, duplicates_count = pipeline.detect_duplicates(df, 'test_table')
        
        assert len(result_df) == 3
        assert duplicates_count == 0
    
    def test_ensure_referential_integrity(self):
        """Test referential integrity enforcement."""
        # Create parent and child tables
        parent_df = pd.DataFrame({
            'category_id': [1, 2, 3],
            'category_name': ['Cat1', 'Cat2', 'Cat3']
        })
        
        child_df = pd.DataFrame({
            'product_id': [1, 2, 3, 4],
            'product_name': ['P1', 'P2', 'P3', 'P4'],
            'category_id': [1, 2, 99, None]  # 99 is invalid reference
        })
        
        dataframes = {
            'categories': parent_df,
            'products': child_df
        }
        
        foreign_keys = {
            'products': [('category_id', 'categories')]
        }
        
        pipeline = DataNormalizationPipeline("dummy.xlsx")
        result = pipeline.ensure_referential_integrity(dataframes, foreign_keys)
        
        # Should keep rows with valid FK or NULL, remove row with FK=99
        assert len(result['products']) == 3
    
    def test_normalization_metrics(self, tmp_path):
        """Test that normalization metrics are tracked."""
        excel_path = tmp_path / "test.xlsx"
        
        df = pd.DataFrame({
            'id': [1, 2, 2, 3],
            'name': ['A', 'B', 'B', 'C']
        })
        
        with pd.ExcelWriter(excel_path) as writer:
            df.to_excel(writer, sheet_name='TestTable', index=False)
        
        pipeline = DataNormalizationPipeline(str(excel_path))
        pipeline.normalize_data()
        
        metrics = pipeline.get_normalization_metrics()
        
        assert 'TestTable' in metrics
        assert metrics['TestTable']['duplicates_removed'] == 1
        assert metrics['TestTable']['rows'] == 3

