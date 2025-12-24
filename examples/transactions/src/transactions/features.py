from datetime import timedelta

import polars as pl

from mlforge import Rolling, entity_key, feature

SOURCE = "data/transactions.parquet"

USER_KEY = "user_id"
MERCHANT_KEY = "merchant_id"
ACCOUNT_KEY = "account_id"

with_merchant_id = entity_key("merchant", alias=MERCHANT_KEY)
with_account_id = entity_key("cc_num", alias=ACCOUNT_KEY)
with_user_id = entity_key("first", "last", "dob", alias=USER_KEY)

### Metrics

spend_metrics = Rolling(
    windows=[timedelta(days=7), "30d", "90d"],
    aggregations={"amt": ["count", "mean", "sum"]},
)


### MERCHANT FEATURES


@feature(
    source=SOURCE,
    keys=[MERCHANT_KEY],
    tags=["merchants"],
    description="Total spend by merchant ID",
    timestamp="transaction_date",
    interval=timedelta(days=1),
    metrics=[spend_metrics],
)
def merchant_spend_1d_interval(df: pl.DataFrame) -> pl.DataFrame:
    return df.pipe(with_merchant_id).select(
        pl.col("merchant_id"),
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_date"),
        pl.col("amt"),
    )


### ACCOUNT FEATURES


@feature(
    source=SOURCE,
    keys=[ACCOUNT_KEY],
    tags=["accounts"],
    description="Total spend by account ID",
    timestamp="transaction_date",
    interval="7d",
    metrics=[spend_metrics],
)
def account_spend_7d_interval(df: pl.DataFrame) -> pl.DataFrame:
    return df.pipe(with_account_id).select(
        pl.col("account_id"),
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_date"),
        pl.col("amt"),
    )


### USER FEATURES


@feature(
    keys=[USER_KEY],
    source=SOURCE,
    tags=["users"],
    description="Total spend by user ID",
    timestamp="transaction_date",
    interval=timedelta(days=30),
    metrics=[spend_metrics],
)
def user_spend_30d_interval(df: pl.DataFrame) -> pl.DataFrame:
    return df.pipe(with_user_id).select(
        pl.col("user_id"),
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_date"),
        pl.col("amt"),
    )
