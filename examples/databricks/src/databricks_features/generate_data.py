#!/usr/bin/env python3
"""Generate synthetic credit card transaction data.

Creates realistic transaction data with:
- Multiple customers with distinct spending patterns
- Various merchant categories
- Temporal patterns (weekday vs weekend, time of day)
- Fraud-like anomalies for testing

Usage:
    uv run python src/databricks_features/generate_data.py
    uv run python src/databricks_features/generate_data.py --rows 10000
"""

import argparse
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl


def generate_customer_id(first: str, last: str, dob: str) -> str:
    """Generate deterministic surrogate key matching mlforge's algorithm."""
    data = f"{first}{last}{dob}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def generate_merchant_id(merchant_name: str) -> str:
    """Generate deterministic surrogate key for merchant."""
    return hashlib.sha256(merchant_name.encode()).hexdigest()[:16]


def generate_transactions(
    n_rows: int = 5000,
    n_customers: int = 100,
    n_merchants: int = 50,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    seed: int = 42,
) -> pl.DataFrame:
    """Generate synthetic credit card transactions.

    Args:
        n_rows: Number of transactions to generate
        n_customers: Number of unique customers
        n_merchants: Number of unique merchants
        start_date: Start of transaction window
        end_date: End of transaction window
        seed: Random seed for reproducibility

    Returns:
        DataFrame with transaction data
    """
    random.seed(seed)

    if start_date is None:
        start_date = datetime(2024, 1, 1)
    if end_date is None:
        end_date = datetime(2024, 12, 31)

    # Generate customer profiles
    first_names = [
        "James",
        "Mary",
        "John",
        "Patricia",
        "Robert",
        "Jennifer",
        "Michael",
        "Linda",
        "David",
        "Elizabeth",
        "William",
        "Barbara",
        "Richard",
        "Susan",
        "Joseph",
        "Jessica",
        "Thomas",
        "Sarah",
        "Charles",
        "Karen",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
        "Hernandez",
        "Lopez",
        "Gonzalez",
        "Wilson",
        "Anderson",
        "Thomas",
        "Taylor",
        "Moore",
        "Jackson",
        "Martin",
    ]

    customers = []
    for i in range(n_customers):
        first = random.choice(first_names)
        last = random.choice(last_names)
        # Generate DOB between 1960 and 2000
        year = random.randint(1960, 2000)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        dob = f"{year}-{month:02d}-{day:02d}"

        customers.append(
            {
                "first_name": first,
                "last_name": last,
                "date_of_birth": dob,
                "customer_id": generate_customer_id(first, last, dob),
                # Spending profile: low, medium, high
                "spending_profile": random.choice(["low", "medium", "high"]),
            }
        )

    # Generate merchant profiles
    merchant_categories = [
        "grocery",
        "restaurant",
        "gas_station",
        "online_retail",
        "entertainment",
        "travel",
        "healthcare",
        "utilities",
    ]
    merchant_names = []
    for category in merchant_categories:
        for i in range(n_merchants // len(merchant_categories) + 1):
            merchant_names.append(f"{category}_{i:03d}")

    merchants = []
    for name in merchant_names[:n_merchants]:
        category = name.split("_")[0]
        merchants.append(
            {
                "merchant_name": name,
                "merchant_id": generate_merchant_id(name),
                "merchant_category": category,
                # Average transaction amount varies by category
                "avg_amount": {
                    "grocery": 75,
                    "restaurant": 45,
                    "gas_station": 50,
                    "online_retail": 100,
                    "entertainment": 60,
                    "travel": 500,
                    "healthcare": 150,
                    "utilities": 120,
                }.get(category, 50),
            }
        )

    # Generate transactions
    transactions = []
    time_range = (end_date - start_date).total_seconds()

    for i in range(n_rows):
        customer = random.choice(customers)
        merchant = random.choice(merchants)

        # Random timestamp within range
        random_seconds = random.random() * time_range
        tx_time = start_date + timedelta(seconds=random_seconds)

        # Amount based on customer profile and merchant category
        base_amount = merchant["avg_amount"]
        if customer["spending_profile"] == "low":
            amount = base_amount * random.uniform(0.3, 0.8)
        elif customer["spending_profile"] == "high":
            amount = base_amount * random.uniform(1.2, 3.0)
        else:
            amount = base_amount * random.uniform(0.7, 1.5)

        # Add some noise and round to 2 decimal places
        amount = round(amount * random.uniform(0.8, 1.2), 2)

        # Is this an online transaction?
        is_online = merchant["merchant_category"] in [
            "online_retail",
            "utilities",
        ]
        if not is_online:
            is_online = random.random() < 0.1  # 10% chance for other categories

        # Simulate some fraud patterns (5% of transactions)
        is_fraud = False
        if random.random() < 0.05:
            is_fraud = True
            # Fraud often involves unusual amounts or patterns
            if random.random() < 0.5:
                amount = amount * random.uniform(5, 20)  # Unusually high
            else:
                # Multiple small transactions
                amount = round(random.uniform(1, 10), 2)

        transactions.append(
            {
                "transaction_id": f"txn_{i:08d}",
                "transaction_time": tx_time.strftime("%Y-%m-%d %H:%M:%S"),
                "first_name": customer["first_name"],
                "last_name": customer["last_name"],
                "date_of_birth": customer["date_of_birth"],
                "customer_id": customer["customer_id"],
                "merchant_name": merchant["merchant_name"],
                "merchant_id": merchant["merchant_id"],
                "merchant_category": merchant["merchant_category"],
                "amount": amount,
                "is_online": is_online,
                "is_fraud": is_fraud,
            }
        )

    # Create DataFrame and sort by time
    df = pl.DataFrame(transactions).sort("transaction_time")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic transaction data"
    )
    parser.add_argument(
        "--rows", type=int, default=5000, help="Number of transactions"
    )
    parser.add_argument(
        "--customers", type=int, default=100, help="Number of customers"
    )
    parser.add_argument(
        "--merchants", type=int, default=50, help="Number of merchants"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output",
        type=str,
        default="data/transactions.parquet",
        help="Output file path",
    )
    args = parser.parse_args()

    print(f"Generating {args.rows} transactions...")
    df = generate_transactions(
        n_rows=args.rows,
        n_customers=args.customers,
        n_merchants=args.merchants,
        seed=args.seed,
    )

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to parquet
    df.write_parquet(output_path)

    print(f"\nGenerated data saved to: {output_path}")
    print(f"Shape: {df.shape}")
    print(f"Customers: {df['customer_id'].n_unique()}")
    print(f"Merchants: {df['merchant_id'].n_unique()}")
    print(
        f"Date range: {df['transaction_time'].min()} to {df['transaction_time'].max()}"
    )
    print(f"Fraud rate: {df['is_fraud'].mean():.2%}")

    print("\nSample transactions:")
    print(
        df.select(
            "transaction_id",
            "transaction_time",
            "first_name",
            "last_name",
            "merchant_category",
            "amount",
            "is_fraud",
        ).head(5)
    )

    print("\nAmount statistics by merchant category:")
    print(
        df.group_by("merchant_category").agg(
            pl.col("amount").mean().alias("avg_amount"),
            pl.col("amount").std().alias("std_amount"),
            pl.len().alias("count"),
        )
    )


if __name__ == "__main__":
    main()
