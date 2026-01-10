"""Tests for environment profiles functionality."""

import pytest
from pydantic import ValidationError

import mlforge.errors as errors
import mlforge.profiles as profiles

# =============================================================================
# Pydantic Config Validation Tests
# =============================================================================


class TestLocalStoreConfig:
    """Tests for LocalStoreConfig."""

    def test_valid_config(self):
        """LocalStoreConfig should validate with valid params."""
        config = profiles.LocalStoreConfig(path="./store")
        assert config.KIND == "local"
        assert config.path == "./store"

    def test_default_path(self):
        """LocalStoreConfig should have default path."""
        config = profiles.LocalStoreConfig()
        assert config.path == "./feature_store"

    def test_create_returns_local_store(self, tmp_path):
        """create() should return LocalStore instance."""
        import mlforge.store as store_

        config = profiles.LocalStoreConfig(path=str(tmp_path / "store"))
        store = config.create()
        assert isinstance(store, store_.LocalStore)
        assert store.path == tmp_path / "store"


class TestS3StoreConfig:
    """Tests for S3StoreConfig."""

    def test_valid_config(self):
        """S3StoreConfig should validate with required fields."""
        config = profiles.S3StoreConfig(bucket="my-bucket")
        assert config.KIND == "s3"
        assert config.bucket == "my-bucket"
        assert config.prefix == ""  # default
        assert config.region is None  # default

    def test_with_all_fields(self):
        """S3StoreConfig should accept all optional fields."""
        config = profiles.S3StoreConfig(
            bucket="my-bucket",
            prefix="features",
            region="us-west-2",
        )
        assert config.prefix == "features"
        assert config.region == "us-west-2"

    def test_missing_bucket_raises(self):
        """S3StoreConfig should require bucket."""
        with pytest.raises(ValidationError):
            profiles.S3StoreConfig()  # type: ignore[call-arg]


class TestGCSStoreConfig:
    """Tests for GCSStoreConfig."""

    def test_valid_config(self):
        """GCSStoreConfig should validate with required fields."""
        config = profiles.GCSStoreConfig(bucket="my-bucket")
        assert config.KIND == "gcs"
        assert config.bucket == "my-bucket"

    def test_create_returns_gcs_store(self, mocker):
        """create() should return GCSStore instance."""
        import mlforge.store as store_

        # Mock GCSFileSystem to avoid real GCS calls
        mock_gcs = mocker.MagicMock()
        mock_gcs.exists.return_value = True
        mocker.patch("mlforge.store.gcsfs.GCSFileSystem", return_value=mock_gcs)

        config = profiles.GCSStoreConfig(bucket="my-bucket", prefix="features")
        store = config.create()
        assert isinstance(store, store_.GCSStore)
        assert store.bucket == "my-bucket"
        assert store.prefix == "features"


class TestRedisStoreConfig:
    """Tests for RedisStoreConfig."""

    def test_valid_config(self):
        """RedisStoreConfig should validate with defaults."""
        config = profiles.RedisStoreConfig()
        assert config.KIND == "redis"
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None

    def test_with_all_fields(self):
        """RedisStoreConfig should accept all fields."""
        config = profiles.RedisStoreConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            password="secret",
            ttl=3600,
            prefix="myapp",
        )
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
        assert config.password == "secret"
        assert config.ttl == 3600
        assert config.prefix == "myapp"

    def test_port_validation(self):
        """RedisStoreConfig should validate port range."""
        with pytest.raises(ValidationError):
            profiles.RedisStoreConfig(port=99999)

        with pytest.raises(ValidationError):
            profiles.RedisStoreConfig(port=0)

    def test_db_validation(self):
        """RedisStoreConfig should validate db >= 0."""
        with pytest.raises(ValidationError):
            profiles.RedisStoreConfig(db=-1)


class TestProfileConfig:
    """Tests for ProfileConfig discriminated union."""

    def test_local_store_discriminator(self):
        """Should create LocalStoreConfig based on KIND."""
        config = profiles.ProfileConfig.model_validate(
            {"offline_store": {"KIND": "local", "path": "./store"}}
        )
        assert isinstance(config.offline_store, profiles.LocalStoreConfig)
        assert config.offline_store.path == "./store"

    def test_s3_store_discriminator(self):
        """Should create S3StoreConfig based on KIND."""
        config = profiles.ProfileConfig.model_validate(
            {"offline_store": {"KIND": "s3", "bucket": "my-bucket"}}
        )
        assert isinstance(config.offline_store, profiles.S3StoreConfig)
        assert config.offline_store.bucket == "my-bucket"

    def test_gcs_store_discriminator(self):
        """Should create GCSStoreConfig based on KIND."""
        config = profiles.ProfileConfig.model_validate(
            {"offline_store": {"KIND": "gcs", "bucket": "my-bucket"}}
        )
        assert isinstance(config.offline_store, profiles.GCSStoreConfig)

    def test_redis_store_discriminator(self):
        """Should create RedisStoreConfig for online_store."""
        config = profiles.ProfileConfig.model_validate(
            {
                "offline_store": {"KIND": "local"},
                "online_store": {"KIND": "redis", "host": "redis.example.com"},
            }
        )
        assert isinstance(config.online_store, profiles.RedisStoreConfig)
        assert config.online_store.host == "redis.example.com"

    def test_invalid_store_kind(self):
        """Should error on unknown store KIND."""
        with pytest.raises(ValidationError) as exc_info:
            profiles.ProfileConfig.model_validate(
                {"offline_store": {"KIND": "postgres", "host": "localhost"}}
            )
        assert "union_tag_invalid" in str(exc_info.value)

    def test_online_store_optional(self):
        """online_store should be optional."""
        config = profiles.ProfileConfig.model_validate(
            {"offline_store": {"KIND": "local"}}
        )
        assert config.online_store is None


class TestMlforgeConfig:
    """Tests for MlforgeConfig root config."""

    def test_valid_config(self):
        """Should validate complete config."""
        config = profiles.MlforgeConfig.model_validate(
            {
                "default_profile": "dev",
                "profiles": {
                    "dev": {
                        "offline_store": {"KIND": "local", "path": "./store"}
                    },
                    "prod": {
                        "offline_store": {"KIND": "s3", "bucket": "my-bucket"}
                    },
                },
            }
        )
        assert config.default_profile == "dev"
        assert len(config.profiles) == 2
        assert "dev" in config.profiles
        assert "prod" in config.profiles

    def test_default_profile_defaults_to_dev(self):
        """default_profile should default to 'dev'."""
        config = profiles.MlforgeConfig.model_validate(
            {"profiles": {"dev": {"offline_store": {"KIND": "local"}}}}
        )
        assert config.default_profile == "dev"


# =============================================================================
# YAML Loading Tests
# =============================================================================


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_yaml(self, tmp_path):
        """Should load and validate mlforge.yaml."""
        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./feature_store
""")
        config = profiles.load_config(config_file)
        assert config is not None
        assert config.default_profile == "dev"
        assert isinstance(
            config.profiles["dev"].offline_store, profiles.LocalStoreConfig
        )

    def test_returns_none_if_no_file(self, tmp_path):
        """Should return None if config file doesn't exist."""
        config = profiles.load_config(tmp_path / "nonexistent.yaml")
        assert config is None

    def test_env_var_substitution(self, tmp_path, monkeypatch):
        """Should resolve ${oc.env:VAR} patterns."""
        monkeypatch.setenv("REDIS_HOST", "redis.example.com")

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: prod
profiles:
  prod:
    offline_store:
      KIND: local
      path: ./store
    online_store:
      KIND: redis
      host: ${oc.env:REDIS_HOST}
""")
        config = profiles.load_config(config_file)
        assert config is not None
        assert config.profiles["prod"].online_store is not None
        assert config.profiles["prod"].online_store.host == "redis.example.com"

    def test_env_var_with_default(self, tmp_path, monkeypatch):
        """Should use default value when env var not set."""
        # Ensure OPTIONAL_VAR is not set
        monkeypatch.delenv("OPTIONAL_VAR", raising=False)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ${oc.env:OPTIONAL_VAR,./default_store}
""")
        config = profiles.load_config(config_file)
        assert config is not None
        assert config.profiles["dev"].offline_store.path == "./default_store"

    def test_missing_env_var_raises(self, tmp_path, monkeypatch):
        """Should error when required env var not set."""
        monkeypatch.delenv("MISSING_BUCKET", raising=False)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: prod
profiles:
  prod:
    offline_store:
      KIND: s3
      bucket: ${oc.env:MISSING_BUCKET}
""")
        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.load_config(config_file)
        assert "MISSING_BUCKET" in str(exc_info.value)

    def test_invalid_yaml_raises(self, tmp_path):
        """Should error on invalid YAML syntax."""
        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
this is not: valid yaml: [
""")
        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.load_config(config_file)
        assert "Failed to parse" in str(exc_info.value)

    def test_invalid_schema_raises(self, tmp_path):
        """Should error on invalid config schema."""
        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: 123  # Should be string? Actually path can be anything convertible
""")
        # This should actually work since 123 can be converted to string
        # Let's test a real schema violation
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: s3
      # Missing required 'bucket' field
""")
        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.load_config(config_file)
        assert "Invalid configuration" in str(exc_info.value)

    def test_list_yaml_raises(self, tmp_path):
        """Should error if YAML is a list not dict."""
        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
- item1
- item2
""")
        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.load_config(config_file)
        assert "mapping" in str(exc_info.value).lower()


# =============================================================================
# Profile Loading Tests
# =============================================================================


class TestLoadProfile:
    """Tests for load_profile function."""

    def test_load_default_profile(self, tmp_path, monkeypatch):
        """Should load default_profile when no name specified."""
        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./dev_store
  prod:
    offline_store:
      KIND: local
      path: ./prod_store
""")
        profile = profiles.load_profile(config_path=config_file)
        assert profile.offline_store.path == "./dev_store"

    def test_load_profile_from_env_var(self, tmp_path, monkeypatch):
        """Should use MLFORGE_PROFILE environment variable."""
        monkeypatch.setenv("MLFORGE_PROFILE", "prod")
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./dev_store
  prod:
    offline_store:
      KIND: local
      path: ./prod_store
""")
        profile = profiles.load_profile(config_path=config_file)
        assert profile.offline_store.path == "./prod_store"

    def test_explicit_name_overrides_env_var(self, tmp_path, monkeypatch):
        """Explicit name should override env var."""
        monkeypatch.setenv("MLFORGE_PROFILE", "prod")

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./dev_store
  prod:
    offline_store:
      KIND: local
      path: ./prod_store
""")
        profile = profiles.load_profile(name="dev", config_path=config_file)
        assert profile.offline_store.path == "./dev_store"

    def test_profile_not_found(self, tmp_path, monkeypatch):
        """Should error with available profiles listed."""
        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
  prod:
    offline_store:
      KIND: local
""")
        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.load_profile(name="staging", config_path=config_file)

        error_msg = str(exc_info.value)
        assert "staging" in error_msg
        assert "not found" in error_msg.lower()
        assert "dev" in error_msg
        assert "prod" in error_msg

    def test_no_config_file_raises(self, tmp_path, monkeypatch):
        """Should error when no mlforge.yaml exists."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.load_profile(config_path=tmp_path / "nonexistent.yaml")
        assert "No mlforge.yaml found" in str(exc_info.value)


class TestGetProfileInfo:
    """Tests for get_profile_info function."""

    def test_returns_default_profile(self, tmp_path, monkeypatch):
        """Should return default_profile from config."""
        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: staging
profiles:
  staging:
    offline_store:
      KIND: local
""")
        result = profiles.get_profile_info(config_file)
        assert result is not None
        name, source, config = result
        assert name == "staging"
        assert source == "config"
        assert config.default_profile == "staging"

    def test_returns_env_var_profile(self, tmp_path, monkeypatch):
        """Should return MLFORGE_PROFILE env var."""
        monkeypatch.setenv("MLFORGE_PROFILE", "prod")

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
""")
        result = profiles.get_profile_info(config_file)
        assert result is not None
        name, source, _ = result
        assert name == "prod"
        assert source == "env"

    def test_returns_none_without_config(self, tmp_path):
        """Should return None if no config file."""
        result = profiles.get_profile_info(tmp_path / "nonexistent.yaml")
        assert result is None

    def test_returns_config_for_default(self, tmp_path, monkeypatch):
        """Should return 'config' source when using default_profile."""
        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
""")
        result = profiles.get_profile_info(config_file)
        assert result is not None
        _, source, _ = result
        assert source == "config"

    def test_returns_env_for_env_var(self, tmp_path, monkeypatch):
        """Should return 'env' when MLFORGE_PROFILE is set."""
        monkeypatch.setenv("MLFORGE_PROFILE", "prod")

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
""")
        result = profiles.get_profile_info(config_file)
        assert result is not None
        _, source, _ = result
        assert source == "env"


# =============================================================================
# Store Validation Tests
# =============================================================================


class TestValidateStores:
    """Tests for validate_stores function."""

    def test_validates_local_store_success(self, tmp_path):
        """Should succeed for valid LocalStore config."""
        config = profiles.ProfileConfig.model_validate(
            {
                "offline_store": {
                    "KIND": "local",
                    "path": str(tmp_path / "store"),
                }
            }
        )
        # Should not raise
        profiles.validate_stores(config)

    def test_validates_gcs_store_success(self, mocker):
        """Should succeed for valid GCSStore config."""
        # Mock GCSFileSystem to avoid real GCS calls
        mock_gcs = mocker.MagicMock()
        mock_gcs.exists.return_value = True
        mocker.patch("mlforge.store.gcsfs.GCSFileSystem", return_value=mock_gcs)

        config = profiles.ProfileConfig.model_validate(
            {"offline_store": {"KIND": "gcs", "bucket": "my-bucket"}}
        )
        # Should not raise
        profiles.validate_stores(config)

    def test_raises_on_gcs_bucket_not_found(self, mocker):
        """Should raise ProfileError when GCS bucket doesn't exist."""
        # Mock GCSFileSystem to report bucket doesn't exist
        mock_gcs = mocker.MagicMock()
        mock_gcs.exists.return_value = False
        mocker.patch("mlforge.store.gcsfs.GCSFileSystem", return_value=mock_gcs)

        config = profiles.ProfileConfig.model_validate(
            {"offline_store": {"KIND": "gcs", "bucket": "nonexistent-bucket"}}
        )
        with pytest.raises(errors.ProfileError) as exc_info:
            profiles.validate_stores(config)
        assert "Failed to validate offline_store" in str(exc_info.value)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDefinitionsIntegration:
    """Tests for Definitions integration with profiles."""

    def test_definitions_loads_from_profile(self, tmp_path, monkeypatch):
        """Definitions should auto-load stores from profile."""
        import mlforge.core as core

        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./my_feature_store
""")

        # Create a minimal feature for registration
        @core.feature(source="data.parquet", keys=["id"])
        def test_feature(df):
            return df

        defs = core.Definitions(
            name="test",
            features=[test_feature],
            # No offline_store - should load from profile
        )
        assert defs.offline_store is not None
        # Path is relative, stored as Path("my_feature_store")
        assert str(defs.offline_store.path) == "my_feature_store"

    def test_explicit_store_overrides_profile(self, tmp_path, monkeypatch):
        """Explicit offline_store should override profile."""
        import mlforge.core as core
        import mlforge.store as store

        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./profile_store
""")
        explicit_store = store.LocalStore(tmp_path / "explicit_store")

        @core.feature(source="data.parquet", keys=["id"])
        def test_feature(df):
            return df

        defs = core.Definitions(
            name="test",
            features=[test_feature],
            offline_store=explicit_store,
        )
        assert defs.offline_store.path == tmp_path / "explicit_store"

    def test_definitions_with_profile_param(self, tmp_path, monkeypatch):
        """Definitions should accept profile parameter."""
        import mlforge.core as core

        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)
        monkeypatch.chdir(tmp_path)

        config_file = tmp_path / "mlforge.yaml"
        config_file.write_text("""
default_profile: dev
profiles:
  dev:
    offline_store:
      KIND: local
      path: ./dev_store
  staging:
    offline_store:
      KIND: local
      path: ./staging_store
""")

        @core.feature(source="data.parquet", keys=["id"])
        def test_feature(df):
            return df

        defs = core.Definitions(
            name="test",
            features=[test_feature],
            profile="staging",
        )
        # Path is relative, stored as Path("staging_store")
        assert str(defs.offline_store.path) == "staging_store"

    def test_definitions_raises_without_store_or_config(
        self, tmp_path, monkeypatch
    ):
        """Should error if no store and no config file."""
        import mlforge.core as core

        monkeypatch.delenv("MLFORGE_PROFILE", raising=False)
        monkeypatch.chdir(tmp_path)
        # No mlforge.yaml in tmp_path

        @core.feature(source="data.parquet", keys=["id"])
        def test_feature(df):
            return df

        with pytest.raises(errors.ProfileError):
            core.Definitions(
                name="test",
                features=[test_feature],
                # No offline_store, no mlforge.yaml
            )
