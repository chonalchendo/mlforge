"""Entity definitions for fraud detection."""

import mlforge as mlf

user = mlf.Entity(
    name="user",
    join_key="user_id",
    from_columns=["first", "last", "dob"],
)

merchant = mlf.Entity(
    name="merchant",
    join_key="merchant_id",
    from_columns=["merchant"],
)

card = mlf.Entity(
    name="card",
    join_key="card_id",
    from_columns=["cc_num"],
)
