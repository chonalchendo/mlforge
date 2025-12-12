# Installation

mlforge requires Python 3.13 or later.

## Install via pip

```bash
pip install mlforge
```

## Install via uv

```bash
uv add mlforge
```

## Dependencies

mlforge has the following core dependencies:

- **polars** (>=1.35.2) - DataFrame library for data transformations
- **pyarrow** (>=22.0.0) - Parquet file support
- **pydantic** (>=2.12.4) - Data validation
- **cyclopts** (>=4.2.1) - CLI framework
- **loguru** (>=0.7.3) - Logging

These will be installed automatically when you install mlforge.

## Verify Installation

Check that mlforge is installed correctly:

```bash
mlforge --help
```

You should see the CLI help output:

```
Usage: mlforge [OPTIONS] COMMAND

A simple feature store SDK

Commands:
  build  Materialize features to offline storage
  list   Display all registered features in a table
```

## Development Installation

If you want to contribute to mlforge or run it from source:

```bash
# Clone the repository
git clone https://github.com/chonalchendo/mlforge.git
cd mlforge

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Next Steps

Continue to the [Quickstart Guide](quickstart.md) to build your first feature.
