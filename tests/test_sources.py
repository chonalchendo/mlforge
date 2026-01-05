"""Tests for the sources module (Source and Format classes)."""

import pytest
from pydantic import ValidationError

import mlforge.sources as sources
from mlforge.sources import CSVFormat, DeltaFormat, ParquetFormat, Source


class TestParquetFormat:
    """Tests for ParquetFormat Pydantic model."""

    def test_default_values(self):
        """ParquetFormat should have sensible defaults."""
        fmt = ParquetFormat()
        assert fmt.row_groups is None
        assert fmt.columns is None

    def test_with_columns(self):
        """ParquetFormat should accept column selection."""
        fmt = ParquetFormat(columns=["user_id", "amount"])
        assert fmt.columns == ["user_id", "amount"]

    def test_with_row_groups(self):
        """ParquetFormat should accept row group selection."""
        fmt = ParquetFormat(row_groups=[0, 1])
        assert fmt.row_groups == [0, 1]

    def test_is_frozen(self):
        """ParquetFormat should be immutable."""
        fmt = ParquetFormat()
        with pytest.raises(ValidationError):
            fmt.columns = ["id"]  # type: ignore

    def test_equality(self):
        """ParquetFormat instances with same values should be equal."""
        fmt1 = ParquetFormat(columns=["id"])
        fmt2 = ParquetFormat(columns=["id"])
        assert fmt1 == fmt2

    def test_negative_row_group_raises(self):
        """ParquetFormat should reject negative row group indices."""
        with pytest.raises(
            ValidationError, match="Row group index must be >= 0"
        ):
            ParquetFormat(row_groups=[0, -1, 2])


class TestCSVFormat:
    """Tests for CSVFormat Pydantic model."""

    def test_default_values(self):
        """CSVFormat should have sensible defaults."""
        fmt = CSVFormat()
        assert fmt.delimiter == ","
        assert fmt.has_header is True
        assert fmt.quote_char == '"'
        assert fmt.skip_rows == 0

    def test_custom_delimiter(self):
        """CSVFormat should accept custom delimiter."""
        fmt = CSVFormat(delimiter="|")
        assert fmt.delimiter == "|"

    def test_tab_delimiter(self):
        """CSVFormat should accept tab delimiter."""
        fmt = CSVFormat(delimiter="\t")
        assert fmt.delimiter == "\t"

    def test_no_header(self):
        """CSVFormat should accept has_header=False."""
        fmt = CSVFormat(has_header=False)
        assert fmt.has_header is False

    def test_skip_rows(self):
        """CSVFormat should accept skip_rows."""
        fmt = CSVFormat(skip_rows=2)
        assert fmt.skip_rows == 2

    def test_is_frozen(self):
        """CSVFormat should be immutable."""
        fmt = CSVFormat()
        with pytest.raises(ValidationError):
            fmt.delimiter = "|"  # type: ignore

    def test_delimiter_must_be_single_char(self):
        """CSVFormat delimiter must be exactly 1 character."""
        with pytest.raises(ValidationError):
            CSVFormat(delimiter="||")

    def test_delimiter_cannot_be_empty(self):
        """CSVFormat delimiter cannot be empty."""
        with pytest.raises(ValidationError):
            CSVFormat(delimiter="")

    def test_quote_char_must_be_single_char(self):
        """CSVFormat quote_char must be exactly 1 character."""
        with pytest.raises(ValidationError):
            CSVFormat(quote_char="''")

    def test_negative_skip_rows_raises(self):
        """CSVFormat should reject negative skip_rows."""
        with pytest.raises(ValidationError):
            CSVFormat(skip_rows=-1)


class TestDeltaFormat:
    """Tests for DeltaFormat Pydantic model."""

    def test_default_values(self):
        """DeltaFormat should default to latest version."""
        fmt = DeltaFormat()
        assert fmt.version is None

    def test_specific_version(self):
        """DeltaFormat should accept specific version."""
        fmt = DeltaFormat(version=5)
        assert fmt.version == 5

    def test_is_frozen(self):
        """DeltaFormat should be immutable."""
        fmt = DeltaFormat()
        with pytest.raises(ValidationError):
            fmt.version = 10  # type: ignore

    def test_negative_version_raises(self):
        """DeltaFormat should reject negative version."""
        with pytest.raises(ValidationError):
            DeltaFormat(version=-1)

    def test_zero_version_allowed(self):
        """DeltaFormat should allow version 0."""
        fmt = DeltaFormat(version=0)
        assert fmt.version == 0


class TestSourceFormatDetection:
    """Tests for Source format auto-detection."""

    def test_parquet_detection(self):
        """Source should auto-detect parquet format."""
        source = Source("data/transactions.parquet")
        assert isinstance(source.format, ParquetFormat)

    def test_csv_detection(self):
        """Source should auto-detect csv format."""
        source = Source("data/events.csv")
        assert isinstance(source.format, CSVFormat)

    def test_delta_detection_for_directory(self):
        """Source should detect delta for directories without extension."""
        source = Source("data/delta_table/")
        assert isinstance(source.format, DeltaFormat)

    def test_explicit_format_overrides_detection(self):
        """Explicit format should override auto-detection."""
        source = Source("data/events.csv", format=ParquetFormat())
        assert isinstance(source.format, ParquetFormat)

    def test_unknown_extension_raises(self):
        """Source should raise for unknown extensions."""
        with pytest.raises(ValueError, match="Cannot auto-detect format"):
            Source("data/file.json")

    def test_uppercase_extension(self):
        """Source should handle uppercase extensions."""
        source = Source("data/transactions.PARQUET")
        assert isinstance(source.format, ParquetFormat)


class TestSourceLocationInference:
    """Tests for Source location inference."""

    def test_local_path(self):
        """Source should infer local location for regular paths."""
        source = Source("data/transactions.parquet")
        assert source.location == "local"
        assert source.is_local is True
        assert source.is_s3 is False
        assert source.is_gcs is False

    def test_s3_path(self):
        """Source should infer S3 location from s3:// prefix."""
        source = Source("s3://bucket/transactions.parquet")
        assert source.location == "s3"
        assert source.is_local is False
        assert source.is_s3 is True
        assert source.is_gcs is False

    def test_gcs_path(self):
        """Source should infer GCS location from gs:// prefix."""
        source = Source("gs://bucket/transactions.parquet")
        assert source.location == "gcs"
        assert source.is_local is False
        assert source.is_s3 is False
        assert source.is_gcs is True


class TestSourceNameInference:
    """Tests for Source name auto-derivation."""

    def test_name_from_local_path(self):
        """Source should derive name from local path stem."""
        source = Source("data/transactions.parquet")
        assert source.name == "transactions"

    def test_name_from_nested_path(self):
        """Source should derive name from nested path."""
        source = Source("path/to/data/events.csv")
        assert source.name == "events"

    def test_name_from_s3_path(self):
        """Source should derive name from S3 path."""
        source = Source("s3://bucket/data/transactions.parquet")
        assert source.name == "transactions"

    def test_name_from_gcs_path(self):
        """Source should derive name from GCS path."""
        source = Source("gs://bucket/data/events.parquet")
        assert source.name == "events"

    def test_explicit_name_overrides(self):
        """Explicit name should override auto-derivation."""
        source = Source("data/transactions.parquet", name="my_source")
        assert source.name == "my_source"

    def test_name_from_directory(self):
        """Source should derive name from directory path."""
        source = Source("data/delta_table/")
        assert source.name == "delta_table"


class TestSourceFormatProperties:
    """Tests for Source format type properties."""

    def test_is_parquet(self):
        """is_parquet should return True for parquet sources."""
        source = Source("data.parquet")
        assert source.is_parquet is True
        assert source.is_csv is False
        assert source.is_delta is False

    def test_is_csv(self):
        """is_csv should return True for CSV sources."""
        source = Source("data.csv")
        assert source.is_csv is True
        assert source.is_parquet is False
        assert source.is_delta is False

    def test_is_delta(self):
        """is_delta should return True for Delta sources."""
        source = Source("delta_table/", format=DeltaFormat())
        assert source.is_delta is True
        assert source.is_parquet is False
        assert source.is_csv is False


class TestSourceImmutability:
    """Tests for Source immutability."""

    def test_source_is_frozen(self):
        """Source should be immutable."""
        source = Source("data.parquet")
        with pytest.raises(AttributeError):
            source.path = "other.parquet"  # type: ignore

    def test_source_equality(self):
        """Source instances with same values should be equal."""
        source1 = Source("data.parquet", name="data")
        source2 = Source("data.parquet", name="data")
        assert source1 == source2


class TestSourceWithCSVFormat:
    """Tests for Source with CSVFormat options."""

    def test_csv_with_custom_delimiter(self):
        """Source should accept CSV with custom delimiter."""
        source = Source(
            "data/events.csv",
            format=CSVFormat(delimiter="|"),
        )
        assert source.is_csv
        assert source.format.delimiter == "|"  # type: ignore

    def test_csv_with_multiple_options(self):
        """Source should accept CSV with multiple format options."""
        source = Source(
            "data/events.csv",
            format=CSVFormat(
                delimiter="\t",
                has_header=False,
                skip_rows=2,
            ),
        )
        fmt = source.format
        assert isinstance(fmt, CSVFormat)
        assert fmt.delimiter == "\t"
        assert fmt.has_header is False
        assert fmt.skip_rows == 2


class TestSourceWithDeltaFormat:
    """Tests for Source with DeltaFormat options."""

    def test_delta_with_version(self):
        """Source should accept Delta with specific version."""
        source = Source(
            "s3://bucket/delta_table/",
            format=DeltaFormat(version=5),
        )
        assert source.is_delta
        assert source.format.version == 5  # type: ignore


class TestFormatTypeAlias:
    """Tests for the Format type alias."""

    def test_format_alias_includes_all_formats(self):
        """Format type should include all format classes."""
        # These should all be valid Format types
        formats: list[sources.Format] = [
            ParquetFormat(),
            CSVFormat(),
            DeltaFormat(),
        ]
        assert len(formats) == 3
