"""
Utility functions for Text2SQL Analytics System.
"""

import logging
import sys
from typing import Any, Dict, List
from datetime import datetime


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('text2sql.log')
        ]
    )
    return logging.getLogger(__name__)


def format_query_result(columns: List[str], rows: List[tuple]) -> List[Dict[str, Any]]:
    """
    Format query results as list of dictionaries.
    
    Args:
        columns: Column names
        rows: Query result rows
    
    Returns:
        List of dictionaries with column names as keys
    """
    return [dict(zip(columns, row)) for row in rows]


def validate_table_name(table_name: str) -> bool:
    """
    Validate that a table name is safe and doesn't contain suspicious patterns.
    
    Args:
        table_name: Table name to validate
    
    Returns:
        True if valid, False otherwise
    """
    # Only allow alphanumeric characters and underscores
    if not table_name.replace('_', '').isalnum():
        return False
    
    # Block system tables
    blocked_prefixes = ['pg_', 'information_schema', 'sys']
    return not any(table_name.lower().startswith(prefix) for prefix in blocked_prefixes)


def measure_execution_time(func):
    """
    Decorator to measure function execution time.
    
    Args:
        func: Function to measure
    
    Returns:
        Wrapped function with timing
    """
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        logger = logging.getLogger(__name__)
        logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
        return result
    return wrapper


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error messages to avoid leaking schema information.
    
    Args:
        error: Exception object
    
    Returns:
        Sanitized error message
    """
    error_str = str(error)
    
    # Remove table names and schema details
    sensitive_patterns = [
        'table', 'column', 'relation', 'constraint',
        'pg_', 'information_schema'
    ]
    
    # Generic error message if sensitive information detected
    if any(pattern in error_str.lower() for pattern in sensitive_patterns):
        return "Query execution failed. Please check your query syntax."
    
    return error_str

