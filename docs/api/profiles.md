# Profiles API

The profiles module provides YAML-based configuration for different environments (dev, staging, production) with automatic store instantiation.

## Configuration File

mlforge uses `mlforge.yaml` to define environment profiles. Each profile specifies offline and optional online store configurations:

```yaml
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
```

Environment variables can be interpolated using `${oc.env:VAR_NAME}` syntax.

## Profile Selection

Profiles are resolved in this order:

1. Explicit `name` parameter (highest priority)
2. `MLFORGE_PROFILE` environment variable
3. `default_profile` from mlforge.yaml

## Functions

::: mlforge.profiles.load_config

::: mlforge.profiles.load_profile

::: mlforge.profiles.get_profile_info

::: mlforge.profiles.print_store_config

::: mlforge.profiles.validate_stores

## Store Configurations

### Offline Stores

::: mlforge.profiles.LocalStoreConfig

::: mlforge.profiles.S3StoreConfig

::: mlforge.profiles.GCSStoreConfig

### Online Stores

::: mlforge.profiles.RedisStoreConfig

## Config Models

::: mlforge.profiles.ProfileConfig

::: mlforge.profiles.MlforgeConfig
