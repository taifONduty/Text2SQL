#!/usr/bin/env python3
"""
Database setup script for Northwind database.
Creates schema, loads data, and sets up users.
"""

import sys
import logging
from pathlib import Path
from typing import Callable, Dict, Optional

import pandas as pd
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_database() -> None:
    """Create the Northwind database if it doesn't exist."""
    logger.info("Creating database...")

    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_admin_user,
        password=settings.db_admin_password,
        database="postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.db_name,))
    if not cursor.fetchone():
        cursor.execute(f"CREATE DATABASE {settings.db_name}")
        logger.info("Database '%s' created successfully", settings.db_name)
    else:
        logger.info("Database '%s' already exists", settings.db_name)

    cursor.close()
    conn.close()


def create_schema() -> None:
    """Create database schema from SQL file."""
    logger.info("Creating database schema...")

    schema_file = Path(__file__).parent.parent / "data" / "schema" / "schema.sql"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    conn = psycopg2.connect(settings.admin_database_url)
    cursor = conn.cursor()

    with open(schema_file, "r") as handle:
        schema_sql = handle.read()

    cursor.execute(schema_sql)
    conn.commit()

    logger.info("Schema created successfully")

    cursor.close()
    conn.close()


def _read_csv(path: Path) -> pd.DataFrame:
    encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode {path}")


def _split_employee_name(series: pd.Series, part: str) -> pd.Series:
    parts = series.fillna("").str.strip().str.split(" ", n=1, expand=True)
    if part == "first":
        return parts[0].replace("", None)
    return parts[1].replace("", None) if parts.shape[1] > 1 else None


def load_data() -> bool:
    """Load Northwind CSV files (already normalized) into PostgreSQL."""
    logger.info("Loading Northwind CSV data...")

    base_dir = Path(__file__).parent.parent / "data" / "raw"
    northwind_dir = base_dir / "northwind"

    if not northwind_dir.exists():
        logger.error("Northwind directory not found at %s", northwind_dir)
        return False

    from sqlalchemy import create_engine

    engine = create_engine(settings.admin_database_url)

    configs: Dict[str, Dict[str, Callable[[pd.Series], pd.Series]]] = {
        "categories": {
            "file": "categories.csv",
            "rename": {
                "categoryid": "category_id",
                "categoryname": "category_name",
                "description": "description",
            },
            "transforms": {},
        },
        "shippers": {
            "file": "shippers.csv",
            "rename": {
                "shipperid": "shipper_id",
                "companyname": "company_name",
                "phone": "phone",
            },
            "transforms": {},
        },
        "customers": {
            "file": "customers.csv",
            "rename": {
                "customerid": "customer_id",
                "companyname": "company_name",
                "contactname": "contact_name",
                "contacttitle": "contact_title",
                "address": "address",
                "city": "city",
                "region": "region",
                "postalcode": "postal_code",
                "country": "country",
                "phone": "phone",
                "fax": "fax",
            },
            "transforms": {},
        },
        "employees": {
            "file": "employees.csv",
            "rename": {
                "employeeid": "employee_id",
                "employeename": "employee_name",
                "title": "title",
                "city": "city",
                "country": "country",
                "reportsto": "reports_to",
            },
            "transforms": {
                "reports_to": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
            },
        },
        "products": {
            "file": "products.csv",
            "rename": {
                "productid": "product_id",
                "productname": "product_name",
                "quantityperunit": "quantity_per_unit",
                "unitprice": "unit_price",
                "discontinued": "discontinued",
                "categoryid": "category_id",
                "supplierid": "supplier_id",
                "unitsinstock": "units_in_stock",
                "unitsonorder": "units_on_order",
                "reorderlevel": "reorder_level",
            },
            "transforms": {
                "unit_price": lambda s: pd.to_numeric(s, errors="coerce"),
                "category_id": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "supplier_id": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "units_in_stock": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "units_on_order": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "reorder_level": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "discontinued": lambda s: pd.to_numeric(s, errors="coerce").fillna(0).astype(int).astype(bool),
            },
        },
        "orders": {
            "file": "orders.csv",
            "rename": {
                "orderid": "order_id",
                "customerid": "customer_id",
                "employeeid": "employee_id",
                "orderdate": "order_date",
                "requireddate": "required_date",
                "shippeddate": "shipped_date",
                "shipperid": "ship_via",
                "freight": "freight",
                "shipname": "ship_name",
                "shipaddress": "ship_address",
                "shipcity": "ship_city",
                "shipregion": "ship_region",
                "shippostalcode": "ship_postal_code",
                "shipcountry": "ship_country",
            },
            "transforms": {
                "order_id": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "employee_id": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "ship_via": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "order_date": lambda s: pd.to_datetime(s, errors="coerce"),
                "required_date": lambda s: pd.to_datetime(s, errors="coerce"),
                "shipped_date": lambda s: pd.to_datetime(s, errors="coerce"),
                "freight": lambda s: pd.to_numeric(s, errors="coerce"),
            },
        },
        "order_details": {
            "file": "order_details.csv",
            "rename": {
                "orderid": "order_id",
                "productid": "product_id",
                "unitprice": "unit_price",
                "quantity": "quantity",
                "discount": "discount",
            },
            "transforms": {
                "order_id": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "product_id": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
                "unit_price": lambda s: pd.to_numeric(s, errors="coerce"),
                "quantity": lambda s: pd.to_numeric(s, errors="coerce"),
                "discount": lambda s: pd.to_numeric(s, errors="coerce"),
            },
        },
    }

    loaded_tables = 0

    for table, cfg in configs.items():
        file_path = northwind_dir / cfg["file"]
        if not file_path.exists():
            logger.warning("%s not found at %s, skipping", table, file_path)
            continue

        logger.info("Loading %s...", file_path.name)
        df_raw = _read_csv(file_path)
        df_raw.columns = df_raw.columns.str.strip().str.lower()

        rename_map = cfg["rename"]
        df = df_raw.rename(columns=rename_map)
        missing_cols = [col for col in rename_map.values() if col not in df.columns]
        for col in missing_cols:
            df[col] = None

        for column, transformer in cfg["transforms"].items():
            if column in df.columns:
                df[column] = transformer(df[column])

        if table == "employees":
            df["first_name"] = _split_employee_name(df["employee_name"], "first")
            df["last_name"] = _split_employee_name(df["employee_name"], "last")
            df = df.drop(columns=["employee_name"])

        logger.info("Loading %d rows into %s...", len(df), table)
        try:
            df.to_sql(table, engine, if_exists="append", index=False, method="multi")
            logger.info("  ✓ Loaded %d rows into %s", len(df), table)
            loaded_tables += 1
        except Exception as exc:
            logger.error("  ✗ Failed to load %s: %s", table, exc)

    result_dir = base_dir / "result" / "Result.csv"
    if result_dir.exists():
        logger.info("Loading Result.csv supplemental table")
        df_result = _read_csv(result_dir)
        df_result.columns = df_result.columns.str.strip().str.lower().str.replace(" ", "_")
        try:
            df_result.to_sql("result", engine, if_exists="append", index=False, method="multi")
            loaded_tables += 1
            logger.info("  ✓ Loaded %d rows into result", len(df_result))
        except Exception as exc:
            logger.error("  ✗ Failed to load result: %s", exc)

    engine.dispose()

    if loaded_tables == 0:
        logger.error("No tables were loaded. Please verify CSV contents.")
        return False

    logger.info("Loaded %d tables into the database", loaded_tables)
    return True


def verify_setup() -> bool:
    """Verify database setup is correct."""
    logger.info("\nVerifying database setup...")
    try:
        conn = psycopg2.connect(settings.readonly_database_url)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
        )
        tables = cursor.fetchall()
        logger.info("\nFound %d tables:", len(tables))

        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            logger.info("  - %s: %d rows", table_name, count)

        cursor.close()
        conn.close()

        logger.info("\n✓ Database setup verified successfully!")
        return True
    except Exception as exc:  # pragma: no cover - setup script
        logger.error("✗ Verification failed: %s", exc)
        return False


def main() -> None:
    """Main setup function."""
    logger.info("=" * 60)
    logger.info("Northwind Database Setup")
    logger.info("=" * 60)

    try:
        create_database()
        create_schema()
        if not load_data():
            logger.warning("Data loading reported issues. Continuing to verification.")
        verify_setup()

        logger.info("\n" + "=" * 60)
        logger.info("Setup completed successfully!")
        logger.info("=" * 60)
    except Exception as exc:  # pragma: no cover - setup script
        logger.error("Setup failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
