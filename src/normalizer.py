"""Utility classes for robust CSV ingestion and schema profiling.

This module introduces a configurable ingestion layer capable of loading
heterogeneous CSV exports and performing lightweight profiling to
support downstream normalization workflows.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_float_dtype,
    is_integer_dtype,
)

from .database import DatabaseManager


logger = logging.getLogger(__name__)


DEFAULT_ENCODINGS: Tuple[str, ...] = (
    "utf-8",
    "utf-8-sig",
    "latin1",
    "cp1252",
)


@dataclass
class CsvTable:
    """Container for a loaded CSV dataset."""

    name: str
    dataframe: pd.DataFrame
    source_path: Path
    encoding: str
    delimiter: str
    quotechar: str


@dataclass
class ColumnProfile:
    """Summary statistics for a column used during schema inference."""

    name: str
    dtype: str
    non_null_count: int
    null_ratio: float
    distinct_values: int
    sample_values: List[Any] = field(default_factory=list)


@dataclass
class TableProfile:
    """Profile for a CSV table capturing key inferences."""

    name: str
    row_count: int
    column_profiles: List[ColumnProfile]
    candidate_keys: List[List[str]]
    probable_foreign_keys: List[str]


class CsvIngestionEngine:
    """Loads CSV files with basic dialect and encoding detection."""

    def __init__(
        self,
        base_path: Path,
        recursive: bool = True,
        explicit_tables: Optional[Iterable[Path]] = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.recursive = recursive
        self.explicit_tables = [Path(p) for p in explicit_tables] if explicit_tables else None

    def load(self) -> Dict[str, CsvTable]:
        """Load CSV files from the configured base path."""
        if self.explicit_tables:
            candidates = [self._resolve_path(p) for p in self.explicit_tables]
        else:
            candidates = self._discover_csv_files()

        tables: Dict[str, CsvTable] = {}
        for file_path in candidates:
            try:
                table = self._load_file(file_path)
            except Exception as exc:  # pragma: no cover - logged for visibility
                logger.exception("Failed to load %s: %s", file_path, exc)
                continue

            name = self._derive_table_name(file_path)
            tables[name] = table
            logger.info(
                "Loaded CSV table %s (rows=%s, cols=%s, delimiter='%s', encoding=%s)",
                name,
                table.dataframe.shape[0],
                table.dataframe.shape[1],
                table.delimiter,
                table.encoding,
            )

        return tables

    def _discover_csv_files(self) -> List[Path]:
        """Return a sorted list of CSV files under the base path."""
        if self.base_path.is_file():
            return [self.base_path]

        glob_pattern = "**/*.csv" if self.recursive else "*.csv"
        files = sorted(self.base_path.glob(glob_pattern))
        if not files:
            logger.warning("No CSV files found in %s", self.base_path)
        return files

    def _resolve_path(self, path: Path) -> Path:
        resolved = path if path.is_absolute() else (self.base_path / path)
        if not resolved.exists():
            raise FileNotFoundError(f"CSV file not found: {resolved}")
        return resolved

    def _load_file(self, file_path: Path) -> CsvTable:
        encoding = self._detect_encoding(file_path)
        delimiter, quotechar = self._detect_dialect(file_path, encoding)

        read_kwargs = {
            "sep": delimiter,
            "quotechar": quotechar,
            "encoding": encoding,
            "engine": "python",  # python engine handles flexible delimiters better
            "dtype_backend": "numpy_nullable",
        }

        try:
            df = pd.read_csv(file_path, **read_kwargs)
        except ValueError as exc:
            if "bad delimiter" not in str(exc).lower():
                raise

            fallback_kwargs = {
                **read_kwargs,
                "sep": None,
            }
            df = pd.read_csv(file_path, **fallback_kwargs)
        df = self._standardize_columns(df)

        return CsvTable(
            name=self._derive_table_name(file_path),
            dataframe=df,
            source_path=file_path,
            encoding=encoding,
            delimiter=delimiter,
            quotechar=quotechar,
        )

    def _detect_encoding(self, file_path: Path) -> str:
        for encoding in DEFAULT_ENCODINGS:
            try:
                with open(file_path, "r", encoding=encoding) as handle:
                    handle.read(4096)
                return encoding
            except UnicodeDecodeError:
                continue
        logger.warning("Falling back to utf-8 for %s", file_path)
        return "utf-8"

    def _detect_dialect(self, file_path: Path, encoding: str) -> Tuple[str, str]:
        try:
            with open(file_path, "r", encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                sniff = csv.Sniffer().sniff(sample)
                delimiter = getattr(sniff, "delimiter", ",")
                quotechar = getattr(sniff, "quotechar", '"')

                if not delimiter or len(delimiter) != 1:
                    raise ValueError("invalid delimiter detected")
                if not quotechar or len(quotechar) != 1:
                    quotechar = '"'

                return delimiter, quotechar
        except Exception:
            return ",", '"'

    def _derive_table_name(self, file_path: Path) -> str:
        return file_path.stem.lower().replace(" ", "_")

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [self._normalize_name(col) for col in df.columns]
        return df

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip().lower().replace(" ", "_")
        normalized = normalized.replace("-", "_").replace("/", "_")
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        return normalized.strip("_")


class SchemaProfiler:
    """Compute lightweight statistics for CSV tables to inform normalization."""

    def __init__(self, max_combination_columns: int = 2) -> None:
        self.max_combination_columns = max_combination_columns

    def profile(self, tables: Dict[str, CsvTable]) -> Dict[str, TableProfile]:
        profiles: Dict[str, TableProfile] = {}
        for name, table in tables.items():
            df = table.dataframe
            column_profiles = [self._profile_column(df, col) for col in df.columns]
            candidate_keys = self._find_candidate_keys(df)
            probable_fks = self._find_probable_foreign_keys(df)
            profiles[name] = TableProfile(
                name=name,
                row_count=df.shape[0],
                column_profiles=column_profiles,
                candidate_keys=candidate_keys,
                probable_foreign_keys=probable_fks,
            )
        return profiles

    def _profile_column(self, df: pd.DataFrame, column: str) -> ColumnProfile:
        series = df[column]
        non_null_count = int(series.notna().sum())
        null_ratio = 1.0 - (non_null_count / max(len(series), 1))
        distinct_values = int(series.nunique(dropna=True))
        sample_values = series.dropna().astype(str).head(5).tolist()
        return ColumnProfile(
            name=column,
            dtype=str(series.dtype),
            non_null_count=non_null_count,
            null_ratio=null_ratio,
            distinct_values=distinct_values,
            sample_values=sample_values,
        )

    def _find_candidate_keys(self, df: pd.DataFrame) -> List[List[str]]:
        candidate_keys: List[List[str]] = []
        for column in df.columns:
            series = df[column]
            if series.is_unique and series.notna().all():
                candidate_keys.append([column])

        if candidate_keys:
            return candidate_keys

        limited_columns = list(df.columns[: min(len(df.columns), 8)])
        for i, col_a in enumerate(limited_columns):
            for col_b in limited_columns[i + 1 :]:
                subset = df[[col_a, col_b]].dropna()
                if not subset.empty and not subset.duplicated().any():
                    candidate_keys.append([col_a, col_b])
                    if len(candidate_keys) >= 3:
                        return candidate_keys
        return candidate_keys

    def _find_probable_foreign_keys(self, df: pd.DataFrame) -> List[str]:
        probable = []
        for column in df.columns:
            if column.endswith("_id") and df[column].notna().any():
                probable.append(column)
        return probable


@dataclass
class ForeignKeySpec:
    """Foreign key metadata used for table creation."""

    column: str
    ref_table: str
    ref_column: str


@dataclass
class NormalizedTable:
    """Represents a table ready for persistence in a relational database."""

    name: str
    dataframe: pd.DataFrame
    primary_key: List[str]
    foreign_keys: List[ForeignKeySpec] = field(default_factory=list)
    source_tables: List[str] = field(default_factory=list)


class NormalizationEngine:
    """Heuristic pipeline that decomposes CSV datasets towards 3NF."""

    def __init__(
        self,
        tables: Dict[str, CsvTable],
        profiles: Optional[Dict[str, TableProfile]] = None,
    ) -> None:
        self.tables = tables
        self.profiles = profiles or SchemaProfiler().profile(tables)
        self.dimension_tables: Dict[str, NormalizedTable] = {}

    def normalize(self) -> Dict[str, NormalizedTable]:
        normalized: Dict[str, NormalizedTable] = {}

        for table_name, csv_table in self.tables.items():
            profile = self.profiles[table_name]
            base_df = csv_table.dataframe.copy()

            primary_key, base_df = self._ensure_primary_key(table_name, base_df, profile)
            dimensions, fact_df = self._extract_dimension_tables(table_name, base_df, primary_key)

            for dim_name, dim_table in dimensions.items():
                if dim_name in self.dimension_tables:
                    existing = self.dimension_tables[dim_name]
                    merged = pd.concat([existing.dataframe, dim_table.dataframe], ignore_index=True)
                    self.dimension_tables[dim_name].dataframe = merged.drop_duplicates().reset_index(drop=True)
                    self.dimension_tables[dim_name].source_tables.extend(dim_table.source_tables)
                else:
                    self.dimension_tables[dim_name] = dim_table

            normalized[table_name] = NormalizedTable(
                name=table_name,
                dataframe=fact_df.reset_index(drop=True),
                primary_key=primary_key,
                foreign_keys=[],
                source_tables=[table_name],
            )

        all_tables = {**self.dimension_tables, **normalized}
        self._register_foreign_keys(all_tables)
        self._enforce_referential_integrity(all_tables)

        return all_tables

    def _ensure_primary_key(
        self,
        table_name: str,
        df: pd.DataFrame,
        profile: TableProfile,
    ) -> Tuple[List[str], pd.DataFrame]:
        if not profile.candidate_keys:
            surrogate = f"{table_name}_id"
            if surrogate in df.columns and not df[surrogate].is_unique:
                surrogate = f"{table_name}_surrogate_id"
            df[surrogate] = pd.Series(range(1, len(df) + 1), dtype="Int64")
            return [surrogate], df

        ranked_candidates = sorted(
            profile.candidate_keys,
            key=lambda cols: (
                0 if any(col == "id" for col in cols) else 1,
                0 if any(col == f"{table_name}_id" for col in cols) else 1,
                len(cols),
            ),
        )

        chosen = ranked_candidates[0]
        missing_cols = [col for col in chosen if col not in df.columns]
        if missing_cols:
            surrogate = f"{table_name}_id"
            df[surrogate] = pd.Series(range(1, len(df) + 1), dtype="Int64")
            return [surrogate], df

        for col in chosen:
            if df[col].isnull().any():
                df[col] = df[col].astype("object")
                missing_indices = df.index[df[col].isnull()].tolist()
                replacements = [
                    f"{table_name}_{col}_missing_{i}"
                    for i, _ in enumerate(missing_indices, start=1)
                ]
                for idx, value in zip(missing_indices, replacements):
                    df.at[idx, col] = value

        return chosen, df

    def _extract_dimension_tables(
        self,
        table_name: str,
        df: pd.DataFrame,
        primary_key: List[str],
    ) -> Tuple[Dict[str, NormalizedTable], pd.DataFrame]:
        df = df.copy()
        dimensions: Dict[str, NormalizedTable] = {}

        for column in list(df.columns):
            if column in primary_key:
                continue
            if not column.endswith("_id"):
                continue

            prefix = column[:-3]
            related_columns = [col for col in df.columns if col.startswith(f"{prefix}_")]
            non_id_columns = [col for col in related_columns if col != column]

            if not non_id_columns:
                continue

            dim_name = f"{prefix}_dimension"
            dim_df = df[[column] + non_id_columns].drop_duplicates().reset_index(drop=True)
            dim_df = dim_df.dropna(subset=[column])
            if dim_df.empty:
                continue
            dimensions[dim_name] = NormalizedTable(
                name=dim_name,
                dataframe=dim_df,
                primary_key=[column],
                foreign_keys=[],
                source_tables=[table_name],
            )

            df = df.drop(columns=non_id_columns)

        return dimensions, df

    def _register_foreign_keys(self, tables: Dict[str, NormalizedTable]) -> None:
        id_registry: Dict[str, List[str]] = {}
        for table in tables.values():
            for pk_column in table.primary_key:
                id_registry.setdefault(pk_column, []).append(table.name)

        for table in tables.values():
            df = table.dataframe
            for column in df.columns:
                if column in table.primary_key:
                    continue
                if not column.endswith("_id"):
                    continue

                referenced_tables = [t for t in id_registry.get(column, []) if t != table.name]
                if not referenced_tables:
                    continue

                target_table = referenced_tables[0]
                if any(
                    fk.column == column and fk.ref_table == target_table for fk in table.foreign_keys
                ):
                    continue

                table.foreign_keys.append(
                    ForeignKeySpec(column=column, ref_table=target_table, ref_column=column)
                )

    def _enforce_referential_integrity(self, tables: Dict[str, NormalizedTable]) -> None:
        for table in tables.values():
            df = table.dataframe
            for fk in table.foreign_keys:
                ref_table = tables.get(fk.ref_table)
                if not ref_table:
                    continue
                valid_values = ref_table.dataframe[fk.ref_column].dropna().unique()
                df = df[df[fk.column].isna() | df[fk.column].isin(valid_values)]
            table.dataframe = df.reset_index(drop=True)


class PostgresLoader:
    """Persist normalized tables into PostgreSQL using DatabaseManager."""

    def __init__(self, db_manager: DatabaseManager, schema: str = "public") -> None:
        self.db_manager = db_manager
        self.schema = schema

    def materialize(
        self,
        tables: Dict[str, NormalizedTable],
        drop_existing: bool = False,
    ) -> None:
        with self.db_manager.get_connection() as connection:
            with connection.cursor() as cursor:
                if drop_existing:
                    for table_name in tables:
                        cursor.execute(
                            f"DROP TABLE IF EXISTS {self.schema}.{table_name} CASCADE"
                        )

                for table in tables.values():
                    create_sql = self._build_create_table_sql(table)
                    cursor.execute(create_sql)

                for table in tables.values():
                    self._copy_table(cursor, table)

            connection.commit()

    def _build_create_table_sql(self, table: NormalizedTable) -> str:
        column_definitions = []
        for column in table.dataframe.columns:
            sql_type = self._map_dtype(table.dataframe[column])
            nullable = "NOT NULL" if column in table.primary_key else ""
            column_definitions.append(f"{column} {sql_type} {nullable}".strip())

        pk_clause = f", PRIMARY KEY ({', '.join(table.primary_key)})" if table.primary_key else ""

        fk_clauses = []
        for fk in table.foreign_keys:
            fk_clauses.append(
                f", FOREIGN KEY ({fk.column}) REFERENCES {self.schema}.{fk.ref_table} ({fk.ref_column})"
            )

        columns_sql = ",\n    ".join(column_definitions)
        fk_sql = "".join(fk_clauses)
        return (
            f"CREATE TABLE IF NOT EXISTS {self.schema}.{table.name} (\n    {columns_sql}{pk_clause}{fk_sql}\n)"
        )

    def _copy_table(self, cursor, table: NormalizedTable) -> None:
        buffer = StringIO()
        table.dataframe.to_csv(buffer, index=False, header=False, na_rep="\\N")
        buffer.seek(0)
        columns_sql = ", ".join(table.dataframe.columns)
        copy_sql = (
            f"COPY {self.schema}.{table.name} ({columns_sql}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
        )
        cursor.copy_expert(copy_sql, buffer)

    @staticmethod
    def _map_dtype(series: pd.Series) -> str:
        if is_integer_dtype(series.dtype):
            return "BIGINT"
        if is_float_dtype(series.dtype):
            return "DOUBLE PRECISION"
        if is_bool_dtype(series.dtype):
            return "BOOLEAN"
        if is_datetime64_any_dtype(series.dtype):
            return "TIMESTAMP"
        return "TEXT"


def build_normalized_database(
    source_path: Path,
    db_manager: DatabaseManager,
    recursive: bool = True,
    drop_existing: bool = False,
) -> Dict[str, NormalizedTable]:
    """High-level helper to ingest CSV files and materialize them in PostgreSQL."""

    ingestion = CsvIngestionEngine(base_path=source_path, recursive=recursive)
    tables = ingestion.load()
    if not tables:
        raise ValueError(f"No CSV files found under {source_path}")

    profiler = SchemaProfiler()
    profiles = profiler.profile(tables)

    engine = NormalizationEngine(tables, profiles)
    normalized_tables = engine.normalize()

    loader = PostgresLoader(db_manager=db_manager)
    loader.materialize(normalized_tables, drop_existing=drop_existing)

    return normalized_tables
