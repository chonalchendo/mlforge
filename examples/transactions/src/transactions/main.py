import polars as pl
import rich

import mlforge as mlf
from mlforge import get_training_data
from transactions.features import account, merchant, user


def main() -> None:
    entity_df = pl.read_parquet("data/transactions.parquet").with_columns(
        pl.col("trans_date_trans_time")
        .str.to_datetime("%Y-%m-%d %H:%M:%S")
        .alias("transaction_date")
    )

    # Demonstrate all three feature input formats:
    # 1. String: all columns, latest version
    # 2. Tuple: all columns, pinned version
    # 3. FeatureSpec: specific columns and/or version
    training_df = get_training_data(
        features=[
            # String format - all columns, latest version
            "account_spend_7d_interval",
            # Tuple format - all columns, pinned version
            ("merchant_spend_1d_interval", "1.0.0"),
            # FeatureSpec - select specific column (memory efficient for wide features)
            mlf.FeatureSpec(
                name="user_spend_30d_interval",
                columns=["amt"],
            ),
        ],
        entity_df=entity_df,
        entities=[account, merchant, user],
        timestamp="transaction_date",
        store="./feature_store",
    )

    rich.print(training_df.head())


if __name__ == "__main__":
    main()
