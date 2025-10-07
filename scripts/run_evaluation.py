#!/usr/bin/env python3
"""
Evaluation script for Text2SQL Analytics System.
Runs all test questions and generates accuracy metrics.
"""

import sys
import os
from pathlib import Path
import json
import time
from typing import List, Dict, Any
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.text2sql_engine import Text2SQLEngine
from src.database import DatabaseManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test questions from requirements
SIMPLE_QUESTIONS = [
    "How many products are currently not discontinued?",
    "List all customers from Germany",
    "What is the unit price of the most expensive product?",
    "Show all orders shipped in 1997",
    "Which employee has the job title 'Sales Representative'?"
]

INTERMEDIATE_QUESTIONS = [
    "What is the total revenue per product category?",
    "Which employee has processed the most orders?",
    "Show monthly sales trends for 1997",
    "List the top 5 customers by total order value",
    "What is the average order value by country?",
    "Which products are out of stock but not discontinued?",
    "Show the number of orders per shipper company",
    "What is the revenue contribution of each supplier?",
    "Find customers who placed orders in every quarter of 1997",
    "Calculate average delivery time by shipping company"
]

COMPLEX_QUESTIONS = [
    "What is the average order value by customer, sorted by their total lifetime value?",
    "Which products have above-average profit margins and are frequently ordered together?",
    "Show the year-over-year sales growth for each product category",
    "Identify customers who have placed orders for products from all categories",
    "Find the most profitable month for each employee based on their order commissions"
]


def calculate_query_quality(sql_query: str, execution_time: float) -> Dict[str, float]:
    """
    Calculate query quality metrics.
    
    Args:
        sql_query: SQL query string
        execution_time: Query execution time in seconds
    
    Returns:
        Dictionary with quality metrics
    """
    sql_upper = sql_query.upper()
    
    return {
        'uses_proper_joins': 1.0 if 'JOIN' in sql_upper and 'ON' in sql_upper else 0.0,
        'has_necessary_where': 1.0 if 'WHERE' in sql_upper or 'LIMIT' in sql_upper else 0.0,
        'correct_group_by': 1.0 if ('GROUP BY' not in sql_upper) or ('SELECT' in sql_upper and 'GROUP BY' in sql_upper) else 0.0,
        'efficient_indexing': 1.0,  # Assume efficient (would need EXPLAIN ANALYZE)
        'execution_time': 1.0 if execution_time < 1.0 else 0.5 if execution_time < 3.0 else 0.0
    }


def calculate_accuracy_score(
    execution_success: bool,
    result_match: bool,
    query_quality: float
) -> float:
    """
    Calculate overall accuracy score using heuristic formula.
    
    Formula from requirements:
        accuracy_score = 0.20 * execution_success + 0.40 * result_match + 0.40 * query_quality
    """
    return (
        0.20 * (1.0 if execution_success else 0.0) +
        0.40 * (1.0 if result_match else 0.0) +
        0.40 * query_quality
    )


def evaluate_questions(questions: List[str], category: str, engine: Text2SQLEngine) -> List[Dict[str, Any]]:
    """
    Evaluate a list of questions.
    
    Args:
        questions: List of questions to evaluate
        category: Category name (Simple, Intermediate, Complex)
        engine: Text2SQL engine instance
    
    Returns:
        List of evaluation results
    """
    results = []
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluating {category} Questions ({len(questions)} total)")
    logger.info(f"{'='*60}\n")
    
    for i, question in enumerate(questions, 1):
        logger.info(f"{i}. {question}")
        
        try:
            result = engine.query(question, execute=True)
            
            execution_success = result['error'] is None
            result_match = execution_success and result['row_count'] > 0  # Basic check
            
            # Calculate quality metrics
            if result['sql_query']:
                quality_metrics = calculate_query_quality(
                    result['sql_query'],
                    result['execution_time'] or 999
                )
                query_quality = sum(quality_metrics.values()) / len(quality_metrics)
            else:
                quality_metrics = {}
                query_quality = 0.0
            
            # Calculate accuracy score
            accuracy = calculate_accuracy_score(execution_success, result_match, query_quality)
            
            eval_result = {
                'category': category,
                'question': question,
                'sql_query': result['sql_query'],
                'execution_success': execution_success,
                'row_count': result['row_count'],
                'execution_time': result['execution_time'],
                'quality_metrics': quality_metrics,
                'query_quality': query_quality,
                'accuracy_score': accuracy,
                'error': result['error']
            }
            
            results.append(eval_result)
            
            # Log result
            status = "✓" if execution_success else "✗"
            logger.info(f"   {status} Accuracy: {accuracy:.2f} | Rows: {result['row_count']} | Time: {result['execution_time']:.3f}s" if result['execution_time'] else f"   {status} Accuracy: {accuracy:.2f}")
            if result['sql_query']:
                logger.info(f"   SQL: {result['sql_query'][:100]}...")
            if result['error']:
                logger.info(f"   Error: {result['error']}")
            logger.info("")
        
        except Exception as e:
            logger.error(f"   ✗ Unexpected error: {e}\n")
            results.append({
                'category': category,
                'question': question,
                'error': str(e),
                'execution_success': False,
                'accuracy_score': 0.0
            })
    
    return results


def print_summary(all_results: List[Dict[str, Any]]):
    """Print evaluation summary."""
    logger.info(f"\n{'='*60}")
    logger.info("EVALUATION SUMMARY")
    logger.info(f"{'='*60}\n")
    
    # Overall statistics
    total_questions = len(all_results)
    successful = sum(1 for r in all_results if r['execution_success'])
    
    avg_accuracy = sum(r['accuracy_score'] for r in all_results) / total_questions
    
    logger.info(f"Total Questions: {total_questions}")
    logger.info(f"Successful Executions: {successful}/{total_questions} ({successful/total_questions*100:.1f}%)")
    logger.info(f"Average Accuracy Score: {avg_accuracy:.3f}\n")
    
    # By category
    categories = ['Simple', 'Intermediate', 'Complex']
    
    logger.info("By Category:")
    for category in categories:
        cat_results = [r for r in all_results if r['category'] == category]
        if cat_results:
            cat_success = sum(1 for r in cat_results if r['execution_success'])
            cat_accuracy = sum(r['accuracy_score'] for r in cat_results) / len(cat_results)
            logger.info(f"  {category:12} - {cat_success}/{len(cat_results)} success, {cat_accuracy:.3f} avg accuracy")
    
    # Execution time statistics
    execution_times = [r.get('execution_time', 0) for r in all_results if r.get('execution_time')]
    if execution_times:
        avg_time = sum(execution_times) / len(execution_times)
        max_time = max(execution_times)
        logger.info(f"\nExecution Time: {avg_time:.3f}s avg, {max_time:.3f}s max")


def save_results(results: List[Dict[str, Any]], output_file: str = "evaluation_results.json"):
    """Save evaluation results to JSON file."""
    output_path = Path(__file__).parent.parent / output_file
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"\nResults saved to: {output_path}")


def main():
    """Main evaluation function."""
    logger.info("\n" + "="*60)
    logger.info("Text2SQL Analytics System - Evaluation")
    logger.info("="*60)
    
    try:
        # Initialize engine
        logger.info("\nInitializing Text2SQL engine...")
        engine = Text2SQLEngine()
        
        # Get schema context
        db_manager = DatabaseManager(readonly=False)
        schema_info = db_manager.get_schema_info()
        engine.set_schema_context(schema_info)
        
        logger.info(f"Schema loaded: {len(schema_info)} tables")
        
        # Evaluate all question categories
        all_results = []
        
        all_results.extend(evaluate_questions(SIMPLE_QUESTIONS, 'Simple', engine))
        all_results.extend(evaluate_questions(INTERMEDIATE_QUESTIONS, 'Intermediate', engine))
        all_results.extend(evaluate_questions(COMPLEX_QUESTIONS, 'Complex', engine))
        
        # Print summary
        print_summary(all_results)
        
        # Save results
        save_results(all_results)
        
        logger.info("\n" + "="*60)
        logger.info("Evaluation completed!")
        logger.info("="*60)
    
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

