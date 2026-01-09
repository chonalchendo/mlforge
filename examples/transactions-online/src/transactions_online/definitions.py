"""
Feature store definitions with profile-based configuration.

This example demonstrates configuring stores via mlforge.yaml profiles:
- offline: LocalStore only (for development)
- online: LocalStore + RedisStore (for real-time serving)

Usage:
    # Build to offline store (default profile)
    mlforge build

    # Build to online store (requires Redis)
    mlforge build --profile online --online
"""

import mlforge as mlf

from transactions_online import features

defs = mlf.Definitions(
    name="Transactions Online Example",
    features=[features],
    # Stores configured via mlforge.yaml profiles
)
