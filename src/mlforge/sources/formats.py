"""
Format configuration classes for data sources.

These classes provide typed, validated configuration for different file formats.
Each format class contains only parameters relevant to that format, following
Ousterhout's principle of avoiding shallow modules.

Uses Pydantic for validation:
- Field constraints are validated at instantiation time
- Clear error messages when validation fails
- Consistent with profiles configuration pattern

Usage:
    import mlforge as mlf

    # Parquet with column selection
    source = mlf.Source("data.parquet", format=mlf.ParquetFormat(columns=["id", "name"]))

    # CSV with custom delimiter
    source = mlf.Source("data.csv", format=mlf.CSVFormat(delimiter="|"))

    # Delta Lake with specific version
    source = mlf.Source("delta_table/", format=mlf.DeltaFormat(version=5))
"""

from pydantic import BaseModel, Field, field_validator


class ParquetFormat(BaseModel, frozen=True):
    """
    Parquet format configuration.

    Attributes:
        row_groups: Specific row groups to read (None = all). Must be non-negative.
        columns: Specific columns to read (None = all)

    Example:
        # Read only specific columns
        ParquetFormat(columns=["user_id", "amount"])

        # Read specific row groups
        ParquetFormat(row_groups=[0, 1])
    """

    row_groups: list[int] | None = None
    columns: list[str] | None = None

    @field_validator("row_groups")
    @classmethod
    def validate_row_groups(cls, v: list[int] | None) -> list[int] | None:
        """Validate all row group indices are non-negative."""
        if v is not None:
            for idx in v:
                if idx < 0:
                    msg = f"Row group index must be >= 0, got {idx}"
                    raise ValueError(msg)
        return v


class CSVFormat(BaseModel, frozen=True):
    """
    CSV format configuration.

    Attributes:
        delimiter: Field separator character (default: ","). Must be exactly 1 character.
        has_header: Whether first row is header (default: True)
        quote_char: Character for quoting fields (default: '"'). Must be exactly 1 character.
        skip_rows: Number of rows to skip at start (default: 0). Must be >= 0.

    Example:
        # Pipe-delimited file
        CSVFormat(delimiter="|")

        # Tab-delimited without header
        CSVFormat(delimiter="\\t", has_header=False)

        # Skip comment rows at start
        CSVFormat(skip_rows=2)

    Raises:
        ValidationError: If delimiter or quote_char is not exactly 1 character,
            or if skip_rows is negative.
    """

    delimiter: str = Field(default=",", min_length=1, max_length=1)
    has_header: bool = True
    quote_char: str = Field(default='"', min_length=1, max_length=1)
    skip_rows: int = Field(default=0, ge=0)


class DeltaFormat(BaseModel, frozen=True):
    """
    Delta Lake format configuration.

    Attributes:
        version: Specific table version to read (None = latest). Must be >= 0 if specified.

    Example:
        # Read latest version
        DeltaFormat()

        # Read specific historical version
        DeltaFormat(version=5)

    Raises:
        ValidationError: If version is negative.
    """

    version: int | None = Field(default=None, ge=0)


# Type alias for any format
Format = ParquetFormat | CSVFormat | DeltaFormat
