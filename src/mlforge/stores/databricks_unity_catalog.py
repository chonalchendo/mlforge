"""
Databricks Unity Catalog storage backend.

Stores features as Delta Lake tables in Unity Catalog, enabling
governance, lineage, and access control.
"""

import json
import re
import tempfile
from pathlib import Path
from typing import Any, override

import polars as pl
from loguru import logger

import mlforge.manifest as manifest
import mlforge.results as results
import mlforge.version as version_utils
from mlforge.stores.base import Store

# Valid SQL identifier pattern (alphanumeric + underscore, not starting with digit)
_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str, field: str = "identifier") -> str:
    """Validate that a string is a safe SQL identifier.

    Args:
        name: The identifier to validate
        field: Field name for error messages

    Returns:
        The validated identifier

    Raises:
        ValueError: If the identifier contains unsafe characters
    """
    if not _IDENTIFIER_PATTERN.match(name):
        raise ValueError(
            f"Invalid {field}: '{name}'. "
            f"Must contain only alphanumeric characters and underscores, "
            f"and not start with a digit."
        )
    return name


def _escape_string(value: str) -> str:
    """Escape a string value for SQL.

    Escapes single quotes by doubling them.

    Args:
        value: String to escape

    Returns:
        Escaped string safe for SQL literals
    """
    return value.replace("'", "''")


class UnityCatalogStore(Store):
    """
    Unity Catalog offline store using Delta Lake.

    Stores features as Delta tables in Unity Catalog with automatic
    governance, lineage tracking, and access control.

    Storage layout:
        Unity Catalog:
        ├── {catalog} (catalog)
        │   └── {schema} (schema)
        │       ├── {feature_name} (Delta table)
        │       │   └── versions via Delta time travel
        │       └── _mlforge_metadata (Delta table)
        │           └── Tracks version mapping: mlforge semver → Delta version

    Versioning strategy:
        - User-facing: mlforge semver (1.0.0, 1.1.0, 2.0.0)
        - Storage: Delta table versions
        - Mapping: _mlforge_metadata table tracks the relationship

    Attributes:
        catalog: Unity Catalog catalog name
        schema: Schema (database) name within the catalog
        volume: Optional volume for artifacts (metadata, manifests)

    Example:
        store = UnityCatalogStore(
            catalog="main",
            schema="features",
        )

        # With Definitions
        defs = mlf.Definitions(
            name="my-project",
            features=[...],
            offline_store=store,
            engine="pyspark",
        )
    """

    def __init__(
        self,
        catalog: str,
        schema: str = "features",
        volume: str | None = None,
    ) -> None:
        """
        Initialize Unity Catalog store.

        Args:
            catalog: Unity Catalog catalog name.
            schema: Schema (database) name. Defaults to "features".
            volume: Optional volume for artifacts.

        Raises:
            ImportError: If pyspark is not available.
            RuntimeError: If no active SparkSession found.
            ValueError: If catalog or schema names are invalid.
        """
        self._catalog = _validate_identifier(catalog, "catalog")
        self._schema = _validate_identifier(schema, "schema")
        self._volume = (
            _validate_identifier(volume, "volume") if volume else None
        )
        self._spark = self._get_spark_session()

        # Ensure schema and metadata table exist
        self._ensure_schema_exists()
        self._ensure_metadata_table_exists()

    def _get_spark_session(self) -> Any:
        """Get active SparkSession.

        Returns:
            Active SparkSession

        Raises:
            ImportError: If pyspark is not installed.
            RuntimeError: If no active SparkSession found.
        """
        try:
            from pyspark.sql import SparkSession
        except ImportError as e:
            raise ImportError(
                "pyspark is required for UnityCatalogStore. "
                "Install it with: pip install mlforge[databricks]"
            ) from e

        session = SparkSession.getActiveSession()
        if session is None:
            raise RuntimeError(
                "No active SparkSession found.\n\n"
                "UnityCatalogStore requires an active SparkSession. "
                "This typically means you need to:\n"
                "  1. Run in a Databricks notebook or job\n"
                "  2. Use engine='pyspark' in your Definitions\n\n"
                "Example:\n"
                "    defs = mlf.Definitions(\n"
                "        name='my-project',\n"
                "        features=[...],\n"
                "        offline_store=mlf.UnityCatalogStore(catalog='main'),\n"
                "        engine='pyspark',\n"
                "    )"
            )
        return session

    def _ensure_schema_exists(self) -> None:
        """Create schema if it doesn't exist."""
        self._spark.sql(
            f"CREATE SCHEMA IF NOT EXISTS {self._catalog}.{self._schema}"
        )

    def _ensure_metadata_table_exists(self) -> None:
        """Create metadata table if it doesn't exist."""
        self._spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {self._full_metadata_table_name} (
                feature_name STRING,
                version STRING,
                delta_version LONG,
                schema_hash STRING,
                config_hash STRING,
                content_hash STRING,
                source_hash STRING,
                row_count LONG,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                columns STRING,
                features STRING,
                entity STRING,
                keys STRING,
                source STRING,
                timestamp_col STRING,
                interval STRING,
                tags STRING,
                description STRING,
                path STRING
            )
            USING DELTA
        """)

    @property
    def _full_schema_name(self) -> str:
        """Get full schema name (catalog.schema)."""
        return f"{self._catalog}.{self._schema}"

    @property
    def _full_metadata_table_name(self) -> str:
        """Get full metadata table name."""
        return f"{self._full_schema_name}._mlforge_metadata"

    def _table_name_for(self, feature_name: str) -> str:
        """Get full table name for a feature.

        Validates the feature name is a safe SQL identifier.
        """
        _validate_identifier(feature_name, "feature_name")
        return f"{self._full_schema_name}.{feature_name}"

    def _get_delta_version(
        self, feature_name: str, mlforge_version: str
    ) -> int | None:
        """Get Delta version for mlforge version.

        Args:
            feature_name: Feature name
            mlforge_version: mlforge semver string

        Returns:
            Delta table version, or None if not found
        """
        # Validate and escape inputs for SQL safety
        safe_name = _escape_string(feature_name)
        safe_version = _escape_string(mlforge_version)

        row = self._spark.sql(f"""
            SELECT delta_version
            FROM {self._full_metadata_table_name}
            WHERE feature_name = '{safe_name}' AND version = '{safe_version}'
        """).first()  # nosec B608 - inputs validated/escaped above

        if row is None:
            return None
        return row.delta_version

    def _get_current_delta_version(self, table_name: str) -> int:
        """Get current Delta table version after write."""
        history = self._spark.sql(
            f"DESCRIBE HISTORY {table_name} LIMIT 1"
        ).first()
        return history.version

    def _resolve_version(
        self, feature_name: str, feature_version: str | None
    ) -> str | None:
        """Resolve version to latest if None."""
        if feature_version is not None:
            return feature_version
        return self.get_latest_version(feature_name)

    @override
    def write(
        self,
        feature_name: str,
        result: results.ResultKind,
        feature_version: str,
    ) -> dict[str, Any]:
        """
        Write feature data to Unity Catalog Delta table.

        Args:
            feature_name: Unique identifier for the feature
            result: Engine result containing feature data
            feature_version: Semantic version string (e.g., "1.0.0")

        Returns:
            Metadata dictionary with table path, row count, and schema
        """
        table_name = self._table_name_for(feature_name)

        # Write to temporary parquet file, then load into Delta
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "data.parquet"
            result.write_parquet(temp_path)

            # Read into Spark and write as Delta table
            spark_df = self._spark.read.parquet(str(temp_path))
            (
                spark_df.write.format("delta")
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .saveAsTable(table_name)
            )

        # Get Delta version after write
        delta_version = self._get_current_delta_version(table_name)

        return {
            "path": table_name,
            "row_count": result.row_count(),
            "schema": result.schema(),
            "delta_version": delta_version,
        }

    @override
    def read(
        self,
        feature_name: str,
        feature_version: str | None = None,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """
        Read feature data from Unity Catalog Delta table.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to read. If None, reads latest.
            columns: Specific columns to read. If None, reads all columns.

        Returns:
            Feature data as a Polars DataFrame

        Raises:
            FileNotFoundError: If the feature/version doesn't exist
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            raise FileNotFoundError(
                f"Feature '{feature_name}' not found. Run 'mlforge build' first."
            )

        table_name = self._table_name_for(feature_name)

        # Get Delta version for this mlforge version
        delta_version = self._get_delta_version(feature_name, resolved)
        if delta_version is None:
            raise FileNotFoundError(
                f"Feature '{feature_name}' version '{resolved}' not found."
            )

        # Read with time travel
        spark_df = (
            self._spark.read.format("delta")
            .option("versionAsOf", delta_version)
            .table(table_name)
        )

        if columns:
            spark_df = spark_df.select(*columns)

        # Convert to Polars via PyArrow
        arrow_table = spark_df.toPandas()
        return pl.from_pandas(arrow_table)

    @override
    def exists(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> bool:
        """
        Check if feature version exists.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version to check. If None, checks any version.

        Returns:
            True if the feature/version exists, False otherwise
        """
        if feature_version is None:
            return len(self.list_versions(feature_name)) > 0

        delta_version = self._get_delta_version(feature_name, feature_version)
        return delta_version is not None

    @override
    def list_versions(self, feature_name: str) -> list[str]:
        """
        List all versions of a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Sorted list of version strings (oldest to newest)
        """
        safe_name = _escape_string(feature_name)

        rows = self._spark.sql(f"""
            SELECT version
            FROM {self._full_metadata_table_name}
            WHERE feature_name = '{safe_name}'
            ORDER BY created_at
        """).collect()  # nosec B608 - feature_name escaped above

        versions = [row.version for row in rows]
        return version_utils.sort_versions(versions)

    @override
    def get_latest_version(self, feature_name: str) -> str | None:
        """
        Get the latest version of a feature.

        Args:
            feature_name: Unique identifier for the feature

        Returns:
            Latest version string, or None if no versions exist
        """
        safe_name = _escape_string(feature_name)

        row = self._spark.sql(f"""
            SELECT version
            FROM {self._full_metadata_table_name}
            WHERE feature_name = '{safe_name}'
            ORDER BY created_at DESC
            LIMIT 1
        """).first()  # nosec B608 - feature_name escaped above

        if row is None:
            return None
        return row.version

    @override
    def path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> str:
        """
        Get the table path for a feature version.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, uses latest.

        Returns:
            Full table name (catalog.schema.table)
        """
        return self._table_name_for(feature_name)

    @override
    def metadata_path_for(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> str:
        """
        Get the metadata table path.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version (unused, metadata is centralized).

        Returns:
            Full metadata table name
        """
        return self._full_metadata_table_name

    @override
    def write_metadata(
        self,
        feature_name: str,
        metadata: manifest.FeatureMetadata,
    ) -> None:
        """
        Write feature metadata to centralized metadata table.

        Note: Must be called immediately after write() to ensure the
        delta_version from table history matches the written data.

        Args:
            feature_name: Unique identifier for the feature
            metadata: FeatureMetadata object to persist
        """
        # Get the delta_version from table history
        table_name = self._table_name_for(feature_name)
        delta_version = self._get_current_delta_version(table_name)

        # Serialize complex fields to JSON and escape for SQL safety
        columns_json = _escape_string(
            json.dumps(
                [c.to_dict() for c in metadata.columns]
                if metadata.columns
                else []
            )
        )
        features_json = _escape_string(
            json.dumps(
                [f.to_dict() for f in metadata.features]
                if metadata.features
                else []
            )
        )
        keys_json = _escape_string(json.dumps(metadata.keys))
        tags_json = _escape_string(
            json.dumps(metadata.tags if metadata.tags else [])
        )

        # Escape all string fields
        safe_name = _escape_string(feature_name)
        safe_version = _escape_string(metadata.version)
        safe_schema_hash = _escape_string(metadata.schema_hash)
        safe_config_hash = _escape_string(metadata.config_hash)
        safe_content_hash = _escape_string(metadata.content_hash)
        safe_source_hash = _escape_string(metadata.source_hash)
        safe_entity = _escape_string(metadata.entity)
        safe_source = _escape_string(metadata.source)
        safe_path = _escape_string(metadata.path)

        # Handle optional fields
        timestamp_sql = (
            f"'{_escape_string(metadata.timestamp)}'"
            if metadata.timestamp
            else "NULL"
        )
        interval_sql = (
            f"'{_escape_string(metadata.interval)}'"
            if metadata.interval
            else "NULL"
        )
        description_sql = (
            f"'{_escape_string(metadata.description)}'"
            if metadata.description
            else "NULL"
        )

        # Insert into metadata table
        self._spark.sql(f"""
            INSERT INTO {self._full_metadata_table_name}
            VALUES (
                '{safe_name}',
                '{safe_version}',
                {delta_version},
                '{safe_schema_hash}',
                '{safe_config_hash}',
                '{safe_content_hash}',
                '{safe_source_hash}',
                {metadata.row_count},
                current_timestamp(),
                current_timestamp(),
                '{columns_json}',
                '{features_json}',
                '{safe_entity}',
                '{keys_json}',
                '{safe_source}',
                {timestamp_sql},
                {interval_sql},
                '{tags_json}',
                {description_sql},
                '{safe_path}'
            )
        """)  # nosec B608 - all values escaped above

    @override
    def read_metadata(
        self,
        feature_name: str,
        feature_version: str | None = None,
    ) -> manifest.FeatureMetadata | None:
        """
        Read feature metadata from centralized metadata table.

        Args:
            feature_name: Unique identifier for the feature
            feature_version: Specific version. If None, reads latest.

        Returns:
            FeatureMetadata if exists, None otherwise
        """
        resolved = self._resolve_version(feature_name, feature_version)

        if resolved is None:
            return None

        safe_name = _escape_string(feature_name)
        safe_version = _escape_string(resolved)

        row = self._spark.sql(f"""
            SELECT *
            FROM {self._full_metadata_table_name}
            WHERE feature_name = '{safe_name}' AND version = '{safe_version}'
        """).first()  # nosec B608 - inputs escaped above

        if row is None:
            return None

        return self._row_to_metadata(row)

    def _row_to_metadata(self, row: Any) -> manifest.FeatureMetadata:
        """Convert a Spark Row to FeatureMetadata."""
        # Parse JSON fields
        columns_data = json.loads(row.columns) if row.columns else []
        features_data = json.loads(row.features) if row.features else []
        keys = json.loads(row.keys) if row.keys else []
        tags = json.loads(row.tags) if row.tags else []

        columns = [manifest.ColumnMetadata.from_dict(c) for c in columns_data]
        features = [manifest.ColumnMetadata.from_dict(f) for f in features_data]

        return manifest.FeatureMetadata(
            name=row.feature_name,
            version=row.version,
            path=row.path or "",
            entity=row.entity or "",
            keys=keys,
            source=row.source or "",
            row_count=row.row_count,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            content_hash=row.content_hash or "",
            schema_hash=row.schema_hash or "",
            config_hash=row.config_hash or "",
            source_hash=row.source_hash or "",
            timestamp=row.timestamp_col,
            interval=row.interval,
            columns=columns,
            features=features,
            tags=tags,
            description=row.description,
        )

    @override
    def list_metadata(self) -> list[manifest.FeatureMetadata]:
        """
        List metadata for latest version of all features.

        Returns:
            List of FeatureMetadata for all features (latest versions only)
        """
        # Get latest version per feature using window function
        rows = self._spark.sql(f"""
            WITH ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY feature_name
                        ORDER BY created_at DESC
                    ) as rn
                FROM {self._full_metadata_table_name}
            )
            SELECT * FROM ranked WHERE rn = 1
        """).collect()  # nosec B608 - table name uses validated identifiers

        metadata_list: list[manifest.FeatureMetadata] = []
        for row in rows:
            try:
                metadata_list.append(self._row_to_metadata(row))
            except Exception as e:
                logger.warning(
                    f"Failed to parse metadata for {row.feature_name}: {e}"
                )

        return metadata_list
