# Transactions PySpark Example

This example demonstrates using mlforge with Apache PySpark for distributed feature computation.

## Quick Start (Docker)

The easiest way to try this example is with Docker - no Java installation required:

```bash
cd examples/transactions-pyspark

# List features
./run.sh list features

# Build all features
./run.sh build

# Build a specific feature
./run.sh build --features merchant_spend_pyspark

# Inspect a feature
./run.sh inspect feature merchant_spend_pyspark

# Interactive shell (for debugging)
./run.sh shell
```

The first run builds the Docker image (~2 minutes). Subsequent runs are fast.

Built features are persisted in `./feature_store/` on your local machine.

## Local Setup (requires Java)

If you prefer running locally:

```bash
# macOS: Install Java
brew install openjdk@17
export JAVA_HOME=$(brew --prefix openjdk@17)
export PATH="$JAVA_HOME/bin:$PATH"

# Linux: Install Java
sudo apt-get install openjdk-17-jre-headless
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Verify Java
java -version

# Run mlforge commands
uv run mlforge build
uv run mlforge list features
```

## Key Differences from Polars Examples

| Aspect | Polars Example | PySpark Example |
|--------|----------------|-----------------|
| Type hints | `polars.DataFrame` | `pyspark.sql.DataFrame` |
| Transformations | `pl.col("x")` | `F.col("x")` |
| Engine | `engine="polars"` (default) | `engine="pyspark"` |
| Requirements | None | Java 8+ runtime |

## Feature Definition Example

```python
from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F

import mlforge as mlf

@mlf.feature(
    source=source,
    entities=[user],
    timestamp="event_time",
    interval="1d",
    metrics=[mlf.Rolling(windows=["7d"], aggregations={"amt": ["sum"]})],
    engine="pyspark",
)
def user_spend(df: SparkDataFrame) -> SparkDataFrame:
    return df.select(
        F.col("user_id"),
        F.to_timestamp(F.col("event_time")).alias("event_time"),
        F.col("amt"),
    )
```

## Custom SparkSession

For production use cases with custom Spark configuration:

```python
from pyspark.sql import SparkSession
from mlforge.engines import PySparkEngine

# Create custom SparkSession
spark = SparkSession.builder \
    .appName("my-feature-pipeline") \
    .config("spark.sql.shuffle.partitions", "200") \
    .config("spark.executor.memory", "4g") \
    .getOrCreate()

# Use with mlforge
engine = PySparkEngine(spark=spark)
result = engine.execute(my_feature)
```

## Databricks Integration

On Databricks, mlforge automatically detects the existing SparkSession:

```python
# In a Databricks notebook - no configuration needed
import mlforge as mlf

defs = mlf.Definitions(
    name="my-project",
    features=[features],
    offline_store=mlf.LocalStore("/dbfs/feature_store"),
    default_engine="pyspark",
)

# Uses the notebook's SparkSession automatically
defs.build()
```

## Docker Commands Reference

```bash
# Build the image manually
docker compose build

# Run any mlforge command
docker compose run --rm mlforge-pyspark mlforge <command>

# Open interactive shell
docker compose run --rm mlforge-pyspark bash

# View logs with more detail
SPARK_LOG_LEVEL=INFO ./run.sh build

# Clean up
docker compose down
docker rmi mlforge-pyspark
```
