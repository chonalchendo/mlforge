import polars as pl
import rich

from mlforge import get_training_data
from transactions.features import with_account_id, with_merchant_id, with_user_id


def main() -> None:
    entity_df = pl.read_parquet("data/transactions.parquet").with_columns(
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_date")
    )

    training_df = get_training_data(
        features=[
            "account_spend_7d_interval",
            "merchant_spend_1d_interval",
            "user_spend_30d_interval",
        ],
        entity_df=entity_df,
        entities=[with_account_id, with_merchant_id, with_user_id],
        timestamp="transaction_date",
        store="./feature_store",
    )

    rich.print(training_df.head())


if __name__ == "__main__":
    main()
