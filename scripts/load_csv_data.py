#!/usr/bin/env python3
"""
Script to load CSV files into PostgreSQL with proper column mapping.
"""

import sys
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def camel_to_snake(name):
    """Convert camelCase to snake_case."""
    # Insert underscore before capital letters and convert to lowercase
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def load_csv_files():
    """Load CSV files into PostgreSQL."""
    logger.info("Loading CSV files into PostgreSQL...")
    
    data_dir = Path(__file__).parent.parent / 'data' / 'raw'
    csv_files = list(data_dir.glob('*.csv'))
    
    if not csv_files:
        logger.error("No CSV files found!")
        return False
    
    logger.info(f"Found {len(csv_files)} CSV files")
    
    # Create SQLAlchemy engine
    engine = create_engine(settings.admin_database_url)
    
    # Table loading order (respecting foreign key dependencies)
    table_order = [
        ('categories', 'categories.csv'),
        ('shippers', 'shippers.csv'),
        ('customers', 'customers.csv'),
        ('employees', 'employees.csv'),
        ('products', 'products.csv'),
        ('orders', 'orders.csv'),
        ('order_details', 'order_details.csv')
    ]
    
    loaded_count = 0
    
    for table_name, csv_filename in table_order:
        csv_path = data_dir / csv_filename
        
        if not csv_path.exists():
            logger.warning(f"⚠ {csv_filename} not found, skipping...")
            continue
        
        try:
            logger.info(f"\nLoading {csv_filename} into {table_name}...")
            
            # Load CSV with different encoding attempts
            df = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(csv_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                logger.error(f"  ✗ Could not read {csv_filename}")
                continue
            
            logger.info(f"  Read {len(df)} rows from CSV")
            
            # Convert column names from camelCase to snake_case
            df.columns = [camel_to_snake(col) for col in df.columns]
            
            logger.info(f"  Columns: {', '.join(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")
            
            # Insert into database
            df.to_sql(
                table_name,
                engine,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )
            
            logger.info(f"  ✓ Successfully loaded {len(df)} rows into {table_name}")
            loaded_count += 1
        
        except Exception as e:
            logger.error(f"  ✗ Error loading {csv_filename}: {e}")
            continue
    
    engine.dispose()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Loaded {loaded_count}/{len(table_order)} tables successfully")
    logger.info(f"{'='*60}")
    
    return loaded_count > 0


def verify_data():
    """Verify data was loaded correctly."""
    logger.info("\nVerifying loaded data...")
    
    engine = create_engine(settings.admin_database_url)
    
    tables = ['categories', 'customers', 'employees', 'orders', 'products', 'shippers', 'order_details']
    
    for table in tables:
        try:
            result = pd.read_sql(f"SELECT COUNT(*) as count FROM {table}", engine)
            count = result['count'][0]
            logger.info(f"  {table:20} {count:5} rows")
        except Exception as e:
            logger.warning(f"  {table:20} Error: {e}")
    
    engine.dispose()


def main():
    """Main function."""
    logger.info("="*60)
    logger.info("CSV Data Loader for Northwind Database")
    logger.info("="*60)
    
    if load_csv_files():
        verify_data()
        logger.info("\n✓ Data loading complete!")
    else:
        logger.error("\n✗ Data loading failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()

