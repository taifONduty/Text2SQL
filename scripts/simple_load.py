#!/usr/bin/env python3
"""Simple CSV loader using COPY command."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from src.config import settings

# Connect
conn = psycopg2.connect(settings.admin_database_url)
cur = conn.cursor()

# Load categories
cur.execute("DELETE FROM order_details; DELETE FROM orders; DELETE FROM products; DELETE FROM customers; DELETE FROM employees; DELETE FROM shippers; DELETE FROM categories;")

print("Loading categories...")
with open('data/raw/categories.csv', 'r') as f:
    next(f)  # Skip header
    cur.copy_from(f, 'categories', sep=',', columns=('category_id', 'category_name', 'description'))
print(f"✓ Loaded categories")

# Load customers  
print("Loading customers...")
with open('data/raw/customers.csv', 'r', encoding='latin-1') as f:
    next(f)
    cur.copy_from(f, 'customers', sep=',', columns=('customer_id', 'company_name', 'contact_name', 'contact_title', 'city', 'country'))
print(f"✓ Loaded customers")

# Load shippers
print("Loading shippers...")
with open('data/raw/shippers.csv', 'r') as f:
    next(f)
    cur.copy_from(f, 'shippers', sep=',', columns=('shipper_id', 'company_name'))
print(f"✓ Loaded shippers")

conn.commit()
cur.close()
conn.close()

print("\n✓ Data loading complete! Run 'python scripts/verify_data.py' to check.")
