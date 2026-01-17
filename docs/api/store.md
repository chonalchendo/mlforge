# Store API

The stores module provides interfaces and implementations for offline feature storage.

## Abstract Base Class

::: mlforge.stores.base.Store

---

## Implementations

### LocalStore

Local filesystem storage using Parquet files.

::: mlforge.stores.local.LocalStore

### S3Store

Amazon S3 cloud storage.

::: mlforge.stores.s3.S3Store

### GCSStore

Google Cloud Storage.

::: mlforge.stores.gcs.GCSStore

### UnityCatalogStore

Databricks Unity Catalog storage using Delta Lake.

::: mlforge.stores.databricks_unity_catalog.UnityCatalogStore

---

## Type Aliases

```python
from mlforge.stores import OfflineStoreKind

# Type alias for all offline store implementations
type OfflineStoreKind = LocalStore | S3Store | GCSStore | UnityCatalogStore
```
