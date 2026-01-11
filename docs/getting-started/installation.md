# Installation

mlforge requires Python 3.13 or later.

## Install via pip

```bash
pip install mlforge-sdk
```

## Install via uv

```bash
uv add mlforge-sdk
```

## Optional Dependencies

Install extras for additional backends:

```bash
# Redis for online serving
pip install mlforge-sdk[redis]

# Google Cloud Storage
pip install mlforge-sdk[gcs]

# DuckDB compute engine
pip install mlforge-sdk[duckdb]

# All extras
pip install mlforge-sdk[all]
```

## Verify Installation

Check that mlforge is installed:

```bash
mlforge --help
```

You should see:

```
Usage: mlforge [OPTIONS] COMMAND

A simple feature store SDK

Commands:
  init       Initialize a new mlforge project
  build      Materialize features to offline storage
  validate   Run validation checks on features
  list       List features, entities, sources, or versions
  inspect    Inspect features, entities, or sources
  ...
```

## Development Installation

To contribute or run from source:

```bash
git clone https://github.com/chonalchendo/mlforge.git
cd mlforge
uv sync
```

## Next Steps

Continue to the [Quickstart Guide](quickstart.md) to build your first feature store.
