import polars as pl

from mlforge import entity_key, feature

SOURCE = "data/transactions.parquet"

USER_KEY = "user_id"
MERCHANT_KEY = "merchant_id"
ACCOUNT_KEY = "account_id"

with_merchant_id = entity_key("merchant", alias=MERCHANT_KEY)
with_account_id = entity_key("cc_num", alias=ACCOUNT_KEY)
with_user_id = entity_key("first", "last", "dob", alias=USER_KEY)


### MERCHANT FEATURES


@feature(
    source=SOURCE,
    keys=[MERCHANT_KEY],
    tags=["merchants"],
    description="Total spend by merchant ID",
)
def merchant_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_merchant_id)
        .group_by(MERCHANT_KEY)
        .agg(pl.col("amt").sum().alias("merchant_total_spend"))
    )


### ACCOUNT FEATURES


@feature(
    source=SOURCE,
    keys=[ACCOUNT_KEY],
    tags=["accounts"],
    description="Total spend by account ID",
)
def account_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_account_id)
        .group_by(ACCOUNT_KEY)
        .agg(pl.col("amt").sum().alias("account_total_spend"))
    )


### USER FEATURES


@feature(
    keys=[USER_KEY], source=SOURCE, tags=["users"], description="Total spend by user ID"
)
def user_total_spend(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_user_id)
        .group_by(USER_KEY)
        .agg(pl.col("amt").sum().alias("total_spend"))
    )


@feature(
    keys=[USER_KEY],
    source=SOURCE,
    tags=["users"],
    timestamp="feature_timestamp",
    description="User mean spend over 30d rolling window",
)
def user_spend_mean_30d(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.pipe(with_user_id)
        # User handles datetime conversion
        .with_columns(
            pl.col("trans_date_trans_time")
            .str.to_datetime("%Y-%m-%d %H:%M:%S")
            .alias("trans_dt")
        )
        .sort("trans_dt")
        .group_by_dynamic(
            "trans_dt",
            every="1d",
            period="30d",
            by=USER_KEY,
        )
        .agg(pl.col("amt").mean().alias("user_spend_mean_30d"))
        .rename({"trans_dt": "feature_timestamp"})
    )
