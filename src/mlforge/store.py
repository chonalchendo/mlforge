"""
Offline feature store implementations.

This module re-exports store classes from mlforge.stores for backward compatibility.
New code should import directly from mlforge.stores.

Example:
    # Preferred (new code)
    from mlforge.stores import LocalStore, S3Store

    # Also works (backward compatibility)
    from mlforge.store import LocalStore, S3Store
"""

from mlforge.stores import (
    GCSStore,
    LocalStore,
    OfflineStoreKind,
    S3Store,
    Store,
    UnityCatalogStore,
)

__all__ = [
    "Store",
    "LocalStore",
    "S3Store",
    "GCSStore",
    "UnityCatalogStore",
    "OfflineStoreKind",
]
