# Defining Features

Features in mlforge are defined using the `@mlf.feature` decorator, which transforms a Python function into a feature that can be built and retrieved.

## The @feature Decorator

The decorator requires two parameters and accepts several optional ones:

```python
import mlforge as mlf
import polars as pl

@mlf.feature(
    keys=["user_id"],                    # Required: entity keys
    source="data/transactions.parquet",  # Required: source data path
    tags=["user_metrics"],               # Optional: feature grouping tags
    timestamp="event_time",              # Optional: for temporal features
    description="User statistics",       # Optional: human-readable description
    interval="1d",                       # Optional: for rolling aggregations
    metrics=[]                           # Optional: metric specifications
)
def user_stats(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("amount").mean().alias("avg_spend")
    )
```

### Required Parameters

#### keys

List of column names that uniquely identify entities. These columns will be used to join features to your entity DataFrame.

```python
@mlf.feature(
    keys=["user_id"],  # Single key
    source="data/users.parquet"
)
def user_age(df): ...

@mlf.feature(
    keys=["user_id", "merchant_id"],  # Composite key
    source="data/interactions.parquet"
)
def user_merchant_interaction(df): ...
```

#### source

Path to the source data file. Supports Parquet and CSV formats.

```python
@mlf.feature(
    keys=["product_id"],
    source="data/products.parquet"  # Parquet
)
def product_features(df): ...

@mlf.feature(
    keys=["customer_id"],
    source="data/customers.csv"  # CSV
)
def customer_features(df): ...
```

The path can be relative or absolute. Relative paths are resolved from your working directory.

### Optional Parameters

#### tags

List of tags to group related features together. Tags enable selective building and listing of features.

```python
@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    tags=["user_metrics", "revenue"]
)
def user_lifetime_value(df): ...

@mlf.feature(
    keys=["user_id"],
    source="data/demographics.parquet",
    tags=["demographics"]
)
def user_age_group(df): ...
```

Build only features with specific tags:

```bash
mlforge build --tags user_metrics
mlforge build --tags user_metrics,demographics
```

List features by tag:

```bash
mlforge list --tags revenue
```

!!! tip "Organizing features"
    Use tags to organize features by domain (e.g., "user", "product"), category (e.g., "demographics", "behavior"), or team ownership (e.g., "data-science", "ml-ops").

#### timestamp

Column name for temporal features. When specified, enables point-in-time correct joins during retrieval.

```python
@mlf.feature(
    keys=["user_id"],
    source="data/events.parquet",
    timestamp="event_timestamp"  # Enables point-in-time joins
)
def user_rolling_stats(df): ...
```

!!! tip "Point-in-time correctness"
    Always specify a timestamp for features computed from time-series data. This ensures
    `mlf.get_training_data()` performs asof joins, preventing data leakage.

See [Point-in-Time Correctness](point-in-time.md) for details.

#### description

Human-readable description displayed by `mlforge list`.

```python
@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    description="Total lifetime spend by user"
)
def user_lifetime_spend(df): ...
```

#### interval

Time interval for rolling aggregations. Accepts either a string (e.g., `"1d"`, `"6h"`) or a Python `timedelta` object.

```python
from datetime import timedelta

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_time",
    interval="1d"  # String format
)
def daily_features(df): ...

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_time",
    interval=timedelta(hours=6)  # timedelta object
)
def hourly_features(df): ...
```

Supported string formats: `"Ns"` (seconds), `"Nm"` (minutes), `"Nh"` (hours), `"Nd"` (days), `"Nw"` (weeks).

!!! tip "Using timedelta"
    Using Python's `timedelta` can make intervals more readable and easier to compute:
    ```python
    interval=timedelta(days=7)  # More explicit than "7d"
    interval=timedelta(hours=6)  # Clearer than "6h"
    interval=timedelta(weeks=4)  # Converts to "28d" automatically
    ```

#### metrics

List of metric specifications for computing features. Currently supports `mlf.Rolling` for time-windowed aggregations.

```python
import mlforge as mlf
from datetime import timedelta

@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_time",
    interval="1d",
    metrics=[
        mlf.Rolling(
            windows=["7d", "30d"],  # Can use strings
            aggregations={"amount": ["sum", "mean", "count"]}
        )
    ]
)
def user_transaction_metrics(df): ...

# Or with timedelta for better readability
@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="transaction_time",
    interval=timedelta(days=1),
    metrics=[
        mlf.Rolling(
            windows=[timedelta(days=7), timedelta(days=30)],  # timedelta objects
            aggregations={"amount": ["sum", "mean", "count"]}
        )
    ]
)
def user_transaction_metrics(df): ...
```

The `mlf.Rolling` metric computes aggregations over sliding time windows. Output column names follow the pattern: `{tag}__{column}__{aggregation}__{window}__{interval}`.

## Feature Functions

The decorated function must:

1. Accept a Polars DataFrame as input
2. Return a Polars DataFrame
3. Include the key columns in the output

### Basic Example

```python
@mlf.feature(
    keys=["product_id"],
    source="data/sales.parquet"
)
def product_total_sales(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("product_id").agg(
        pl.col("quantity").sum().alias("total_sales")
    )
```

### Aggregation Example

```python
@mlf.feature(
    keys=["customer_id"],
    source="data/orders.parquet",
    description="Customer order statistics"
)
def customer_order_stats(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("customer_id").agg([
        pl.col("order_id").count().alias("order_count"),
        pl.col("total_amount").sum().alias("lifetime_value"),
        pl.col("total_amount").mean().alias("avg_order_value"),
        pl.col("order_date").max().alias("last_order_date")
    ])
```

### Time-Based Rolling Features

```python
@mlf.feature(
    keys=["user_id"],
    source="data/activity.parquet",
    timestamp="feature_timestamp",
    description="User activity over 7-day windows"
)
def user_7d_activity(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df
        .sort("event_time")
        .group_by_dynamic(
            "event_time",
            every="1d",
            period="7d",
            by="user_id"
        )
        .agg([
            pl.col("event_id").count().alias("event_count_7d"),
            pl.col("session_id").n_unique().alias("unique_sessions_7d")
        ])
        .rename({"event_time": "feature_timestamp"})
    )
```

!!! note "Timestamp column naming"
    For temporal features, rename your time column to `feature_timestamp` in the output.
    This convention ensures correct asof joins during retrieval.

## Multiple Features per Module

Organize related features in a single module:

```python
# user_features.py
import mlforge as mlf
import polars as pl

SOURCE = "data/users.parquet"

@mlf.feature(
    keys=["user_id"],
    source=SOURCE,
    tags=["demographics"]
)
def user_age(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "age"])

@mlf.feature(
    keys=["user_id"],
    source=SOURCE,
    tags=["demographics"]
)
def user_tenure_days(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        (pl.col("created_at").dt.date() - pl.lit("2020-01-01").str.to_date())
        .dt.total_days()
        .alias("tenure_days")
    ).select(["user_id", "tenure_days"])

@mlf.feature(
    keys=["user_id"],
    source=SOURCE,
    tags=["subscription"]
)
def user_is_premium(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(["user_id", "is_premium"])
```

Then register the entire module:

```python
# definitions.py
import mlforge as mlf
import user_features

defs = mlf.Definitions(
    name="my-project",
    features=[user_features],  # Auto-discovers all features
    offline_store=mlf.LocalStore("./feature_store")
)
```

## Best Practices

### 1. Keep Features Pure

Feature functions should be deterministic and stateless:

```python
# Good - pure transformation
@mlf.feature(keys=["user_id"], source="data/users.parquet")
def user_age_group(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.when(pl.col("age") < 25).then(pl.lit("young"))
        .when(pl.col("age") < 65).then(pl.lit("adult"))
        .otherwise(pl.lit("senior"))
        .alias("age_group")
    )

# Bad - depends on external state
current_year = 2024  # External dependency

@mlf.feature(keys=["user_id"], source="data/users.parquet")
def user_is_adult(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        (current_year - pl.col("birth_year") >= 18).alias("is_adult")
    )
```

### 2. Use Descriptive Names

Name features after what they represent, not how they're computed:

```python
# Good
@mlf.feature(keys=["user_id"], source="data/transactions.parquet")
def user_total_spend(df): ...

# Bad
@mlf.feature(keys=["user_id"], source="data/transactions.parquet")
def sum_amount_by_user(df): ...
```

### 3. Include Key Columns

Always ensure key columns are in the output:

```python
# Good
@mlf.feature(keys=["user_id"], source="data/events.parquet")
def user_event_count(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("user_id").agg(
        pl.col("event_id").count().alias("event_count")
    )  # user_id is preserved by group_by

# Bad - missing key
@mlf.feature(keys=["user_id"], source="data/events.parquet")
def user_event_count(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        pl.col("event_id").count().alias("event_count")
    )  # user_id is lost!
```

### 4. Add Descriptions for Complex Features

```python
@mlf.feature(
    keys=["user_id"],
    source="data/transactions.parquet",
    timestamp="feature_timestamp",
    description="30-day rolling average of transaction amounts"
)
def user_spend_mean_30d(df): ...
```

## Next Steps

- [Building Features](building-features.md) - Materialize features to storage
- [Entity Keys](entity-keys.md) - Work with surrogate keys and composite identifiers
- [Point-in-Time Correctness](point-in-time.md) - Learn about temporal joins
