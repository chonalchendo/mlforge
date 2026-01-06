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

if T.TYPE_CHECKING:
    import mlforge.online as online_
    import mlforge.store as store_


# =============================================================================
# Offline Store Configs
# =============================================================================


class LocalStoreConfig(BaseModel, frozen=True):
    """Configuration for local filesystem store."""

    KIND: T.Literal["local"] = "local"
    path: str = "./feature_store"

    def create(self) -> store_.LocalStore:
        """Create store instance from this config."""
        import mlforge.store as store_

        return store_.LocalStore(path=self.path)


class S3StoreConfig(BaseModel, frozen=True):
    """Configuration for S3 store."""

    KIND: T.Literal["s3"] = "s3"
    bucket: str
    prefix: str = ""
    region: str | None = None

    def create(self) -> store_.S3Store:
        """Create store instance from this config."""
        import mlforge.store as store_

        return store_.S3Store(
            bucket=self.bucket,
            prefix=self.prefix,
            region=self.region,
        )


class GCSStoreConfig(BaseModel, frozen=True):
    """Configuration for Google Cloud Storage store."""

    KIND: T.Literal["gcs"] = "gcs"
    bucket: str
    prefix: str = ""

    def create(self) -> store_.Store:
        """Create store instance from this config."""
        raise NotImplementedError(
            "GCSStore is not yet implemented. "
            "Use 'local' or 's3' for offline_store KIND."
        )


# Discriminated union for offline stores
OfflineStoreConfig = T.Annotated[
    LocalStoreConfig | S3StoreConfig | GCSStoreConfig,
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

    def create(self) -> online_.RedisStore:
        """Create store instance from this config."""
        import mlforge.online as online_

        return online_.RedisStore(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            ttl=self.ttl,
            prefix=self.prefix,
        )


# Discriminated union for online stores
OnlineStoreConfig = T.Annotated[
    RedisStoreConfig,
    Field(discriminator="KIND"),
]


# =============================================================================
# Profile and Root Config
# =============================================================================


class ProfileConfig(BaseModel, frozen=True):
    """Configuration for a single profile."""

    offline_store: OfflineStoreConfig
    online_store: OnlineStoreConfig | None = None


class MlforgeConfig(BaseModel, frozen=True):
    """Root configuration from mlforge.yaml."""

    default_profile: str = "dev"
    profiles: dict[str, ProfileConfig]


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
