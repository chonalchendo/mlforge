# Storage Backends

mlforge supports multiple storage backends for persisting built features. Choose the backend that best fits your deployment environment.

## LocalStore

The default storage backend that writes features to the local filesystem as Parquet files.

### Basic Usage

```python
from mlforge import Definitions, LocalStore
import features

defs = Definitions(
    name="my-project",
    features=[features],
    offline_store=LocalStore(path="./feature_store")
)
```

### Configuration

```python
from pathlib import Path

# Using string path
store = LocalStore(path="./feature_store")

# Using Path object
store = LocalStore(path=Path("./feature_store"))

# Custom location
store = LocalStore(path=Path.home() / "ml_projects" / "features")
```

### Storage Format

Each feature is stored as an individual Parquet file:

```
feature_store/
├── user_total_spend.parquet
├── user_avg_spend.parquet
└── product_popularity.parquet
```

### When to Use

- **Local development** - Fast iteration and debugging
- **Small datasets** - Features fit on local disk
- **Single machine deployments** - No distributed infrastructure needed
- **CI/CD pipelines** - Ephemeral feature stores for testing

## S3Store

Cloud storage backend for Amazon S3, supporting distributed access and production deployments.

### Basic Usage

```python
from mlforge import Definitions, S3Store
import features

defs = Definitions(
    name="my-project",
    features=[features],
    offline_store=S3Store(
        bucket="mlforge-features",
        prefix="prod/features"
    )
)
```

### Configuration

```python
# With prefix (recommended for organization)
store = S3Store(
    bucket="my-bucket",
    prefix="prod/features"  # Features stored at s3://my-bucket/prod/features/
)

# Without prefix (bucket root)
store = S3Store(
    bucket="my-bucket",
    prefix=""  # Features stored at s3://my-bucket/
)

# With explicit region
store = S3Store(
    bucket="my-bucket",
    prefix="prod/features",
    region="us-west-2"
)
```

### AWS Credentials

S3Store uses standard AWS credential resolution:

=== "Environment Variables"

    ```bash
    export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    export AWS_DEFAULT_REGION=us-east-1
    ```

=== "AWS CLI Configuration"

    ```bash
    aws configure
    # AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
    # AWS Secret Access Key: ****
    # Default region name: us-east-1
    # Default output format: json
    ```

=== "IAM Role (EC2/ECS/Lambda)"

    When running on AWS services, use IAM roles instead of static credentials:

    ```python
    # No credentials needed - uses instance/task role
    store = S3Store(bucket="mlforge-features", prefix="prod")
    ```

### Storage Format

Features are stored in S3 with the same Parquet format:

```
s3://mlforge-features/prod/features/
├── user_total_spend.parquet
├── user_avg_spend.parquet
└── product_popularity.parquet
```

### IAM Policy

Your AWS credentials need appropriate S3 permissions. Here's a minimal IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "mlforgeFeatureStoreAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mlforge-features",
        "arn:aws:s3:::mlforge-features/*"
      ]
    }
  ]
}
```

#### Read-Only Access

For production environments where only feature retrieval is needed:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "mlforgeFeatureStoreReadOnly",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mlforge-features",
        "arn:aws:s3:::mlforge-features/*"
      ]
    }
  ]
}
```

#### Write-Only Access

For feature build pipelines that only write features:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "mlforgeFeatureStoreWriteOnly",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mlforge-features",
        "arn:aws:s3:::mlforge-features/*"
      ]
    }
  ]
}
```

#### Prefix-Based Access Control

Restrict access to specific prefixes (e.g., `prod/` vs `dev/`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "mlforgeProductionAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mlforge-features",
        "arn:aws:s3:::mlforge-features/prod/*"
      ],
      "Condition": {
        "StringLike": {
          "s3:prefix": ["prod/*"]
        }
      }
    }
  ]
}
```

### When to Use

- **Production deployments** - Centralized, durable storage
- **Team collaboration** - Shared feature store across multiple users
- **Large datasets** - Features too large for local disk
- **Multi-environment workflows** - Separate dev/staging/prod prefixes
- **CI/CD pipelines** - Build features in one environment, use in another

### Error Handling

```python
from mlforge import S3Store

try:
    store = S3Store(bucket="nonexistent-bucket", prefix="features")
except ValueError as e:
    print(f"Bucket error: {e}")
    # Bucket 'nonexistent-bucket' does not exist or is not accessible.
    # Ensure the bucket is created and credentials have appropriate permissions.
```

Common issues:

1. **Bucket doesn't exist** - Create the bucket first using AWS Console or CLI
2. **Missing permissions** - Verify IAM policy allows required S3 actions
3. **Wrong region** - Specify `region` parameter if bucket is in non-default region
4. **Invalid credentials** - Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

## Complete Example

### Local Development

```python
from mlforge import Definitions, LocalStore, feature
import polars as pl

@feature(keys=["user_id"], source="data/transactions.parquet")
def user_total_spend(df):
    return df.group_by("user_id").agg(
        pl.col("amount").sum().alias("total_spend")
    )

# Local development - fast iteration
defs = Definitions(
    name="user-features",
    features=[user_total_spend],
    offline_store=LocalStore("./dev_features")
)

defs.build()
```

### Production Deployment

```python
from mlforge import Definitions, S3Store, feature
import polars as pl
import os

@feature(keys=["user_id"], source="s3://my-bucket/data/transactions.parquet")
def user_total_spend(df):
    return df.group_by("user_id").agg(
        pl.col("amount").sum().alias("total_spend")
    )

# Production - S3 storage
environment = os.getenv("ENVIRONMENT", "dev")

defs = Definitions(
    name="user-features",
    features=[user_total_spend],
    offline_store=S3Store(
        bucket="mlforge-features",
        prefix=f"{environment}/features"  # dev/features or prod/features
    )
)

defs.build()
```

### Multi-Environment Setup

```python
from mlforge import Definitions, S3Store, LocalStore
import os

def get_store():
    """Get appropriate store based on environment."""
    env = os.getenv("ENVIRONMENT", "local")

    if env == "local":
        return LocalStore("./feature_store")
    elif env == "dev":
        return S3Store(bucket="mlforge-features", prefix="dev/features")
    elif env == "staging":
        return S3Store(bucket="mlforge-features", prefix="staging/features")
    elif env == "prod":
        return S3Store(bucket="mlforge-features-prod", prefix="features")
    else:
        raise ValueError(f"Unknown environment: {env}")

defs = Definitions(
    name="user-features",
    features=[...],
    offline_store=get_store()
)
```

Usage:

```bash
# Local development
ENVIRONMENT=local python build_features.py

# Dev environment
ENVIRONMENT=dev python build_features.py

# Production
ENVIRONMENT=prod python build_features.py
```

## Performance Considerations

### LocalStore

**Pros:**
- Fastest for small datasets (no network overhead)
- Simple setup (no credentials required)
- Works offline

**Cons:**
- Limited by local disk space
- Not suitable for distributed deployments
- No built-in backup/versioning

### S3Store

**Pros:**
- Virtually unlimited storage
- High durability (99.999999999%)
- Built-in versioning (if enabled on bucket)
- Accessible from anywhere

**Cons:**
- Network latency for read/write operations
- Data transfer costs for large datasets
- Requires AWS credentials

### Optimization Tips

**For S3Store:**

1. **Use same region** - Colocate compute and S3 bucket to minimize latency
2. **Enable S3 Transfer Acceleration** - For cross-region access
3. **Batch operations** - Materialize multiple features in one run
4. **Use IAM roles** - Avoid credential management overhead

```python
# Good: Batch materialization
defs.build()  # Builds all features

# Less efficient: Individual feature builds
for feature_name in ["feature1", "feature2", "feature3"]:
    defs.materialize(feature_names=[feature_name])
```

## Next Steps

- [Building Features](building-features.md) - Build features to storage
- [Retrieving Features](retrieving-features.md) - Read features from storage
- [Store API Reference](../api/store.md) - Detailed API documentation
