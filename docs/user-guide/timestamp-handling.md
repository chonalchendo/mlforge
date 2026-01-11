# Timestamp Handling

The `Timestamp` class provides flexible datetime parsing with automatic format detection. Use it to configure how mlforge interprets timestamp columns in your source data.

## Basic Usage

```python
import mlforge as mlf

# Simple case - auto-detect format
timestamp = mlf.Timestamp(column="event_time")

# Explicit format for consistent parsing
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
)
```

## Using Timestamp with Features

Pass a `Timestamp` to the `@feature` decorator to enable point-in-time correct joins:

```python
import mlforge as mlf
import polars as pl

transactions = mlf.Source("data/transactions.parquet")

timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
)

@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp=timestamp,  # Enables point-in-time joins
    interval=timedelta(days=1),
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("user_id", "trans_date_trans_time", "amt")
```

## Automatic Format Detection

When no format is specified, mlforge samples the column and tries common datetime formats:

```python
# Auto-detect - works for standard formats
timestamp = mlf.Timestamp(column="created_at")
```

**Supported auto-detected formats:**

| Format | Example |
|--------|---------|
| `%Y-%m-%dT%H:%M:%S` | `2024-01-15T14:30:00` |
| `%Y-%m-%d %H:%M:%S` | `2024-01-15 14:30:00` |
| `%Y-%m-%dT%H:%M:%S%z` | `2024-01-15T14:30:00+0000` |
| `%Y-%m-%d %H:%M:%S%z` | `2024-01-15 14:30:00+0000` |
| `%Y-%m-%dT%H:%M:%S.%f` | `2024-01-15T14:30:00.123456` |
| `%Y-%m-%d %H:%M:%S.%f` | `2024-01-15 14:30:00.123456` |
| `%Y-%m-%d` | `2024-01-15` |
| `%d/%m/%Y %H:%M:%S` | `15/01/2024 14:30:00` |
| `%m/%d/%Y %H:%M:%S` | `01/15/2024 14:30:00` |
| `%d/%m/%Y` | `15/01/2024` |
| `%m/%d/%Y` | `01/15/2024` |

!!! tip "Prefer explicit formats"
    While auto-detection is convenient, specifying the format explicitly ensures consistent parsing and avoids ambiguity (e.g., `01/02/2024` could be January 2nd or February 1st).

## Explicit Format Strings

Use Python's strftime format codes for explicit parsing:

```python
# ISO 8601 with space separator
timestamp = mlf.Timestamp(
    column="event_time",
    format="%Y-%m-%d %H:%M:%S",
)

# Date only
timestamp = mlf.Timestamp(
    column="date",
    format="%Y-%m-%d",
)

# Custom format
timestamp = mlf.Timestamp(
    column="legacy_timestamp",
    format="%d-%b-%Y %H:%M",  # e.g., "15-Jan-2024 14:30"
)
```

**Common format codes:**

| Code | Meaning | Example |
|------|---------|---------|
| `%Y` | 4-digit year | `2024` |
| `%m` | Month (zero-padded) | `01` |
| `%d` | Day (zero-padded) | `15` |
| `%H` | Hour (24-hour) | `14` |
| `%M` | Minute | `30` |
| `%S` | Second | `00` |
| `%f` | Microsecond | `123456` |
| `%z` | UTC offset | `+0000` |
| `%b` | Abbreviated month | `Jan` |
| `%B` | Full month name | `January` |

## Column Aliasing

Rename the output column using the `alias` parameter:

```python
# Input column: "trans_date_trans_time"
# Output column: "event_time"
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
    alias="event_time",
)
```

This is useful when:

- Source columns have verbose or inconsistent names
- You want a standard timestamp column name across features
- Downstream code expects a specific column name

## Timestamp Properties

Access timestamp configuration programmatically:

```python
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
    alias="event_time",
)

timestamp.column        # "trans_date_trans_time"
timestamp.format        # "%Y-%m-%d %H:%M:%S"
timestamp.alias         # "event_time"
timestamp.output_column # "event_time" (alias if set, otherwise column)
```

## String vs Timestamp Object

You can use either a string or a `Timestamp` object for the `timestamp` parameter:

```python
# String - simple case
@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp="event_time",  # Column name as string
)
def feature_a(df): ...

# Timestamp object - with format/alias
@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp=mlf.Timestamp(
        column="trans_date_trans_time",
        format="%Y-%m-%d %H:%M:%S",
    ),
)
def feature_b(df): ...
```

Use a string when:

- The column is already a datetime type
- The format is auto-detectable

Use a `Timestamp` object when:

- You need to specify an explicit format
- You want to rename the column with an alias
- The format is non-standard

## Handling Different Column Types

mlforge handles three scenarios:

### 1. Already Datetime Type

If the column is already a Polars datetime type, no parsing is needed:

```python
# Column is datetime - used directly
timestamp = mlf.Timestamp(column="event_time")
```

### 2. String Column with Known Format

Specify the format for reliable parsing:

```python
# String column - parse with format
timestamp = mlf.Timestamp(
    column="event_time",
    format="%Y-%m-%d %H:%M:%S",
)
```

### 3. String Column with Unknown Format

Let mlforge auto-detect:

```python
# Auto-detect format from sample values
timestamp = mlf.Timestamp(column="event_time")
```

If auto-detection fails, you'll receive a `TimestampParseError` with sample values to help identify the format.

## Complete Example

```python
# features.py
from datetime import timedelta

import polars as pl

import mlforge as mlf
from entities import user, merchant

# Define source
transactions = mlf.Source("data/transactions.parquet")

# Define timestamp with explicit format
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
)

# Define rolling metrics
spend_metrics = mlf.Rolling(
    windows=["1d", "7d", "30d"],
    aggregations={"amt": ["sum", "mean", "count"]},
)

@mlf.feature(
    source=transactions,
    entities=[user],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[spend_metrics],
    tags=["user", "spending"],
)
def user_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("user_id", "trans_date_trans_time", "amt")

@mlf.feature(
    source=transactions,
    entities=[merchant],
    timestamp=timestamp,
    interval=timedelta(days=1),
    metrics=[spend_metrics],
    tags=["merchant", "spending"],
)
def merchant_spend(df: pl.DataFrame) -> pl.DataFrame:
    return df.select("merchant_id", "trans_date_trans_time", "amt")
```

## Error Handling

### TimestampParseError

Raised when parsing fails. The error includes sample values to help diagnose the issue:

```python
# Error message example:
# TimestampParseError: Failed to parse column 'event_time'.
# Sample values: ['15-01-2024', '16-01-2024', '17-01-2024']
#
# Try specifying an explicit format:
#   Timestamp(column="event_time", format="%d-%m-%Y")
```

### Column Not Found

Raised when the specified column doesn't exist:

```python
# Error message example:
# TimestampParseError: Column 'event_time' not found in DataFrame
```

## Best Practices

### 1. Always Specify Format for Production

```python
# Good - consistent parsing
timestamp = mlf.Timestamp(
    column="event_time",
    format="%Y-%m-%d %H:%M:%S",
)

# Risky - format detection may vary
timestamp = mlf.Timestamp(column="event_time")
```

### 2. Use Standard Column Names

```python
# Good - clear, standard name
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    alias="event_time",  # Standardize output
)
```

### 3. Define Timestamps at Module Level

```python
# Good - reusable across features
timestamp = mlf.Timestamp(
    column="trans_date_trans_time",
    format="%Y-%m-%d %H:%M:%S",
)

@mlf.feature(timestamp=timestamp, ...)
def feature_a(df): ...

@mlf.feature(timestamp=timestamp, ...)
def feature_b(df): ...
```

### 4. Handle Timezone-Aware Data

```python
# Include timezone in format
timestamp = mlf.Timestamp(
    column="event_time",
    format="%Y-%m-%dT%H:%M:%S%z",  # e.g., 2024-01-15T14:30:00+0000
)
```

## Next Steps

- [Point-in-Time Correctness](point-in-time.md) - How timestamps enable correct joins
- [Source Abstraction](source-abstraction.md) - Configure data sources
- [Defining Features](defining-features.md) - Use timestamps in feature definitions
