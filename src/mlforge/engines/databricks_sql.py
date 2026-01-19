"""
Databricks SQL Connector engine for ad-hoc queries.

This module provides DatabricksSQLEngine for executing SQL queries
directly on Databricks SQL Warehouses via the SQL Connector.

Note: For building features with PySpark transformations, use
PySparkEngine with Databricks Connect instead. This engine is
for SQL-only queries and ad-hoc exploration.
"""

from typing import TYPE_CHECKING, Any, override

import mlforge.engines.base as base
import mlforge.errors as errors
import mlforge.results as results_

if TYPE_CHECKING:
    import mlforge.core as core
    import mlforge.profiles as profiles


class DatabricksSQLEngine(base.Engine):
    """
    Databricks SQL Connector engine for ad-hoc queries.

    Executes SQL queries directly on Databricks SQL Warehouses via the
    SQL Connector. Useful for quick data exploration and validation.

    For building features with PySpark transformations, use PySparkEngine
    with Databricks Connect instead.

    Attributes:
        _config: Databricks connection configuration
        _connection: SQL Connector connection (lazily created)

    Example:
        engine = DatabricksSQLEngine(
            host="your-workspace.cloud.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
            token="dapi_xxx",
        )

        # Execute ad-hoc SQL query
        result = engine.query("SELECT * FROM catalog.schema.table LIMIT 10")
        df = result.to_polars()
    """

    def __init__(
        self,
        config: "profiles.DatabricksConnectionConfig | None" = None,
        host: str | None = None,
        http_path: str | None = None,
        token: str | None = None,
    ) -> None:
        """
        Initialize Databricks engine.

        Args:
            config: Databricks connection config from profile.
            host: Databricks workspace hostname (overrides config).
            http_path: SQL Warehouse HTTP path (overrides config).
            token: Personal access token (overrides config).

        Raises:
            ImportError: If databricks-sql-connector is not installed.
            ValueError: If required connection parameters are missing.
        """
        self._verify_connector_installed()

        # Build connection parameters from config + overrides
        self._host = host or (config.host if config else None)
        self._http_path = http_path or (config.http_path if config else None)
        self._token = token or (config.token if config else None)

        if not all([self._host, self._http_path, self._token]):
            raise ValueError(
                "Databricks connection requires host, http_path, and token.\n\n"
                "Set via environment variables:\n"
                "    export DATABRICKS_HOST=https://company.cloud.databricks.com\n"
                "    export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/abc123\n"
                "    export DATABRICKS_TOKEN=dapi_xxxxx\n\n"
                "Or configure in mlforge.yaml:\n"
                "    databricks:\n"
                "      host: ${oc.env:DATABRICKS_HOST}\n"
                "      http_path: ${oc.env:DATABRICKS_HTTP_PATH}\n"
                "      token: ${oc.env:DATABRICKS_TOKEN}"
            )

        self._connection: Any | None = None

    def _verify_connector_installed(self) -> None:
        """Verify databricks-sql-connector is installed."""
        try:
            import databricks.sql  # noqa: F401
        except ImportError:
            raise ImportError(
                "databricks-sql-connector is required for DatabricksSQLEngine.\n\n"
                "Install with:\n"
                "    pip install mlforge[databricks-sql]"
            )

    def _get_connection(self) -> Any:
        """Get or create SQL Connector connection."""
        if self._connection is None:
            from databricks import sql

            self._connection = sql.connect(
                server_hostname=self._host,
                http_path=self._http_path,
                access_token=self._token,
            )
        return self._connection

    def close(self) -> None:
        """Close the SQL Connector connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def query(self, sql: str) -> results_.DatabricksSQLResult:
        """
        Execute an ad-hoc SQL query.

        Args:
            sql: SQL query to execute

        Returns:
            DatabricksSQLResult containing the query results

        Example:
            engine = DatabricksSQLEngine(...)
            result = engine.query("SELECT * FROM catalog.schema.table LIMIT 10")
            df = result.to_polars()
        """
        return self._execute_sql("ad_hoc_query", sql)

    @override
    def execute(self, feature: "core.Feature") -> results_.ResultKind:
        """
        Execute a SQL-defined feature.

        Calls the feature function to get a SQL string, substitutes the
        {source} placeholder, and executes via SQL Connector.

        Args:
            feature: Feature definition to execute

        Returns:
            DatabricksSQLResult containing the query result

        Raises:
            TypeError: If feature function doesn't return a SQL string
            FeatureMaterializationError: If SQL execution fails
        """
        source = feature.source_obj

        # Verify source is Unity Catalog table
        if not source.is_unity_catalog:
            raise errors.FeatureMaterializationError(
                feature_name=feature.name,
                message=(
                    f"DatabricksSQLEngine requires Unity Catalog source, "
                    f"got {source.location} source"
                ),
                hint=(
                    "Use Source(table='catalog.schema.table') for SQL features, "
                    "or use PySparkEngine with Databricks Connect for PySpark features."
                ),
            )

        # Call feature function to get SQL string
        # SQL features take no arguments, regular features take a df
        import inspect

        sig = inspect.signature(feature.fn)
        if len(sig.parameters) == 0:
            # No-arg SQL feature function
            result = feature.fn()  # type: ignore[call-arg]
        else:
            raise errors.FeatureMaterializationError(
                feature_name=feature.name,
                message=(
                    "SQL feature functions for Unity Catalog must take no arguments"
                ),
                hint=(
                    "Define your feature like:\n"
                    f"    @feature(source=Source(table='catalog.schema.table'), keys=['id'])\n"
                    f"    def {feature.name}():\n"
                    f'        return "SELECT id, SUM(amount) FROM {{source}} GROUP BY id"'  # nosec B608
                ),
            )

        if not isinstance(result, str):
            raise TypeError(
                f"Feature '{feature.name}' must return SQL string for Unity Catalog sources, "
                f"got {type(result).__name__}.\n\n"
                f"Example:\n"
                f"    @feature(source=Source(table='main.schema.table'), keys=['id'])\n"
                f"    def {feature.name}():\n"
                f'        return "SELECT id, SUM(amount) FROM {{source}} GROUP BY id"'  # nosec B608
            )

        # Substitute {source} placeholder with table name
        sql_query = result.format(source=source.table)

        # Execute SQL and return result
        return self._execute_sql(feature.name, sql_query)

    def _execute_sql(
        self,
        feature_name: str,
        sql_query: str,
    ) -> results_.DatabricksSQLResult:
        """
        Execute SQL query and return result.

        Args:
            feature_name: Feature name for error context
            sql_query: SQL query to execute

        Returns:
            DatabricksSQLResult wrapping the query results

        Raises:
            FeatureMaterializationError: If SQL execution fails
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql_query)

                # Get column names from cursor description
                columns = [desc[0] for desc in cursor.description]

                # Fetch all results
                rows = cursor.fetchall()

                return results_.DatabricksSQLResult(
                    columns=columns,
                    rows=rows,
                    sql=sql_query,
                )

        except Exception as e:
            raise errors.FeatureMaterializationError(
                feature_name=feature_name,
                message=f"SQL execution failed: {e}",
                hint=(
                    "Check your SQL syntax and ensure the table exists.\n"
                    f"SQL:\n{sql_query}"
                ),
            ) from e
