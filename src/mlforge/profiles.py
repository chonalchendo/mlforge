"""
Environment profiles for mlforge configuration.

This module provides YAML-based configuration for different environments
(dev, staging, production) with automatic store instantiation.

Example mlforge.yaml:
    default_profile: dev

    profiles:
      dev:
        offline_store:
          KIND: local
          path: ./feature_store

      production:
        offline_store:
          KIND: s3
          bucket: my-bucket
          prefix: features
        online_store:
          KIND: redis
          host: ${oc.env:REDIS_HOST}
          password: ${oc.env:REDIS_PASSWORD}
"""

from __future__ import annotations

import os
import typing as T
from pathlib import Path

from omegaconf import DictConfig, OmegaConf
from omegaconf.errors import InterpolationKeyError
from pydantic import BaseModel, Field, ValidationError

import mlforge.errors as errors
import mlforge.logging as log

if T.TYPE_CHECKING:
    import mlforge.stores as stores


# =============================================================================
# Offline Store Configs
# =============================================================================


class LocalStoreConfig(BaseModel, frozen=True):
    """Configuration for local filesystem store."""

    KIND: T.Literal["local"] = "local"
    path: str = "./feature_store"

    def create(self) -> stores.LocalStore:
        """Create store instance from this config."""
        import mlforge.stores as stores

        return stores.LocalStore(path=self.path)


class S3StoreConfig(BaseModel, frozen=True):
    """Configuration for S3 store."""

    KIND: T.Literal["s3"] = "s3"
    bucket: str
    prefix: str = ""
    region: str | None = None

    def create(self) -> stores.S3Store:
        """Create store instance from this config."""
        import mlforge.stores as stores

        return stores.S3Store(
            bucket=self.bucket,
            prefix=self.prefix,
            region=self.region,
        )


class GCSStoreConfig(BaseModel, frozen=True):
    """Configuration for Google Cloud Storage store."""

    KIND: T.Literal["gcs"] = "gcs"
    bucket: str
    prefix: str = ""

    def create(self) -> stores.GCSStore:
        """Create store instance from this config."""
        import mlforge.stores as stores

        return stores.GCSStore(
            bucket=self.bucket,
            prefix=self.prefix,
        )


class UnityCatalogStoreConfig(BaseModel, frozen=True):
    """
    Configuration for Databricks Unity Catalog store.

    When used with Databricks Connect (running locally), the Databricks
    config from the root mlforge.yaml will be used to create the SparkSession.

    Example mlforge.yaml:
        databricks:
          host: ${oc.env:DATABRICKS_HOST}
          token: ${oc.env:DATABRICKS_TOKEN}
          serverless: true

        profiles:
          dev:
            offline_store:
              KIND: unity-catalog
              catalog: dev_sandbox
              schema: features
    """

    KIND: T.Literal["unity-catalog"] = "unity-catalog"
    catalog: str
    schema_: str = Field(default="features", alias="schema")
    volume: str | None = None

    model_config = {"populate_by_name": True}

    def create(
        self,
        databricks_config: DatabricksComputeConfig | None = None,
    ) -> stores.UnityCatalogStore:
        """
        Create store instance from this config.

        Args:
            databricks_config: Optional Databricks config for creating
                SparkSession via Databricks Connect. If None, assumes
                we're running inside Databricks with an active session.

        Returns:
            UnityCatalogStore instance
        """
        import mlforge.stores as stores

        # If databricks_config provided, create session via Databricks Connect
        if databricks_config is not None:
            # Create the SparkSession - this makes it the active session
            databricks_config.create_spark_session()

        return stores.UnityCatalogStore(
            catalog=self.catalog,
            schema=self.schema_,
            volume=self.volume,
        )


# Discriminated union for offline stores
OfflineStoreConfig = T.Annotated[
    LocalStoreConfig | S3StoreConfig | GCSStoreConfig | UnityCatalogStoreConfig,
    Field(discriminator="KIND"),
]


# =============================================================================
# Online Store Configs
# =============================================================================


class RedisStoreConfig(BaseModel, frozen=True):
    """Configuration for Redis online store."""

    KIND: T.Literal["redis"] = "redis"
    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    password: str | None = None
    ttl: int | None = None
    prefix: str = "mlforge"

    def create(self) -> stores.RedisStore:
        """Create store instance from this config."""
        import mlforge.stores as stores

        return stores.RedisStore(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            ttl=self.ttl,
            prefix=self.prefix,
        )


class DynamoDBStoreConfig(BaseModel, frozen=True):
    """Configuration for DynamoDB online store."""

    KIND: T.Literal["dynamodb"] = "dynamodb"
    table_name: str
    region: str | None = None
    endpoint_url: str | None = None
    ttl_seconds: int | None = None
    auto_create: bool = True

    def create(self) -> stores.DynamoDBStore:
        """Create store instance from this config."""
        import mlforge.stores as stores

        return stores.DynamoDBStore(
            table_name=self.table_name,
            region=self.region,
            endpoint_url=self.endpoint_url,
            ttl_seconds=self.ttl_seconds,
            auto_create=self.auto_create,
        )


class DatabricksOnlineStoreConfig(BaseModel, frozen=True):
    """Configuration for Databricks Online Tables store."""

    KIND: T.Literal["databricks-online-tables"] = "databricks-online-tables"
    catalog: str
    schema_: str = Field(default="features_online", alias="schema")
    sync_mode: T.Literal["snapshot", "triggered", "continuous"] = "triggered"
    auto_create: bool = True
    warehouse_id: str | None = None

    model_config = {"populate_by_name": True}

    def create(self) -> stores.DatabricksOnlineStore:
        """Create store instance from this config."""
        import mlforge.stores as stores

        return stores.DatabricksOnlineStore(
            catalog=self.catalog,
            schema=self.schema_,
            sync_mode=self.sync_mode,
            auto_create=self.auto_create,
            warehouse_id=self.warehouse_id,
        )


# Discriminated union for online stores
OnlineStoreConfig = T.Annotated[
    RedisStoreConfig | DynamoDBStoreConfig | DatabricksOnlineStoreConfig,
    Field(discriminator="KIND"),
]


# =============================================================================
# Databricks Connection Config
# =============================================================================


class DatabricksComputeConfig(BaseModel, frozen=True):
    """
    Databricks compute configuration for Databricks Connect.

    Specifies how to connect to Databricks for PySpark execution.
    Supports serverless compute (recommended) or specific clusters.

    Example mlforge.yaml:
        databricks:
          host: ${oc.env:DATABRICKS_HOST}
          token: ${oc.env:DATABRICKS_TOKEN}
          serverless: true
    """

    host: str = Field(
        description="Databricks workspace hostname (without https://)"
    )
    token: str = Field(description="Personal access token")

    # Compute options (one of these should be set)
    serverless: bool = Field(
        default=True,
        description="Use serverless compute (recommended for dev)",
    )
    cluster_id: str | None = Field(
        default=None,
        description="Specific cluster ID (alternative to serverless)",
    )

    # SQL Connector settings (for DatabricksSQLEngine)
    http_path: str | None = Field(
        default=None,
        description="SQL Warehouse HTTP path (for SQL queries)",
    )

    def create_spark_session(self) -> "SparkSession":
        """
        Create a SparkSession via Databricks Connect.

        Returns:
            SparkSession connected to Databricks

        Raises:
            ImportError: If databricks-connect is not installed
            ValueError: If neither serverless nor cluster_id is configured
        """
        try:
            from databricks.connect import DatabricksSession
        except ImportError as e:
            raise ImportError(
                "databricks-connect is required for Databricks Connect.\n\n"
                "Install with:\n"
                "    pip install mlforge[databricks-connect]"
            ) from e

        # Ensure host doesn't have https:// prefix
        host = self.host.replace("https://", "").replace("http://", "")

        builder = DatabricksSession.builder.remote(
            host=f"https://{host}",
            token=self.token,
        )

        if self.serverless:
            builder = builder.serverless(True)
        elif self.cluster_id:
            builder = builder.clusterId(self.cluster_id)
        else:
            raise ValueError(
                "Databricks compute requires either serverless=true or cluster_id.\n\n"
                "Configure in mlforge.yaml:\n"
                "    databricks:\n"
                "      serverless: true  # Recommended\n"
                "      # OR\n"
                "      cluster_id: 0123-456789-abcdef"
            )

        return builder.getOrCreate()


# Backward compatibility alias
DatabricksConnectionConfig = DatabricksComputeConfig


# Type hint for SparkSession (only used in type hints)
if T.TYPE_CHECKING:
    from pyspark.sql import SparkSession


# =============================================================================
# Profile and Root Config
# =============================================================================


class ProfileConfig(BaseModel, frozen=True):
    """Configuration for a single profile."""

    offline_store: OfflineStoreConfig
    online_store: OnlineStoreConfig | None = None
    # Profile-level databricks config (overrides root-level)
    databricks: DatabricksComputeConfig | None = None


class MlforgeConfig(BaseModel, frozen=True):
    """Root configuration from mlforge.yaml."""

    default_profile: str = "dev"
    profiles: dict[str, ProfileConfig]
    databricks: DatabricksConnectionConfig | None = None


# =============================================================================
# Config Loading
# =============================================================================

CONFIG_FILENAME = "mlforge.yaml"


def load_config(config_path: Path | None = None) -> MlforgeConfig | None:
    """
    Load and validate mlforge.yaml configuration.

    Args:
        config_path: Path to config file. If None, searches for mlforge.yaml
                     in current directory.

    Returns:
        Validated MlforgeConfig, or None if no config file exists.

    Raises:
        ProfileError: If config file is invalid or env vars missing.
    """
    if config_path is None:
        config_path = Path(CONFIG_FILENAME)

    if not config_path.exists():
        return None

    # Load YAML with OmegaConf (handles ${oc.env:VAR} interpolation)
    try:
        loaded = OmegaConf.load(config_path)
        if not isinstance(loaded, DictConfig):
            raise errors.ProfileError(
                f"Expected YAML mapping in {config_path}, got list or scalar",
                hint="mlforge.yaml must be a YAML mapping with profiles key.",
            )
        omega_conf: DictConfig = loaded
    except errors.ProfileError:
        raise
    except Exception as e:
        raise errors.ProfileError(
            f"Failed to parse {config_path}: {e}",
            hint="Check that your mlforge.yaml is valid YAML syntax.",
        ) from e

    # Resolve all interpolations (environment variables)
    try:
        OmegaConf.resolve(omega_conf)
    except InterpolationKeyError as e:
        # Extract variable name from error message
        raise errors.ProfileError(
            f"Failed to resolve config variables: {e}",
            hint="Set the missing environment variable and try again.",
        ) from e
    except Exception as e:
        raise errors.ProfileError(
            f"Failed to resolve config variables: {e}",
        ) from e

    # Convert to dict for Pydantic validation
    config_dict = OmegaConf.to_container(omega_conf, resolve=True)

    # Validate with Pydantic
    try:
        return MlforgeConfig.model_validate(config_dict)
    except ValidationError as e:
        # Format Pydantic errors nicely
        error_lines = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msg = err["msg"]
            error_lines.append(f"  {loc}: {msg}")

        raise errors.ProfileError(
            f"Invalid configuration in {config_path}:\n"
            + "\n".join(error_lines),
            hint="Check the mlforge.yaml schema and fix the validation errors.",
        ) from e


def load_profile(
    name: str | None = None,
    config_path: Path | None = None,
) -> ProfileConfig:
    """
    Load a profile from mlforge.yaml.

    Profile resolution order:
    1. Explicit `name` parameter (highest priority)
    2. MLFORGE_PROFILE environment variable
    3. default_profile from mlforge.yaml

    Args:
        name: Profile name. If None, uses env var or config default.
        config_path: Path to config file. If None, uses mlforge.yaml.

    Returns:
        ProfileConfig with validated store configs.

    Raises:
        ProfileError: If no config file found, profile not found, or config invalid.
    """
    config = load_config(config_path)

    if config is None:
        raise errors.ProfileError(
            f"No {CONFIG_FILENAME} found.",
            hint=(
                "Either create mlforge.yaml or provide explicit "
                "offline_store to Definitions."
            ),
        )

    # Determine profile name (precedence: explicit > env var > default)
    if name is None:
        name = os.environ.get("MLFORGE_PROFILE", config.default_profile)

    # Get profile config
    if name not in config.profiles:
        available = list(config.profiles.keys())
        available_str = ", ".join(
            f"{p}{' (default)' if p == config.default_profile else ''}"
            for p in available
        )

        raise errors.ProfileError(
            f"Profile '{name}' not found.\n\nAvailable profiles: {available_str}",
            hint=f"Use one of the available profiles: mlforge build --profile {available[0]}",
        )

    return config.profiles[name]


def get_profile_info(
    config_path: Path | None = None,
) -> tuple[str, str, MlforgeConfig] | None:
    """
    Get current profile name, source, and config in one call.

    Args:
        config_path: Path to config file. If None, uses mlforge.yaml.

    Returns:
        Tuple of (profile_name, source, config) where source is "env" or "config",
        or None if no config file exists.
    """
    config = load_config(config_path)
    if config is None:
        return None

    if "MLFORGE_PROFILE" in os.environ:
        return os.environ["MLFORGE_PROFILE"], "env", config

    return config.default_profile, "config", config


# =============================================================================
# Profile Display and Validation
# =============================================================================


def print_store_config(config: ProfileConfig) -> None:
    """
    Print store configuration details to console.

    Args:
        config: Profile configuration to display.
    """
    offline = config.offline_store
    log.print_info("Offline Store:")
    log.print_info(f"  Type: {offline.KIND}")

    # Print fields that exist on this config type (excluding KIND)
    for field in offline.model_fields:
        if field == "KIND":
            continue
        value = getattr(offline, field)
        if value:  # Only print non-empty values
            log.print_info(f"  {field.replace('_', ' ').title()}: {value}")

    log.print_info("")
    if config.online_store:
        online = config.online_store
        log.print_info("Online Store:")
        log.print_info(f"  Type: {online.KIND}")
        for field in ["host", "port", "db"]:
            if hasattr(online, field):
                log.print_info(
                    f"  {field.replace('_', ' ').title()}: {getattr(online, field)}"
                )
    else:
        log.print_info("Online Store: not configured")


def validate_stores(config: ProfileConfig) -> None:
    """
    Validate store connectivity.

    Creates store instances and verifies they can be accessed.
    For LocalStore, ensures the directory can be created.
    For Redis, attempts a ping to verify connectivity.

    Args:
        config: Profile configuration to validate.

    Raises:
        ProfileError: If any store fails validation.
    """
    log.print_info("")
    log.print_info("Validating stores...")

    # Validate offline store
    try:
        store = config.offline_store.create()
        # For LocalStore, ensure directory can be created
        store_path = getattr(store, "path", None)
        if store_path is not None and hasattr(store_path, "mkdir"):
            store_path.mkdir(parents=True, exist_ok=True)
        log.print_success(f"  offline_store: {config.offline_store.KIND} - OK")
    except Exception as e:
        log.print_error(
            f"  offline_store: {config.offline_store.KIND} - FAILED"
        )
        log.print_error(f"    {e}")
        raise errors.ProfileError(
            f"Failed to validate offline_store ({config.offline_store.KIND}): {e}",
            hint="Check your store configuration and ensure the service is accessible.",
        ) from e

    # Validate online store
    if config.online_store:
        try:
            online_store = config.online_store.create()
            client = getattr(online_store, "_client", None)
            if client is not None:
                client.ping()
            log.print_success(
                f"  online_store: {config.online_store.KIND} - OK"
            )
        except Exception as e:
            log.print_error(
                f"  online_store: {config.online_store.KIND} - FAILED"
            )
            log.print_error(f"    {e}")
            raise errors.ProfileError(
                f"Failed to validate online_store ({config.online_store.KIND}): {e}",
                hint="Check your store configuration and ensure the service is running.",
            ) from e

    log.print_info("")
    log.print_success("Profile valid.")
