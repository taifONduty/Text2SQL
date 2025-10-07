"""
Data Normalization Pipeline for Northwind Database.
Handles loading, validation, and normalization of data from Excel/CSV files.
"""

import pandas as pd
import logging
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import numpy as np


logger = logging.getLogger(__name__)


class DataNormalizationPipeline:
    """Pipeline for loading and normalizing Northwind database data."""
    
    def __init__(self, data_path: str):
        """
        Initialize the data normalization pipeline.
        
        Args:
            data_path: Path to the data file (Excel or CSV)
        """
        self.data_path = Path(data_path)
        self.dataframes: Dict[str, pd.DataFrame] = {}
        self.logger = logging.getLogger(__name__)
        self.normalization_metrics: Dict[str, Any] = {}
    
    def load_excel_file(self) -> Dict[str, pd.DataFrame]:
        """
        Load Excel file with multiple sheets.
        
        Returns:
            Dictionary mapping sheet names to DataFrames
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        self.logger.info(f"Loading data from: {self.data_path}")
        
        try:
            if self.data_path.suffix.lower() in ['.xlsx', '.xls']:
                # Load all sheets from Excel
                excel_file = pd.ExcelFile(self.data_path)
                self.logger.info(f"Found {len(excel_file.sheet_names)} sheets")
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    self.dataframes[sheet_name] = df
                    self.logger.info(f"Loaded sheet '{sheet_name}': {df.shape[0]} rows, {df.shape[1]} columns")
            
            elif self.data_path.suffix.lower() == '.csv':
                # Load single CSV file
                df = pd.read_csv(self.data_path)
                table_name = self.data_path.stem
                self.dataframes[table_name] = df
                self.logger.info(f"Loaded CSV '{table_name}': {df.shape[0]} rows, {df.shape[1]} columns")
            
            else:
                raise ValueError(f"Unsupported file format: {self.data_path.suffix}")
            
            return self.dataframes
        
        except Exception as e:
            self.logger.error(f"Failed to load data file: {e}")
            raise
    
    def validate_data_types(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """
        Validate and convert data types appropriately.
        
        Args:
            df: DataFrame to validate
            table_name: Name of the table
        
        Returns:
            DataFrame with validated data types
        """
        self.logger.info(f"Validating data types for table: {table_name}")
        
        # Convert column names to lowercase and replace spaces with underscores
        df.columns = df.columns.str.lower().str.replace(' ', '_')
        
        # Detect and convert date columns
        date_patterns = ['date', 'time', 'timestamp']
        for col in df.columns:
            if any(pattern in col.lower() for pattern in date_patterns):
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    self.logger.debug(f"Converted '{col}' to datetime")
                except Exception as e:
                    self.logger.warning(f"Could not convert '{col}' to datetime: {e}")
        
        # Convert numeric columns
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to convert to numeric
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except Exception:
                    pass
        
        return df
    
    def handle_missing_values(self, df: pd.DataFrame, strategy: str = 'keep') -> pd.DataFrame:
        """
        Handle missing values in the DataFrame.
        
        Args:
            df: DataFrame to process
            strategy: Strategy for handling NULLs ('keep', 'drop', 'fill')
        
        Returns:
            DataFrame with missing values handled
        """
        initial_nulls = df.isnull().sum().sum()
        
        if strategy == 'drop':
            df = df.dropna()
        elif strategy == 'fill':
            # Fill numeric columns with 0, string columns with empty string
            for col in df.columns:
                if df[col].dtype in ['float64', 'int64']:
                    df[col] = df[col].fillna(0)
                elif df[col].dtype == 'object':
                    df[col] = df[col].fillna('')
        # 'keep' strategy: leave NULLs as is (handled by PostgreSQL)
        
        final_nulls = df.isnull().sum().sum()
        self.logger.info(f"Missing values: {initial_nulls} -> {final_nulls} (strategy: {strategy})")
        
        return df
    
    def detect_duplicates(self, df: pd.DataFrame, table_name: str) -> Tuple[pd.DataFrame, int]:
        """
        Detect and remove duplicate rows.
        
        Args:
            df: DataFrame to check
            table_name: Name of the table
        
        Returns:
            Tuple of (deduplicated DataFrame, number of duplicates removed)
        """
        initial_rows = len(df)
        df = df.drop_duplicates()
        duplicates_removed = initial_rows - len(df)
        
        if duplicates_removed > 0:
            self.logger.warning(f"Removed {duplicates_removed} duplicate rows from {table_name}")
        
        return df, duplicates_removed
    
    def ensure_referential_integrity(
        self,
        dataframes: Dict[str, pd.DataFrame],
        foreign_keys: Dict[str, List[Tuple[str, str]]]
    ) -> Dict[str, pd.DataFrame]:
        """
        Ensure referential integrity across tables.
        
        Args:
            dataframes: Dictionary of DataFrames
            foreign_keys: Dictionary mapping table to list of (fk_column, ref_table)
        
        Returns:
            DataFrames with referential integrity ensured
        """
        self.logger.info("Ensuring referential integrity")
        
        for table_name, fk_list in foreign_keys.items():
            if table_name not in dataframes:
                continue
            
            df = dataframes[table_name]
            
            for fk_column, ref_table in fk_list:
                if ref_table not in dataframes or fk_column not in df.columns:
                    continue
                
                ref_df = dataframes[ref_table]
                ref_pk = ref_df.columns[0]  # Assuming first column is PK
                
                # Check for orphaned foreign keys
                valid_refs = ref_df[ref_pk].unique()
                initial_rows = len(df)
                
                # Keep rows where FK is null or exists in reference table
                df = df[df[fk_column].isnull() | df[fk_column].isin(valid_refs)]
                
                removed_rows = initial_rows - len(df)
                if removed_rows > 0:
                    self.logger.warning(
                        f"Removed {removed_rows} rows from {table_name} "
                        f"due to invalid {fk_column} references"
                    )
                
                dataframes[table_name] = df
        
        return dataframes
    
    def normalize_data(self) -> Dict[str, pd.DataFrame]:
        """
        Perform full data normalization pipeline.
        
        Returns:
            Dictionary of normalized DataFrames
        """
        self.logger.info("Starting data normalization pipeline")
        
        # Step 1: Load data
        if not self.dataframes:
            self.load_excel_file()
        
        # Step 2: Validate and clean each DataFrame
        for table_name, df in self.dataframes.items():
            self.logger.info(f"Normalizing table: {table_name}")
            
            # Validate data types
            df = self.validate_data_types(df, table_name)
            
            # Handle missing values (keep NULLs for database)
            df = self.handle_missing_values(df, strategy='keep')
            
            # Remove duplicates
            df, duplicates = self.detect_duplicates(df, table_name)
            
            # Update DataFrame
            self.dataframes[table_name] = df
            
            # Track metrics
            self.normalization_metrics[table_name] = {
                'rows': len(df),
                'columns': len(df.columns),
                'duplicates_removed': duplicates,
                'null_count': df.isnull().sum().sum()
            }
        
        self.logger.info("Data normalization completed")
        return self.dataframes
    
    def get_normalization_metrics(self) -> Dict[str, Any]:
        """
        Get normalization metrics report.
        
        Returns:
            Dictionary with normalization metrics
        """
        return self.normalization_metrics
    
    def export_to_csv(self, output_dir: str):
        """
        Export normalized DataFrames to CSV files.
        
        Args:
            output_dir: Directory to save CSV files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for table_name, df in self.dataframes.items():
            csv_path = output_path / f"{table_name}.csv"
            df.to_csv(csv_path, index=False)
            self.logger.info(f"Exported {table_name} to {csv_path}")


def load_and_normalize_data(data_path: str) -> Dict[str, pd.DataFrame]:
    """
    Convenience function to load and normalize data.
    
    Args:
        data_path: Path to data file
    
    Returns:
        Dictionary of normalized DataFrames
    """
    pipeline = DataNormalizationPipeline(data_path)
    return pipeline.normalize_data()

