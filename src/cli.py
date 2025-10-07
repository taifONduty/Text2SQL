#!/usr/bin/env python3
"""
Command-line interface for Text2SQL Analytics System.
Interactive shell for asking natural language questions and utilities for
building a normalized warehouse from raw CSV exports.
"""

import argparse
import csv
import json
import logging
import shlex
import sys
from pathlib import Path
from typing import Optional

from .text2sql_engine import Text2SQLEngine
from .database import DatabaseManager
from .config import settings
from .normalizer import build_normalized_database


def print_banner():
    """Print application banner."""
    print("\n" + "="*70)
    print("  Text2SQL Analytics System - Interactive Shell")
    print("  Ask questions in natural language, get SQL and results!")
    print("="*70 + "\n")


def print_help():
    """Print help message."""
    help_text = """
Available Commands:
  <question>     Ask a natural language question
  :help          Show this help message
  :schema        Show database schema
  :tables        List all tables
  :history       Show query history
  :last          Show last query details
  :export csv <path>   Save last result rows as CSV
  :export json <path>  Save last result (SQL + rows) as JSON
  :clear         Clear screen
  :exit, :quit   Exit the application

Examples:
  > How many products are there?
  > Show top 5 customers by order value
  > What is the total revenue by category?
"""
    print(help_text)


def format_results_table(results: list, columns: list, max_rows: int = 20):
    """Format results as ASCII table."""
    if not results:
        return "No results"
    
    # Limit rows for display
    display_results = results[:max_rows]
    
    # Calculate column widths
    col_widths = {col: len(col) for col in columns}
    for row in display_results:
        for col in columns:
            value = str(row.get(col, ''))
            col_widths[col] = max(col_widths[col], len(value))
    
    # Build table
    header = " | ".join(col.ljust(col_widths[col]) for col in columns)
    separator = "-+-".join("-" * col_widths[col] for col in columns)
    
    table = f"\n{header}\n{separator}\n"
    
    for row in display_results:
        row_str = " | ".join(
            str(row.get(col, '')).ljust(col_widths[col]) 
            for col in columns
        )
        table += f"{row_str}\n"
    
    if len(results) > max_rows:
        table += f"\n... {len(results) - max_rows} more rows (showing first {max_rows})\n"
    
    return table


class InteractiveCLI:
    """Interactive command-line interface."""
    
    def __init__(self):
        """Initialize CLI."""
        self.engine: Optional[Text2SQLEngine] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.query_history = []
        self.last_result = None
        
        # Suppress info logging for cleaner output
        logging.basicConfig(level=logging.WARNING)
    
    def initialize(self):
        """Initialize Text2SQL engine and database connection."""
        print("Initializing Text2SQL engine...")
        
        try:
            # Check API key
            if not settings.gemini_api_key:
                print("Error: GEMINI_API_KEY not found in environment")
                print("   Please set it in your .env file")
                return False
            
            # Initialize engine
            self.engine = Text2SQLEngine()
            
            # Load schema
            print("Loading database schema...")
            self.db_manager = DatabaseManager(readonly=False)
            
            if not self.db_manager.test_connection():
                print("Error: Cannot connect to database")
                print("   Please check your database configuration in .env")
                return False
            
            schema_info = self.db_manager.get_schema_info()
            self.engine.set_schema_context(schema_info)
            
            print(f"✓ Schema loaded: {len(schema_info)} tables\n")
            return True
        
        except Exception as e:
            print(f"Initialization failed: {e}")
            return False
    
    def _export_last_result(self, fmt: str, output_path: Path) -> None:
        """Export the last successful result to the specified format."""
        if not self.last_result or self.last_result.get("error"):
            print("\nNo successful query result available for export.\n")
            return

        results = self.last_result.get("results") or []
        columns = self.last_result.get("columns") or []

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            if not results:
                print("\nNo rows to export.\n")
                return

            if not columns and results:
                columns = list(results[0].keys())

            try:
                with output_path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"\n✓ Exported {len(results)} rows to {output_path}\n")
            except Exception as exc:
                print(f"\nFailed to export CSV: {exc}\n")

        elif fmt == "json":
            payload = {
                "question": self.last_result.get("question"),
                "sql_query": self.last_result.get("sql_query"),
                "row_count": self.last_result.get("row_count"),
                "execution_time": self.last_result.get("execution_time"),
                "results": results,
                "columns": columns,
                "metadata": self.last_result.get("metadata", {}),
            }
            try:
                with output_path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                print(f"\n✓ Exported result payload to {output_path}\n")
            except Exception as exc:
                print(f"\nFailed to export JSON: {exc}\n")

        else:
            print(f"\nUnsupported export format: {fmt}\n")

    def handle_command(self, command: str):
        """Handle special commands."""
        raw_command = command.strip()
        command = raw_command.lower()
        
        if command == ':help':
            print_help()
        
        elif command == ':schema':
            if self.db_manager:
                schema_info = self.db_manager.get_schema_info()
                print(f"\nDatabase Schema ({len(schema_info)} tables):\n")
                for table_name in sorted(schema_info.keys()):
                    print(f"  • {table_name}")
                print()
        
        elif command == ':tables':
            if self.db_manager:
                schema_info = self.db_manager.get_schema_info()
                print(f"\nAvailable Tables ({len(schema_info)} total):\n")
                for i, table_name in enumerate(sorted(schema_info.keys()), 1):
                    print(f"{i:2}. {table_name}")
                print()
        
        elif command == ':history':
            if not self.query_history:
                print("\nNo query history yet.\n")
            else:
                print(f"\nQuery History ({len(self.query_history)} queries):\n")
                for i, entry in enumerate(self.query_history[-10:], 1):
                    print(f"{i}. {entry['question']}")
                    print(f"   → {entry['row_count']} rows in {entry['execution_time']:.3f}s")
                print()
        
        elif command == ':last':
            if self.last_result:
                print("\nLast Query Details:\n")
                print(f"Question: {self.last_result['question']}")
                print(f"\nGenerated SQL:\n{self.last_result['sql_query']}")
                print(f"\nRows: {self.last_result['row_count']}")
                print(f"Execution Time: {self.last_result['execution_time']:.4f}s")
                
                if self.last_result['error']:
                    print(f"\nError: {self.last_result['error']}")
                print()
            else:
                print("\nNo queries executed yet.\n")
        
        elif command == ':clear':
            print("\033[H\033[J", end="")
            print_banner()

        elif command.startswith(':export'):
            tokens = shlex.split(raw_command)
            if len(tokens) < 3:
                print("\nUsage: :export <csv|json> <output_path>\n")
                return

            fmt = tokens[1].lower()
            output_path = Path(" ".join(tokens[2:]))
            self._export_last_result(fmt, output_path)
        
        else:
            print(f"Unknown command: {command}")
            print("Type :help for available commands\n")
    
    def process_question(self, question: str):
        """Process a natural language question."""
        if not self.engine:
            print("Engine not initialized")
            return
        
        print(f"\nProcessing: {question}")
        print("-" * 70)
        
        try:
            result = self.engine.query(question, execute=True)
            
            # Store result
            self.last_result = result
            self.query_history.append(result)
            
            if result['error']:
                print(f"Error: {result['error']}\n")
                return
            
            # Display SQL
            print(f"\nGenerated SQL:\n{result['sql_query']}\n")
            
            # Display results
            if result['results']:
                print(f"Results ({result['row_count']} rows):")
                table = format_results_table(result['results'], result['columns'])
                print(table)
            else:
                print("📊 No results returned\n")
            
            # Display metadata
            print(f"Execution time: {result['execution_time']:.4f}s")
            print("-" * 70 + "\n")
        
        except Exception as e:
            print(f"Error: {e}\n")
    
    def run(self):
        """Run interactive CLI loop."""
        print_banner()
        
        if not self.initialize():
            return
        
        print_help()
        print("Ready! Type your question or :help for commands.\n")
        
        try:
            while True:
                try:
                    user_input = input("❯ ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith(':'):
                        if user_input.lower() in [':exit', ':quit', ':q']:
                            print("\nGoodbye! 👋\n")
                            break
                        else:
                            self.handle_command(user_input)
                    else:
                        # Process as question
                        self.process_question(user_input)
                
                except KeyboardInterrupt:
                    print("\n\nInterrupted. Type :exit to quit.\n")
                    continue
        
        except EOFError:
            print("\n\nGoodbye! 👋\n")


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(description="Text2SQL Analytics CLI")
    parser.add_argument(
        "--normalize",
        type=str,
        help="Path to a CSV file or directory to normalize and load into PostgreSQL",
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop and recreate tables before loading when using --normalize",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Process only top-level CSV files (no directory recursion)",
    )
    parser.set_defaults(recursive=True)

    args = parser.parse_args()

    if args.normalize:
        csv_path = Path(args.normalize)
        if not csv_path.exists():
            print(f"CSV path not found: {csv_path}")
            sys.exit(1)

        print("Loading CSV files and building normalized schema...")
        db_manager = DatabaseManager(
            connection_url=settings.admin_database_url,
            readonly=False,
        )

        try:
            normalized_tables = build_normalized_database(
                source_path=csv_path,
                db_manager=db_manager,
                recursive=args.recursive,
                drop_existing=args.drop_existing,
            )
        except Exception as exc:
            print(f"Normalization failed: {exc}")
            sys.exit(1)

        print("✓ Normalization complete and data loaded into PostgreSQL\n")
        for table_name, table in normalized_tables.items():
            row_count, column_count = table.dataframe.shape
            pk_display = ", ".join(table.primary_key)
            print(
                f"  • {table_name}: {row_count} rows × {column_count} cols | PK [{pk_display}]"
            )
        print()
        return

    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()
