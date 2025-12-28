# Feature Validation

mlforge provides a validation system to ensure data quality before features are materialized. Validators run on the output of your feature function, before any metrics are computed.

## Why Validate?

Validation helps catch data quality issues early:

- **Prevent bad data from entering your feature store**
- **Document data expectations** in code
- **Fail fast** instead of discovering issues in production
- **Track validation rules** in metadata for auditing

## Using Built-in Validators

mlforge includes common validators for typical data quality checks.

### Basic Example

```python
import mlforge as mlf

@mlf.feature(
    keys=["merchant_id"],
    source="data/transactions.parquet",
    validators={
        "merchant_id": [mlf.not_null()],
        "amount": [mlf.not_null(), mlf.greater_than_or_equal(0)],
    }
)
def merchant_transactions(df):
    return df.select(["merchant_id", "amount", "transaction_date"])
```

If validation fails, the build will stop and report which validations failed:

```
ERROR: Feature validation failed for merchant_transactions
  - Column 'amount': 3 values < 0 (greater_than_or_equal(0))
```

### Available Validators

#### Null Checks

```python
import mlforge as mlf

@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "user_id": [mlf.not_null()],
        "email": [mlf.not_null()],
    }
)
def user_features(df):
    return df
```

#### Uniqueness

```python
import mlforge as mlf

@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "user_id": [mlf.unique()],  # Ensure no duplicate user IDs
    }
)
def user_features(df):
    return df
```

#### Numeric Comparisons

```python
import mlforge as mlf

@mlf.feature(
    keys=["product_id"],
    source="products.parquet",
    validators={
        "price": [mlf.greater_than(0)],
        "discount_pct": [mlf.greater_than_or_equal(0), mlf.less_than_or_equal(100)],
        "stock": [mlf.greater_than_or_equal(0)],
    }
)
def product_features(df):
    return df
```

#### Range Validation

```python
import mlforge as mlf

@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "age": [mlf.in_range(18, 120)],  # inclusive by default
        "score": [mlf.in_range(0, 100, inclusive=True)],
    }
)
def user_features(df):
    return df
```

#### Pattern Matching

```python
import mlforge as mlf

@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "email": [mlf.matches_regex(r"^\w+@\w+\.\w+$")],
        "phone": [mlf.matches_regex(r"^\+?1?\d{9,15}$")],
    }
)
def user_features(df):
    return df
```

#### Set Membership

```python
import mlforge as mlf

@mlf.feature(
    keys=["transaction_id"],
    source="transactions.parquet",
    validators={
        "status": [mlf.is_in(["pending", "approved", "rejected"])],
        "payment_method": [mlf.is_in(["card", "bank", "wallet"])],
    }
)
def transaction_features(df):
    return df
```

### Combining Validators

You can apply multiple validators to a single column:

```python
import mlforge as mlf

@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "age": [
            mlf.not_null(),           # Must have a value
            mlf.greater_than(0),      # Must be positive
            mlf.less_than(150),       # Must be reasonable
        ],
    }
)
def user_features(df):
    return df
```

Validators run in order. If any validator fails, validation stops and reports the failure.

## Creating Custom Validators

You can create custom validators for domain-specific validation logic.

### Basic Custom Validator

A validator is a function that returns a `Validator` object:

```python
from mlforge.validators import Validator, ValidationResult
import polars as pl

def is_valid_email() -> Validator:
    """Validate email addresses using custom logic."""

    def validate(series: pl.Series) -> ValidationResult:
        # Implement your validation logic
        invalid_emails = series.filter(
            ~series.str.contains("@") | series.is_null()
        )

        if len(invalid_emails) > 0:
            return ValidationResult(
                passed=False,
                message=f"{len(invalid_emails)} invalid email addresses",
                failed_count=len(invalid_emails),
            )

        return ValidationResult(passed=True)

    return Validator(name="is_valid_email", fn=validate)
```

Use it like any built-in validator:

```python
import mlforge as mlf

@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "email": [is_valid_email()],
    }
)
def user_features(df):
    return df
```

### Parameterized Custom Validators

Create validators that accept parameters:

```python
from mlforge.validators import Validator, ValidationResult
import polars as pl

def min_length(length: int) -> Validator:
    """Validate that string values have minimum length."""

    def validate(series: pl.Series) -> ValidationResult:
        too_short = series.filter(series.str.lengths() < length)

        if len(too_short) > 0:
            return ValidationResult(
                passed=False,
                message=f"{len(too_short)} values shorter than {length}",
                failed_count=len(too_short),
            )

        return ValidationResult(passed=True)

    return Validator(name=f"min_length({length})", fn=validate)


@mlf.feature(
    keys=["user_id"],
    source="users.parquet",
    validators={
        "username": [min_length(3)],
        "password_hash": [min_length(60)],  # bcrypt hashes are 60 chars
    }
)
def user_features(df):
    return df
```

### Business Logic Validators

Implement complex business rules:

```python
from mlforge.validators import Validator, ValidationResult
import polars as pl

def is_valid_transaction() -> Validator:
    """
    Validate transaction business rules.

    - Amount must be > 0
    - Refunds (negative amounts) must have a parent transaction
    - High-value transactions must have approval
    """

    def validate(series: pl.Series) -> ValidationResult:
        # This validator works on the entire DataFrame row context
        # For row-level validation, you'd need to implement custom logic

        invalid = series.filter(series == 0)  # No zero-amount transactions

        if len(invalid) > 0:
            return ValidationResult(
                passed=False,
                message=f"{len(invalid)} transactions with zero amount",
                failed_count=len(invalid),
            )

        return ValidationResult(passed=True)

    return Validator(name="is_valid_transaction", fn=validate)
```

### Statistical Validators

Validate statistical properties:

```python
from mlforge.validators import Validator, ValidationResult
import polars as pl

def within_std_devs(n_std: float) -> Validator:
    """Validate values are within n standard deviations of mean."""

    def validate(series: pl.Series) -> ValidationResult:
        mean = series.mean()
        std = series.std()

        if std is None or mean is None:
            return ValidationResult(passed=True)  # Skip if insufficient data

        lower = mean - (n_std * std)
        upper = mean + (n_std * std)

        outliers = series.filter((series < lower) | (series > upper))

        if len(outliers) > 0:
            return ValidationResult(
                passed=False,
                message=f"{len(outliers)} outliers beyond {n_std} std devs",
                failed_count=len(outliers),
            )

        return ValidationResult(passed=True)

    return Validator(name=f"within_std_devs({n_std})", fn=validate)


@mlf.feature(
    keys=["user_id"],
    source="transactions.parquet",
    validators={
        "amount": [within_std_devs(3)],  # Catch extreme outliers
    }
)
def transaction_features(df):
    return df
```

### Multi-Column Validators

For validators that need to check relationships between columns, implement the logic in your feature function and validate the result:

```python
import mlforge as mlf
from mlforge.validators import Validator, ValidationResult
import polars as pl

def discount_less_than_price() -> Validator:
    """Validate discount is always less than price."""

    def validate(series: pl.Series) -> ValidationResult:
        # Assumes series contains a boolean column from the feature function
        invalid = series.filter(~series)

        if len(invalid) > 0:
            return ValidationResult(
                passed=False,
                message=f"{len(invalid)} rows where discount >= price",
                failed_count=len(invalid),
            )

        return ValidationResult(passed=True)

    return Validator(name="discount_less_than_price", fn=validate)


@mlf.feature(
    keys=["product_id"],
    source="products.parquet",
    validators={
        "valid_pricing": [discount_less_than_price()],
    }
)
def product_features(df):
    return df.with_columns([
        (pl.col("discount") < pl.col("price")).alias("valid_pricing")
    ])
```

## Validation in Metadata

Validators are tracked in feature metadata for auditing and documentation:

```json
{
  "name": "merchant_transactions",
  "columns": [
    {
      "name": "merchant_id",
      "dtype": "String"
    },
    {
      "name": "amount",
      "dtype": "Float64",
      "validators": [
        {
          "validator": "not_null"
        },
        {
          "validator": "greater_than_or_equal",
          "value": 0
        }
      ]
    }
  ],
  "features": [...]
}
```

This metadata shows:
- Which columns have validators
- What validation rules are applied
- Parameters for each validator

## Validation CLI Command

Run validation without building features:

```bash
# Validate all features
mlforge validate

# Validate specific features
mlforge validate --features merchant_transactions

# Validate by tag
mlforge validate --tags transactions
```

This is useful for:
- Testing new validators before building
- Validating source data changes
- CI/CD data quality checks

## Best Practices

### 1. Validate at the Source

Add validators close to where data enters your feature store:

```python
@mlf.feature(
    keys=["user_id"],
    source="raw/users.parquet",
    validators={
        "user_id": [mlf.not_null(), mlf.unique()],
        "created_at": [mlf.not_null()],
        "email": [mlf.not_null(), mlf.matches_regex(r"^\w+@\w+\.\w+$")],
    }
)
def user_base_features(df):
    return df
```

### 2. Use Validators for Assumptions

Document assumptions your feature logic makes:

```python
@mlf.feature(
    keys=["transaction_id"],
    source="transactions.parquet",
    validators={
        "amount": [mlf.greater_than(0)],  # Feature assumes positive amounts
    }
)
def transaction_features(df):
    # This logic assumes amount > 0
    return df.with_columns([
        (100.0 / pl.col("amount")).alias("amount_inverse")
    ])
```

### 3. Keep Validators Simple

Each validator should check one thing:

```python
# Good: Each validator checks one aspect
validators={
    "age": [mlf.not_null(), mlf.greater_than(0), mlf.less_than(150)]
}

# Bad: Complex multi-condition validator
validators={
    "age": [validate_age_is_valid_and_reasonable_and_not_null()]
}
```

### 4. Provide Clear Error Messages

Make validation failures actionable:

```python
def is_valid_phone_number() -> Validator:
    def validate(series: pl.Series) -> ValidationResult:
        invalid = series.filter(~series.str.contains(r"^\+?\d{10,15}$"))

        if len(invalid) > 0:
            return ValidationResult(
                passed=False,
                message=f"{len(invalid)} invalid phone numbers (expected format: +1234567890)",
                failed_count=len(invalid),
            )

        return ValidationResult(passed=True)

    return Validator(name="is_valid_phone_number", fn=validate)
```

### 5. Test Your Validators

Write tests for custom validators:

```python
def test_min_length_validator():
    series = pl.Series(["abc", "ab", "a"])
    validator = min_length(3)
    result = validator(series)

    assert not result.passed
    assert result.failed_count == 2  # "ab" and "a" are too short
```

## See Also

- [Validators API Reference](../api/validators.md) - Complete API documentation
- [Validation API Reference](../api/validation.md) - Validation execution internals
- [Building Features](building-features.md) - How validation fits into the build process
- [Feature Metadata](feature-metadata.md) - How validators appear in metadata
