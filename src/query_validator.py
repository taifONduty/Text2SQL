"""
SQL Query Validator and Sanitizer.
Ensures queries are safe and conform to security restrictions.
"""

import re
import logging
from typing import Tuple, Optional, List


logger = logging.getLogger(__name__)


class QueryValidator:
    """Validates and sanitizes SQL queries for security."""
    
    # Blocked SQL keywords and operations
    BLOCKED_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
        'MERGE', 'REPLACE', 'CALL', 'DO', 'HANDLER',
        'LOAD', 'PREPARE', 'DEALLOCATE', 'BEGIN', 'COMMIT',
        'ROLLBACK', 'SAVEPOINT', 'SET', 'RESET', 'SHOW',
        'COPY', 'ANALYZE', 'VACUUM', 'CLUSTER', 'LOCK',
        'LISTEN', 'NOTIFY', 'UNLISTEN'
    ]
    
    # Blocked system schemas and tables (except for schema introspection)
    BLOCKED_SCHEMAS = [
        'pg_catalog', 'pg_toast',
        'pg_temp', 'pg_internal', 'catalog', 'sys'
    ]
    
    # Allowed system schemas for schema introspection
    ALLOWED_SCHEMA_INTROSPECTION = [
        'information_schema.tables',
        'information_schema.columns',
        'information_schema.table_constraints',
        'information_schema.key_column_usage'
    ]
    
    # Allowed keywords for SELECT queries
    ALLOWED_KEYWORDS = [
        'SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT',
        'RIGHT', 'FULL', 'OUTER', 'ON', 'AS', 'AND', 'OR',
        'NOT', 'IN', 'BETWEEN', 'LIKE', 'IS', 'NULL',
        'GROUP', 'BY', 'HAVING', 'ORDER', 'LIMIT', 'OFFSET',
        'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN',
        'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'WITH',
        'UNION', 'INTERSECT', 'EXCEPT', 'EXISTS', 'ALL',
        'ANY', 'SOME', 'CAST', 'EXTRACT', 'COALESCE'
    ]
    
    def __init__(self):
        """Initialize the query validator."""
        self.logger = logging.getLogger(__name__)
    
    def validate(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a SQL query for security and compliance.
        
        Args:
            query: SQL query string to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Empty query provided"
        
        query_upper = query.upper().strip()
        
        # Check 1: Block dangerous keywords even if query is malformed
        for keyword in self.BLOCKED_KEYWORDS:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_upper):
                self.logger.warning(f"Blocked keyword detected: {keyword}")
                return False, f"Operation not allowed: {keyword}"
        
        # Check 2: Must be a SELECT or WITH query
        if not query_upper.startswith('SELECT') and not query_upper.startswith('WITH'):
            return False, "Only SELECT queries are allowed"
        
        # Check 3: Block system schema access (except for allowed introspection)
        # First check if this is a schema introspection query
        is_schema_introspection = any(
            allowed.upper() in query_upper for allowed in self.ALLOWED_SCHEMA_INTROSPECTION
        )
        
        if not is_schema_introspection:
            for schema in self.BLOCKED_SCHEMAS:
                if schema.upper() in query_upper:
                    self.logger.warning(f"System schema access blocked: {schema}")
                    return False, f"Access to system schema not allowed: {schema}"
            
            # Also block direct information_schema access unless it's introspection
            if 'INFORMATION_SCHEMA' in query_upper and not any(
                allowed.upper() in query_upper for allowed in self.ALLOWED_SCHEMA_INTROSPECTION
            ):
                self.logger.warning("Direct information_schema access blocked")
                return False, "Access to system schema not allowed: information_schema"
        
        # Check 4: SQL injection patterns
        injection_patterns = [
            r';\s*DROP',
            r';\s*DELETE',
            r';\s*INSERT',
            r'--.*DROP',
            r'/\*.*\*/',  # Block comments that might hide malicious code
            r'UNION.*SELECT.*FROM.*PG_',  # Union-based injection
            r"'.*OR.*'.*=.*'",  # Classic SQL injection
            r'1\s*=\s*1',  # Always true condition
            r'1\s*=\s*0',  # Always false condition
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, query_upper):
                self.logger.warning(f"SQL injection pattern detected: {pattern}")
                return False, "Potentially malicious query detected"
        
        # Check 5: Ensure query doesn't have multiple statements
        # Remove string literals first to avoid false positives
        query_without_strings = re.sub(r"'[^']*'", "", query)
        if ';' in query_without_strings.rstrip(';'):
            return False, "Multiple statements not allowed"
        
        self.logger.debug(f"Query validated successfully: {query[:100]}...")
        return True, None
    
    def sanitize(self, query: str) -> str:
        """
        Sanitize a SQL query by removing potentially dangerous elements.
        
        Args:
            query: SQL query string
        
        Returns:
            Sanitized query string
        """
        # Remove comments
        query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Ensure single statement (remove trailing semicolons except the last one)
        query = query.rstrip(';').strip() + ';'
        
        return query
    
    def extract_table_names(self, query: str) -> List[str]:
        """
        Extract table names from a SQL query.
        
        Args:
            query: SQL query string
        
        Returns:
            List of table names found in the query
        """
        # Simple pattern matching for FROM and JOIN clauses
        pattern = r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        matches = re.findall(pattern, query, re.IGNORECASE)
        return list(set(matches))


def validate_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Convenience function to validate a query.
    
    Args:
        query: SQL query string
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = QueryValidator()
    return validator.validate(query)
