"""
Entity definition for feature stores.

Entities represent the subjects of features (users, merchants, accounts, etc.)
with explicit join keys and optional surrogate key generation from source columns.

Usage:
    import mlforge as mlf

    # Simple entity - direct column passthrough
    merchant = mlf.Entity(name="merchant", join_key="merchant_id")

    # Surrogate key from multiple columns
    user = mlf.Entity(
        name="user",
        join_key="user_id",
        from_columns=["first", "last", "dob"],
    )

    # Use in feature definition
    @mlf.feature(source="data.parquet", entities=[user])
    def user_spend(df):
        return df.select("user_id", "amount")
"""

from pydantic import BaseModel, Field, field_validator, model_validator


class Entity(BaseModel, frozen=True):
    """
    Entity definition with optional surrogate key generation.

    An entity represents a subject (user, merchant, etc.) with a join key
    that uniquely identifies it. When `from_columns` is provided, the engine
    automatically generates the join key as a surrogate key by hashing those
    columns.

    Attributes:
        name: Logical name for the entity (e.g., "user", "merchant")
        join_key: Column name(s) that identify this entity in the output
        from_columns: Source columns to hash into a surrogate key (optional)

    Example:
        # Direct column passthrough
        merchant = Entity(name="merchant", join_key="merchant_id")

        # Surrogate key from multiple columns
        user = Entity(
            name="user",
            join_key="user_id",
            from_columns=["first", "last", "dob"],
        )

        # Composite key (multiple columns)
        user_merchant = Entity(
            name="user_merchant",
            join_key=["user_id", "merchant_id"],
        )
    """

    name: str = Field(..., min_length=1)
    join_key: str | list[str]
    from_columns: list[str] | None = None

    @field_validator("join_key")
    @classmethod
    def validate_join_key(cls, v: str | list[str]) -> str | list[str]:
        """Validate join_key is non-empty."""
        if isinstance(v, str):
            if not v:
                raise ValueError("join_key cannot be empty")
        elif isinstance(v, list):
            if not v:
                raise ValueError("join_key list cannot be empty")
            for key in v:
                if not key:
                    raise ValueError(
                        "join_key list cannot contain empty strings"
                    )
        return v

    @field_validator("from_columns")
    @classmethod
    def validate_from_columns(cls, v: list[str] | None) -> list[str] | None:
        """Validate from_columns if provided."""
        if v is not None:
            if not v:
                raise ValueError("from_columns cannot be empty list")
            for col in v:
                if not col:
                    raise ValueError(
                        "from_columns cannot contain empty strings"
                    )
        return v

    @model_validator(mode="after")
    def validate_surrogate_key_config(self) -> "Entity":
        """Validate that surrogate key config is consistent."""
        if self.from_columns is not None and isinstance(self.join_key, list):
            raise ValueError(
                "Cannot use from_columns with composite join_key. "
                "Surrogate key generation only supports single join_key."
            )
        return self

    @property
    def key_columns(self) -> list[str]:
        """
        Return join key as a list.

        Returns:
            List of join key column names
        """
        if isinstance(self.join_key, str):
            return [self.join_key]
        return self.join_key

    @property
    def requires_generation(self) -> bool:
        """
        Whether surrogate key needs to be generated.

        Returns:
            True if from_columns is specified, False otherwise
        """
        return self.from_columns is not None
