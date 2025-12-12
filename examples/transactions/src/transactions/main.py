import polars as pl
import rich

from mlforge import get_training_data
from transactions.features import with_account_id, with_merchant_id, with_user_id


def main() -> None:
    entity_df = pl.read_parquet("data/transactions.parquet").with_columns(
        pl.col("trans_date_trans_time").str.to_datetime("%Y-%m-%d %H:%M:%S")
    )

    training_df = get_training_data(
        features=[
            "account_total_spend",
            "merchant_total_spend",
            "user_total_spend",
            "user_spend_mean_30d",
        ],
        entity_df=entity_df,
        entities=[with_account_id, with_merchant_id, with_user_id],
        timestamp="trans_date_trans_time",
        store="./feature_store",
    )

    rich.print(training_df.head())


if __name__ == "__main__":
    main()
