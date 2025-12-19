from transactions import features

from mlforge import Definitions, LocalStore, S3Store

defs = Definitions(
    name="Transactions features.",
    features=[features],
    # offline_store=LocalStore(path="./feature_store"),
    offline_store=S3Store(bucket="mlforge-example", prefix="features/"),
)
