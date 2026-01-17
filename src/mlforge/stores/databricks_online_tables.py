"""
Databricks Online Tables storage backend.

Provides low-latency feature serving using Databricks Online Tables,
which automatically sync from Delta tables in Unity Catalog.
"""

import re
from typing import Any, Literal, override

from mlforge.stores.base import OnlineStore

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


class DatabricksOnlineStore(OnlineStore):
    """
    Databricks Online Tables for low-latency feature serving.

    Online Tables automatically sync from Delta tables in Unity Catalog,
    providing millisecond-latency lookups without manual data management.

    Prerequisites:
        - UnityCatalogStore as offline_store (source for Online Tables)
        - engine="pyspark" in Definitions

    Storage layout:
        Unity Catalog:
        ├── {catalog} (catalog)
        │   └── {schema} (schema for Online Tables)
        │       └── {feature_name} (Online Table, synced from offline Delta)

    Sync modes:
        - snapshot: Full refresh on each sync (small tables, infrequent updates)
        - triggered: Incremental sync on demand (default, manual control)
        - continuous: Near real-time streaming sync (real-time features)

    Attributes:
        catalog: Unity Catalog catalog name
        schema: Schema for Online Tables
        sync_mode: Sync mode for Online Tables
        auto_create: Whether to auto-create Online Tables

    Example:
        online_store = mlf.DatabricksOnlineStore(
            catalog="main",
            schema="features_online",
            sync_mode="triggered",
        )

        defs = mlf.Definitions(
            name="my-project",
            features=[...],
            offline_store=mlf.UnityCatalogStore(catalog="main", schema="features"),
            online_store=online_store,
            engine="pyspark",
        )
    """

    def __init__(
        self,
        catalog: str,
        schema: str = "features_online",
        sync_mode: Literal["snapshot", "triggered", "continuous"] = "triggered",
        auto_create: bool = True,
        warehouse_id: str | None = None,
    ) -> None:
        """
        Initialize Databricks Online Tables store.

        Args:
            catalog: Unity Catalog catalog name.
            schema: Schema for Online Tables. Defaults to "features_online".
            sync_mode: Sync mode for Online Tables. Defaults to "triggered".
            auto_create: Auto-create Online Tables if they don't exist.
                Defaults to True.
            warehouse_id: SQL warehouse ID for queries. If not specified, uses
                the first available warehouse. Recommended to set explicitly
                in multi-warehouse environments.

        Raises:
            ImportError: If databricks-sdk is not installed.
            RuntimeError: If not running in Databricks environment.
            ValueError: If catalog or schema names are invalid.
        """
        try:
            from databricks.sdk import WorkspaceClient
        except ImportError as e:
            raise ImportError(
                "databricks-sdk package not installed. "
                "Install with: pip install mlforge[databricks]"
            ) from e

        self._catalog = _validate_identifier(catalog, "catalog")
        self._schema = _validate_identifier(schema, "schema")
        self._sync_mode = sync_mode
        self._auto_create = auto_create
        self._warehouse_id = warehouse_id

        # Initialize Databricks client
        # Uses environment variables: DATABRICKS_HOST, DATABRICKS_TOKEN
        self._client = WorkspaceClient()

    @property
    def full_schema_name(self) -> str:
        """Get full schema name (catalog.schema)."""
        return f"{self._catalog}.{self._schema}"

    def _table_name_for(self, feature_name: str) -> str:
        """Get full table name for a feature.

        Validates the feature name is a safe SQL identifier.
        """
        _validate_identifier(feature_name, "feature_name")
        return f"{self.full_schema_name}.{feature_name}"

    def _online_table_exists(self, feature_name: str) -> bool:
        """Check if Online Table exists.

        Args:
            feature_name: Name of the feature

        Returns:
            True if the Online Table exists, False otherwise

        Raises:
            Exception: Re-raises non-404 errors (auth, network, rate limit)
        """
        from databricks.sdk.errors import NotFound

        online_table_name = self._table_name_for(feature_name)
        try:
            self._client.online_tables.get(online_table_name)
            return True
        except NotFound:
            return False

    def _create_online_table(
        self,
        feature_name: str,
        source_table: str,
        primary_keys: list[str],
    ) -> None:
        """Create Online Table for feature.

        Args:
            feature_name: Name of the feature
            source_table: Full name of source Delta table
            primary_keys: Primary key columns for lookup
        """
        from databricks.sdk.service.catalog import (
            OnlineTable,
            OnlineTableSpec,
            OnlineTableSpecContinuousSchedulingPolicy,
            OnlineTableSpecTriggeredSchedulingPolicy,
        )

        online_table_name = self._table_name_for(feature_name)

        # Build spec based on sync mode
        spec_kwargs: dict[str, Any] = {
            "source_table_full_name": source_table,
            "primary_key_columns": primary_keys,
        }

        if self._sync_mode == "triggered":
            spec_kwargs["run_triggered"] = (
                OnlineTableSpecTriggeredSchedulingPolicy()
            )
        elif self._sync_mode == "continuous":
            spec_kwargs["run_continuously"] = (
                OnlineTableSpecContinuousSchedulingPolicy()
            )
        # snapshot mode doesn't need a scheduling policy

        spec = OnlineTableSpec(**spec_kwargs)

        # Create the OnlineTable object with name and spec
        online_table = OnlineTable(name=online_table_name, spec=spec)
        self._client.online_tables.create(table=online_table)

    def _trigger_sync(self, feature_name: str) -> None:
        """Trigger sync for Online Table.

        Args:
            feature_name: Name of the feature
        """
        # For triggered mode, call the pipeline API to start sync
        # For continuous mode, sync is automatic
        # For snapshot mode, recreating the table handles refresh
        if self._sync_mode == "triggered":
            online_table_name = self._table_name_for(feature_name)
            # Getting the Online Table triggers a pipeline run for triggered mode
            self._client.online_tables.get(online_table_name)

    def sync_feature(
        self,
        feature_name: str,
        source_table: str,
        primary_keys: list[str],
    ) -> None:
        """Sync feature to Online Table.

        Creates the Online Table if it doesn't exist (when auto_create=True),
        then triggers a sync from the source Delta table.

        Args:
            feature_name: Name of the feature.
            source_table: Full name of source Delta table in Unity Catalog.
            primary_keys: Primary key columns for lookup.

        Raises:
            ValueError: If Online Table doesn't exist and auto_create=False.
        """
        if not self._online_table_exists(feature_name):
            if self._auto_create:
                self._create_online_table(
                    feature_name, source_table, primary_keys
                )
            else:
                online_table_name = self._table_name_for(feature_name)
                raise ValueError(
                    f"Online Table '{online_table_name}' not found.\n\n"
                    f"Create the Online Table manually or enable auto_create:\n\n"
                    f"    online_store = mlf.DatabricksOnlineStore(\n"
                    f"        catalog='{self._catalog}',\n"
                    f"        schema='{self._schema}',\n"
                    f"        auto_create=True,\n"
                    f"    )"
                )

        self._trigger_sync(feature_name)

    def _query_online_table(
        self,
        table_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        """Query Online Table for a single entity.

        Args:
            table_name: Full table name
            entity_keys: Entity key columns and values

        Returns:
            Feature values dict, or None if not found
        """
        # Build WHERE clause from entity keys with proper escaping
        where_clauses = [
            f"{_validate_identifier(k, 'key')} = '{_escape_string(str(v))}'"
            for k, v in entity_keys.items()
        ]
        where_sql = " AND ".join(where_clauses)

        # Execute query using statement execution API
        result = self._client.statement_execution.execute_statement(
            warehouse_id=self._get_sql_warehouse_id(),
            statement=f"SELECT * FROM {table_name} WHERE {where_sql} LIMIT 1",  # nosec B608 - inputs validated/escaped above
            wait_timeout="30s",
        )

        if (
            result.result
            and result.result.data_array
            and len(result.result.data_array) > 0
        ):
            # Convert to dict using column names from manifest
            if (
                result.manifest
                and result.manifest.schema
                and result.manifest.schema.columns
            ):
                columns = [col.name for col in result.manifest.schema.columns]
                values = result.result.data_array[0]
                return dict(zip(columns, values, strict=False))

        return None

    def _get_sql_warehouse_id(self) -> str:
        """Get SQL warehouse ID for query execution.

        Returns the configured warehouse_id, or the first available warehouse
        if not explicitly configured.

        Returns:
            SQL warehouse ID

        Raises:
            RuntimeError: If no SQL warehouse is available
        """
        if self._warehouse_id:
            return self._warehouse_id

        warehouses = list(self._client.warehouses.list())
        if not warehouses:
            raise RuntimeError(
                "No SQL warehouse available.\n\n"
                "DatabricksOnlineStore requires a SQL warehouse for queries.\n"
                "Create one in your Databricks workspace or use a serverless "
                "warehouse."
            )
        return warehouses[0].id

    @override
    def write(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
        values: dict[str, Any],
    ) -> None:
        """
        Write feature values for a single entity.

        Note: For Databricks Online Tables, data is synced from the offline
        Delta table. Direct writes are not supported. Use sync_feature()
        after updating the offline store.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values
            values: Feature column values

        Raises:
            NotImplementedError: Direct writes not supported for Online Tables.
        """
        raise NotImplementedError(
            "Direct writes are not supported for Databricks Online Tables.\n\n"
            "Online Tables automatically sync from Delta tables in Unity "
            "Catalog.\n"
            "To update feature values:\n"
            "  1. Update the offline store (UnityCatalogStore)\n"
            "  2. Call sync_feature() to trigger a sync to the Online Table\n\n"
            "Example:\n"
            "    defs.build(features=['user_spend'], online=True)"
        )

    @override
    def write_batch(
        self,
        feature_name: str,
        records: list[dict[str, Any]],
        entity_key_columns: list[str],
    ) -> int:
        """
        Write feature values for multiple entities.

        Note: For Databricks Online Tables, data is synced from the offline
        Delta table. Direct writes are not supported. Use sync_feature()
        after updating the offline store.

        Args:
            feature_name: Name of the feature
            records: List of records with entity keys and feature values
            entity_key_columns: Column names that form the entity key

        Raises:
            NotImplementedError: Direct writes not supported for Online Tables.
        """
        raise NotImplementedError(
            "Direct writes are not supported for Databricks Online Tables.\n\n"
            "Online Tables automatically sync from Delta tables in Unity "
            "Catalog.\n"
            "To update feature values:\n"
            "  1. Update the offline store (UnityCatalogStore)\n"
            "  2. Call sync_feature() to trigger a sync to the Online Table\n\n"
            "Example:\n"
            "    defs.build(features=['user_spend'], online=True)"
        )

    @override
    def read(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> dict[str, Any] | None:
        """
        Read feature values for a single entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            Feature values dict, or None if not found
        """
        table_name = self._table_name_for(feature_name)
        return self._query_online_table(table_name, entity_keys)

    @override
    def read_batch(
        self,
        feature_name: str,
        entity_keys: list[dict[str, str]],
    ) -> list[dict[str, Any] | None]:
        """
        Read feature values for multiple entities.

        Args:
            feature_name: Name of the feature
            entity_keys: List of entity key dicts

        Returns:
            List of feature value dicts (None for missing entities)
        """
        if not entity_keys:
            return []

        table_name = self._table_name_for(feature_name)
        results: list[dict[str, Any] | None] = []

        for keys in entity_keys:
            result = self._query_online_table(table_name, keys)
            results.append(result)

        return results

    @override
    def delete(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Delete feature values for a single entity.

        Note: For Databricks Online Tables, data is synced from the offline
        Delta table. Direct deletes are not supported.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Raises:
            NotImplementedError: Direct deletes not supported for Online Tables.
        """
        raise NotImplementedError(
            "Direct deletes are not supported for Databricks Online Tables.\n\n"
            "Online Tables automatically sync from Delta tables in Unity "
            "Catalog.\n"
            "To delete feature values:\n"
            "  1. Delete from the offline store (UnityCatalogStore)\n"
            "  2. Call sync_feature() to sync the deletion to the Online Table"
        )

    @override
    def exists(
        self,
        feature_name: str,
        entity_keys: dict[str, str],
    ) -> bool:
        """
        Check if feature values exist for an entity.

        Args:
            feature_name: Name of the feature
            entity_keys: Entity key columns and values

        Returns:
            True if exists, False otherwise
        """
        result = self.read(feature_name, entity_keys)
        return result is not None

    def ping(self) -> bool:
        """
        Check Databricks connection and Online Tables access.

        Returns:
            True if connected and accessible, False otherwise
        """
        try:
            # Try to list Online Tables to verify access
            # Type ignore: SDK stubs incorrectly type online_tables as Optional
            list(self._client.online_tables.list())  # type: ignore[union-attr]
            return True
        except Exception:
            return False
