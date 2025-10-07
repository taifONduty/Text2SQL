#!/usr/bin/env python3
"""
Setup verification script.
Checks that all components are properly configured.
"""

import sys
import os
from pathlib import Path
import importlib

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_version():
    """Check Python version."""
    print("Checking Python version...", end=" ")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor} (requires 3.10+)")
        return False


def check_dependencies():
    """Check required dependencies are installed."""
    print("\nChecking dependencies...")
    
    required = [
        'pandas', 'psycopg2', 'sqlalchemy', 'google.generativeai',
        'pytest', 'dotenv', 'pydantic'
    ]
    
    missing = []
    for package in required:
        try:
            importlib.import_module(package.replace('.', '_') if '.' in package else package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    return True


def check_environment_variables():
    """Check environment variables."""
    print("\nChecking environment configuration...")
    
    from src.config import settings
    
    checks = {
        'GEMINI_API_KEY': settings.gemini_api_key,
        'DB_HOST': settings.db_host,
        'DB_ADMIN_USER': settings.db_admin_user,
        'DB_ADMIN_PASSWORD': settings.db_admin_password,
    }
    
    all_ok = True
    for key, value in checks.items():
        if value and value != "your_gemini_api_key_here" and value != "your_admin_password":
            print(f"  ✓ {key} is set")
        else:
            print(f"  ✗ {key} is not configured")
            all_ok = False
    
    if not all_ok:
        print("\n  Configure your .env file with actual credentials")
    
    return all_ok


def check_database_connection():
    """Check database connection."""
    print("\nChecking database connection...")
    
    try:
        from src.database import DatabaseManager
        
        db_manager = DatabaseManager(readonly=False)
        if db_manager.test_connection():
            print("  ✓ Database connection successful")
            return True
        else:
            print("  ✗ Database connection failed")
            return False
    
    except Exception as e:
        print(f"  ✗ Database connection error: {e}")
        return False


def check_database_schema():
    """Check database schema."""
    print("\nChecking database schema...")
    
    try:
        from src.database import DatabaseManager
        
        db_manager = DatabaseManager(readonly=False)
        schema_info = db_manager.get_schema_info()
        
        expected_tables = ['products', 'categories', 'orders', 'customers', 'employees']
        
        found_tables = list(schema_info.keys())
        missing_tables = [t for t in expected_tables if t not in found_tables]
        
        print(f"  Found {len(found_tables)} tables")
        
        if missing_tables:
            print(f"  ✗ Missing core tables: {', '.join(missing_tables)}")
            print(f"  Run: python scripts/setup_database.py")
            return False
        else:
            print(f"  ✓ All core tables present")
            return True
    
    except Exception as e:
        print(f"  ✗ Schema check error: {e}")
        return False


def check_data_file():
    """Check Northwind data file."""
    print("\nChecking data file...")
    
    data_file = Path(__file__).parent.parent / 'data' / 'raw' / 'northwind.xlsx'
    
    if data_file.exists():
        size_mb = data_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Data file found ({size_mb:.2f} MB)")
        return True
    else:
        print(f"  ✗ Data file not found: {data_file}")
        print(f"  Download with: python scripts/download_northwind.py")
        return False


def check_gemini_api():
    """Check Gemini API connection."""
    print("\nChecking Gemini API...")
    
    try:
        from src.text2sql_engine import Text2SQLEngine
        from src.config import settings
        
        if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
            print("  ✗ Gemini API key not configured")
            print("  Get API key from: https://ai.google.dev/")
            return False
        
        # Try to initialize (without actually calling API)
        engine = Text2SQLEngine()
        print("  ✓ Gemini API key configured")
        return True
    
    except ValueError as e:
        print(f"  ✗ {e}")
        return False
    except Exception as e:
        print(f"  ⚠ Warning: {e}")
        return True  # May be network issue, not critical


def check_project_structure():
    """Check project structure."""
    print("\nChecking project structure...")
    
    required_files = [
        'README.md',
        'requirements.txt',
        'setup.py',
        'pytest.ini',
        'src/__init__.py',
        'src/config.py',
        'src/database.py',
        'src/text2sql_engine.py',
        'src/query_validator.py',
        'src/data_loader.py',
        'tests/conftest.py',
        'tests/test_query_validator.py',
        'tests/test_accuracy/test_simple_queries.py',
        'data/schema/schema.sql',
    ]
    
    project_root = Path(__file__).parent.parent
    missing = []
    
    for file_path in required_files:
        if (project_root / file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path}")
            missing.append(file_path)
    
    if missing:
        print(f"\nMissing files: {len(missing)}")
        return False
    
    return True


def main():
    """Run all checks."""
    print("="*70)
    print("  Text2SQL Analytics System - Setup Verification")
    print("="*70)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment Variables", check_environment_variables),
        ("Project Structure", check_project_structure),
        ("Data File", check_data_file),
        ("Database Connection", check_database_connection),
        ("Database Schema", check_database_schema),
        ("Gemini API", check_gemini_api),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n  ✗ {name} check failed with error: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:8} {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Run tests: make test")
        print("  2. Run evaluation: make evaluate")
        print("  3. Try interactive mode: python -m src.cli")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  • Missing dependencies: pip install -r requirements.txt")
        print("  • Missing .env: cp env.example .env (then edit)")
        print("  • Database not setup: python scripts/setup_database.py")
        print("  • Data not downloaded: python scripts/download_northwind.py")
    
    print("\n" + "="*70)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

