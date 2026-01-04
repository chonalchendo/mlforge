import mlforge as mlf
from transactions import features

defs = mlf.Definitions(
    name="Transactions features.",
    features=[features],
    offline_store=mlf.LocalStore(path="./feature_store"),
    # default_engine="polars",  # Use polars for small datasets
    # offline_store=mlf.S3Store(bucket="mlforge-example", prefix="features/"),
)
