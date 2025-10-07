"""
Text2SQL Engine using Google Gemini API.
Converts natural language questions to SQL queries.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import sys
import types

try:  # pragma: no cover - executed at import time
    import google.generativeai as genai
except ModuleNotFoundError:  # pragma: no cover - fallback for missing optional dependency
    stub = types.ModuleType("google.generativeai")

    def _missing(*args, **kwargs):
        raise ModuleNotFoundError(
            "google-generativeai is required. Install it with 'pip install google-generativeai'."
        )

    class _MissingGenerativeModel:  # type: ignore
        def __init__(self, *args, **kwargs):
            _missing()

    stub.configure = _missing  # type: ignore[attr-defined]
    stub.GenerativeModel = _MissingGenerativeModel  # type: ignore[attr-defined]
    sys.modules.setdefault("google.generativeai", stub)
    genai = stub  # type: ignore[assignment]

from .config import settings
from .cache import query_cache
from .database import DatabaseManager
from .history import query_history
from .query_validator import QueryValidator


logger = logging.getLogger(__name__)


class Text2SQLEngine:
    """Converts natural language to SQL using Google Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Text2SQL engine.
        
        Args:
            api_key: Google Gemini API key (optional, uses settings if not provided)
        """
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise ValueError("Gemini API key not provided")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
        
        self.query_validator = QueryValidator()
        self.logger = logging.getLogger(__name__)
        self.schema_context: Optional[str] = None
    
    def set_schema_context(self, schema_info: Dict[str, Any]):
        """
        Set database schema context for the LLM.
        
        Args:
            schema_info: Dictionary with table and column information
        """
        schema_description = "Database Schema (Northwind):\n\n"
        
        # Build schema description
        for table_name, columns in schema_info.items():
            schema_description += f"Table: {table_name}\n"
            schema_description += "Columns:\n"
            
            if isinstance(columns, list):
                for col in columns:
                    if isinstance(col, dict):
                        col_name = col.get('column_name', '')
                        data_type = col.get('data_type', '')
                        nullable = col.get('is_nullable', 'YES')
                        schema_description += f"  - {col_name} ({data_type})"
                        if nullable == 'NO':
                            schema_description += " NOT NULL"
                        schema_description += "\n"
            
            schema_description += "\n"
        
        self.schema_context = schema_description
        self.logger.info("Schema context set successfully")
    
    def _requires_tie_handling(self, question: str) -> bool:
        """Heuristic to detect when a question expects all tied extrema."""
        keywords = [
            "highest",
            "lowest",
            "maximum",
            "minimum",
            "top",
            "bottom",
            "largest",
            "smallest",
            "best",
            "worst",
        ]
        lowered = question.lower()
        return any(word in lowered for word in keywords)

    @staticmethod
    def _supports_ties(sql_query: str) -> bool:
        """Check whether SQL already returns all tied rows."""
        sql_upper = sql_query.upper()
        if "WITH TIES" in sql_upper:
            return True
        if re.search(r"FETCH\s+FIRST\s+\d+\s+ROW", sql_upper) and "WITH TIES" in sql_upper:
            return True
        if re.search(r"=\s*\(\s*SELECT\s+(MAX|MIN)\(", sql_upper):
            return True
        return False

    @staticmethod
    def _apply_ties_patch(sql_query: str) -> Optional[str]:
        """Attempt to patch ORDER BY ... LIMIT 1 queries to keep ties."""
        pattern = re.compile(r"\s+LIMIT\s+1\s*;?\s*$", re.IGNORECASE)
        if pattern.search(sql_query):
            patched = pattern.sub(" FETCH FIRST 1 ROWS WITH TIES;", sql_query.rstrip())
            return patched
        return None

    def generate_sql(self, question: str, max_retries: int = 2) -> Tuple[str, Dict[str, Any]]:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
            max_retries: Maximum number of retries on failure
        
        Returns:
            Tuple of (SQL query string, metadata dict)
        
        Raises:
            ValueError: If query generation fails after retries
        """
        if not self.schema_context:
            raise ValueError("Schema context not set. Call set_schema_context() first.")
        # Learning mechanism: reuse successful past SQL if available
        historic = query_history.lookup(question)
        if historic and historic.get("sql_query"):
            sql_query = historic["sql_query"]
            if self._requires_tie_handling(question) and not self._supports_ties(sql_query):
                self.logger.info(
                    "Skipping history reuse for '%s' because tie-aware SQL is required.", question
                )
            else:
                metadata = {
                    "question": question,
                    "attempts": 0,
                    "source": "history",
                    "reused_at": historic.get("created_at"),
                }
                self.logger.info("Reusing SQL from history for question: %s", question)
                return sql_query, metadata

        # Build prompt for fresh generation
        prompt = self._build_prompt(question)

        reminder_appended = False
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"Generating SQL for question (attempt {attempt + 1}): {question}")
                
                # Generate response
                response = self.model.generate_content(prompt)
                
                # Extract SQL from response
                sql_query = self._extract_sql_from_response(response.text)
                
                # Validate generated query
                is_valid, error_msg = self.query_validator.validate(sql_query)
                
                if is_valid:
                    if self._requires_tie_handling(question) and not self._supports_ties(sql_query):
                        patched_sql = self._apply_ties_patch(sql_query)
                        if patched_sql and self._supports_ties(patched_sql):
                            self.logger.info("Patched generated SQL to include WITH TIES.")
                            sql_query = patched_sql
                        else:
                            if attempt < max_retries:
                                self.logger.warning(
                                    "Generated SQL missing tie handling; retrying with guidance."
                                )
                                if not reminder_appended:
                                    prompt += (
                                        "\n\nReminder: Ensure the query includes all tied rows "
                                        "by using FETCH FIRST ... WITH TIES or filtering by MAX/MIN."
                                    )
                                    reminder_appended = True
                                continue
                            raise ValueError(
                                "Generated SQL is missing tie-aware logic (FETCH FIRST ... WITH TIES or MAX/MIN filter)."
                            )
                    metadata = {
                        'question': question,
                        'attempts': attempt + 1,
                        'raw_response': response.text[:500]  # Store first 500 chars
                    }
                    self.logger.info(f"SQL generated successfully: {sql_query[:100]}...")
                    return sql_query, metadata
                else:
                    self.logger.warning(f"Generated invalid SQL (attempt {attempt + 1}): {error_msg}")
                    if attempt < max_retries:
                        # Retry with validation feedback
                        prompt += f"\n\nPrevious attempt failed: {error_msg}. Please generate a valid SELECT-only query."
                        continue
                    else:
                        raise ValueError(f"Failed to generate valid SQL after {max_retries + 1} attempts: {error_msg}")
            
            except Exception as e:
                self.logger.error(f"Error generating SQL (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise ValueError(f"Failed to generate SQL: {e}")
        
        raise ValueError("Failed to generate SQL query")
    
    def _build_prompt(self, question: str) -> str:
        """
        Build prompt for Gemini API.
        
        Args:
            question: Natural language question
        
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a SQL expert. Convert the following natural language question into a PostgreSQL query.

{self.schema_context}

IMPORTANT RULES:
1. Generate ONLY SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
2. Use proper JOINs (avoid cartesian products)
3. Include appropriate WHERE clauses for filtering
4. Use GROUP BY when aggregating data
5. Return ONLY the SQL query without explanations
6. Do not access system tables (pg_catalog, information_schema)
7. Use table and column names exactly as shown in the schema
8. End the query with a semicolon
9. When answering questions about highest/lowest/top values, include all tied rows (e.g., use FETCH FIRST ... WITH TIES or filter by MAX/MIN)

Question: {question}

SQL Query:
"""
        return prompt
    
    def _extract_sql_from_response(self, response_text: str) -> str:
        """
        Extract SQL query from Gemini response.
        
        Args:
            response_text: Raw response from Gemini
        
        Returns:
            Extracted SQL query
        """
        # Try to extract SQL from code blocks
        code_block_pattern = r'```sql\n(.*?)\n```'
        match = re.search(code_block_pattern, response_text, re.DOTALL | re.IGNORECASE)
        
        if match:
            sql_query = match.group(1).strip()
        else:
            # Try generic code block
            code_block_pattern = r'```\n(.*?)\n```'
            match = re.search(code_block_pattern, response_text, re.DOTALL)
            
            if match:
                sql_query = match.group(1).strip()
            else:
                # Assume entire response is SQL
                sql_query = response_text.strip()
        
        # Clean up the query
        sql_query = sql_query.strip()
        
        # Remove any markdown or extra formatting
        sql_query = re.sub(r'^SQL Query:\s*', '', sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r'^Query:\s*', '', sql_query, flags=re.IGNORECASE)
        
        return sql_query
    
    def query(self, question: str, execute: bool = True, max_retries: int = 2) -> Dict[str, Any]:
        """
        Convert question to SQL and optionally execute it.
        
        Args:
            question: Natural language question
            execute: Whether to execute the generated query
        
        Returns:
            Dictionary with query, results, and metadata
        """
        result = {
            'question': question,
            'sql_query': None,
            'results': None,
            'columns': None,
            'row_count': 0,
            'execution_time': None,
            'error': None,
            'metadata': {}
        }
        
        cache_hit = False
        
        try:
            # Generate SQL
            sql_query, metadata = self.generate_sql(question, max_retries=max_retries)
            result['sql_query'] = sql_query
            result['metadata'] = metadata
            
            if execute and sql_query:
                cached_payload = query_cache.get(sql_query)
                if cached_payload:
                    cache_hit = True
                    result['results'] = cached_payload.get('results')
                    result['columns'] = cached_payload.get('columns')
                    result['row_count'] = cached_payload.get('row_count', 0)
                    result['execution_time'] = cached_payload.get('execution_time')
                    result['metadata']['cache_hit'] = True
                    result['metadata']['cache_backend'] = query_cache.backend()
                    self.logger.info("Cache hit for SQL query.")
                else:
                    db_manager = DatabaseManager(readonly=True)
                    start_time = time.time()
                    results, columns = db_manager.execute_query(sql_query)
                    execution_time = time.time() - start_time
                    
                    result['results'] = results
                    result['columns'] = columns
                    result['row_count'] = len(results)
                    result['execution_time'] = execution_time
                    result['metadata']['cache_hit'] = False
                    result['metadata']['cache_backend'] = query_cache.backend()
                    
                    query_cache.set(
                        sql_query,
                        {
                            'results': results,
                            'columns': columns,
                            'row_count': len(results),
                            'execution_time': execution_time,
                        },
                    )
                    
                    self.logger.info(f"Query executed in {execution_time:.4f}s, returned {len(results)} rows")
        
        except Exception as e:
            self.logger.error(f"Error processing question: {e}")
            result['error'] = str(e)
        
        finally:
            try:
                query_history.record(
                    question=question,
                    sql_query=result['sql_query'],
                    success=result['error'] is None,
                    row_count=result['row_count'],
                    execution_time=result['execution_time'],
                    cached=cache_hit,
                    error=result['error'],
                )
            except Exception as exc:  # pragma: no cover - history failures should not break flow
                self.logger.warning("Failed to record query history: %s", exc)
        
        return result
    
    def batch_query(self, questions: List[str], execute: bool = True) -> List[Dict[str, Any]]:
        """
        Process multiple questions in batch.
        
        Args:
            questions: List of natural language questions
        
        Returns:
            List of result dictionaries
        """
        results = []
        for i, question in enumerate(questions, 1):
            self.logger.info(f"Processing question {i}/{len(questions)}")
            result = self.query(question, execute=execute)
            results.append(result)
        
        return results


def create_text2sql_engine(schema_info: Optional[Dict[str, Any]] = None) -> Text2SQLEngine:
    """
    Create and initialize a Text2SQL engine.
    
    Args:
        schema_info: Optional schema information to set context
    
    Returns:
        Initialized Text2SQLEngine instance
    """
    engine = Text2SQLEngine()
    
    if schema_info:
        engine.set_schema_context(schema_info)
    
    return engine
