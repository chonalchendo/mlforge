"""Entity definitions for credit card transaction features.

Entities represent the primary keys used to organize and join features.
mlforge automatically generates surrogate keys from source columns when
`from_columns` is specified, enabling consistent key generation across
training and inference.
"""

import mlforge as mlf

# Customer entity with surrogate key generation from PII fields.
# The user_id is a deterministic hash of (first, last, dob), enabling
# consistent identification without storing PII in feature tables.
customer = mlf.Entity(
    name="customer",
    join_key="customer_id",
    from_columns=["first_name", "last_name", "date_of_birth"],
)

# Merchant entity with surrogate key from merchant name.
# This allows joining features to transactions without exposing
# the full merchant name in the feature store.
merchant = mlf.Entity(
    name="merchant",
    join_key="merchant_id",
    from_columns=["merchant_name"],
)

# Transaction entity uses the transaction_id directly as the key.
# No surrogate key generation needed since transaction_id is already
# a unique identifier in the source data.
transaction = mlf.Entity(
    name="transaction",
    join_key="transaction_id",
)

# Customer-merchant pair for cross-entity features.
# Composite key enables tracking customer behavior at specific merchants.
customer_merchant = mlf.Entity(
    name="customer_merchant",
    join_key=["customer_id", "merchant_id"],
)
