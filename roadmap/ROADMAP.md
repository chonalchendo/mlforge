# ROADMAP

## Overview

mlforge is a Python feature store SDK focused on simplicity and developer experience. This roadmap tracks the journey from initial implementation to production-ready v1.0.0.

---

## Version Summary

| Version | Focus | Status |
|---------|-------|--------|
| v0.1.0 | Core SDK - @feature, Definitions, LocalStore, retrieval | ✅ Complete |
| v0.2.0 | Tags, S3Store, Rolling metrics, metadata, validators | ✅ Complete |
| v0.3.0 | Validation CLI, manifest command | ✅ Complete |
| v0.4.0 | Rolling metrics, interval support, build enhancements | ✅ Complete |
| v0.5.0 | Feature versioning, DuckDB engine, Redis online store | ✅ Complete |
| v0.6.0 | Developer ergonomics, Source/Entity/Timestamp, GCS, CLI init | Planned |
| v0.7.0 | Serving & Integration - REST API, MLflow, FeatureSpec | Planned |
| v0.8.0 | Enterprise - Databricks, PySpark, Iceberg | Planned |
| v0.9.0 | Quality & Monitoring - Metrics, drift, Prometheus, embeddings | Planned |
| v1.0.0 | Production ready | Planned |

---

## Implemented Features (Current State)

### Core SDK
- **@feature decorator** - Define features with keys, source, tags, timestamp, interval, metrics, validators
- **Definitions class** - Register features from modules, build, validate, list features/tags
- **LocalStore** - Parquet persistence with metadata support
- **S3Store** - S3 backend with s3fs, full metadata support
- **entity_key / surrogate_key** - Hash-based entity key generation
- **get_training_data** - Point-in-time correct retrieval with asof joins

### Compute
- **PolarsEngine** - Load sources (Parquet/CSV), execute features, compute metrics
- **PolarsCompiler** - Rolling aggregations via group_by_dynamic
- **Rolling metrics** - Windows, aggregations (count, sum, mean, min, max, std, median)

### Validation
- **9 validators** - not_null, unique, greater_than, less_than, greater_than_or_equal, less_than_or_equal, in_range, matches_regex, is_in
- **Per-column validators** - Defined in @feature decorator

### Metadata
- **FeatureMetadata** - Captured on build (schema, row count, timestamps, columns)
- **.meta.json files** - Per-feature metadata storage
- **Manifest** - Consolidated view of all features

### CLI
- `mlforge build` - Materialize features (--features, --tags, --force, --no-preview)
- `mlforge validate` - Run validators without building
- `mlforge list` - List features with optional tag filtering
- `mlforge inspect <feature>` - Show feature metadata
- `mlforge manifest` - Display/regenerate manifest.json

---

## Planned Features

### v0.5.0 - Compute Backends, Versioning & Online Store

**Target:** Q1 2025

| Feature | Description |
|---------|-------------|
| Feature Versioning | Semantic versioning with auto-detection (MAJOR/MINOR/PATCH bumps) |
| DuckDB Engine | Alternative compute backend for local development and large datasets |
| Redis Online Store | Real-time feature serving for online/offline alignment |
| Package Restructure | engines/, compilers/ as packages for extensibility |

See [v0.5.0.md](./v0.5.0.md) for detailed design.

### v0.6.0 - Developer Ergonomics & Source Abstraction

**Target:** Q2 2025

| Feature | Description |
|---------|-------------|
| Source Abstraction | `Source` class with format auto-detection (Parquet, CSV, Delta) |
| Entity Definition | `Entity` class with automatic surrogate key generation |
| Timestamp Handling | Auto-detect datetime formats, `Timestamp` class |
| GCS Storage | Google Cloud Storage support for sources |
| CLI `init` Command | Initialize new mlforge project with boilerplate structure |
| CLI Enhancements | Subcommands for list (features, entities, sources, versions) |
| Detailed Examples | Fraud detection, recommendation system examples |

See [v0.6.0.md](./v0.6.0.md) for detailed design.

### v0.7.0 - Serving & Integration

**Target:** Q3 2025

| Feature | Description |
|---------|-------------|
| REST API | `mlforge serve` - FastAPI-based feature serving |
| DynamoDB Online Store | AWS-managed online store for production deployments |
| FeatureSpec | Column-level feature selection in `get_training_data()` |
| MLflow Integration | Log feature versions and schemas to MLflow experiments |

### v0.8.0 - Enterprise & Scale

**Target:** Q4 2025

| Feature | Description |
|---------|-------------|
| PySpark Engine | Distributed compute for production-scale datasets |
| Unity Catalog | Databricks-native offline store with Delta Lake |
| Databricks Online Tables | Databricks-native online serving |
| Apache Iceberg | Iceberg format support for sources and stores |

### v0.9.0 - Quality & Monitoring

**Target:** Q1 2026

| Feature | Description |
|---------|-------------|
| Data Quality Metrics | Null rates, cardinality, distributions |
| Drift Detection | Population Stability Index (PSI) for distribution monitoring |
| Prometheus Metrics | Export metrics for Grafana dashboards |
| Text Embeddings | Built-in support for text embedding features |
| Catalog Generation | `mlforge catalog` for human-readable feature documentation |
| Manifest Search | `defs.search_features()` for programmatic discovery in notebooks |

### v1.0.0 - Production Ready

**Target:** When feature-complete and stable

| Feature | Description |
|---------|-------------|
| Stable APIs | Frozen public APIs with backwards compatibility guarantees |
| Production Guides | Deployment, monitoring, troubleshooting documentation |

See [v1.0.0.md](./v1.0.0.md) for complete definition of done.

---

## Future Considerations (Post v1.0.0)

Features under consideration for future releases:

| Feature | Description | Potential Version |
|---------|-------------|-------------------|
| Streaming Features | Kafka, Kinesis integration for real-time pipelines | v1.1.0 |
| Feature Dependencies | Feature A depends on Feature B, DAG execution | v1.2.0 |
| Lineage Tracking | Source → Feature → Model tracking | v1.2.0 |
| Vector DB Integration | HelixDB or similar for embedding similarity search | v1.2.0 |
| Airflow/Dagster Operators | Native orchestration integration | v1.3.0 |
| Web UI | Visual feature catalog and monitoring dashboard | v1.4.0 |
| AI Feature Assistance | AI-powered feature suggestions and optimization | v1.5.0+ |
| SAAS Platform | Managed mlforge platform (like dbt Cloud) | Strategic |

### Ideas Not Planned

The following ideas were evaluated and deferred indefinitely:

- **Unified DataFrame API** - Wrapper mimicking Polars across engines (too complex, Polars is sufficient)
- **Custom Rust Engine** - Custom data transformation engine (premature, Polars/DuckDB already Rust-based)
- **CLI `apply` Command** - Infrastructure provisioning (belongs in Terraform/Pulumi)
- **AI Data Labeling** - LLM-based data labeling (outside core scope, use specialized tools)
- **Great Expectations Integration** - Built-in validators are sufficient for most cases

---

## Detailed Roadmaps

- [v0.1.0.md](./v0.1.0.md) - Core SDK (Complete)
- [v0.2.0.md](./v0.2.0.md) - Tags, S3, Metadata (Complete)
- [v0.3.0.md](./v0.3.0.md) - Original plan (superseded)
- [v0.5.0.md](./v0.5.0.md) - Versioning, DuckDB, Redis
- [v0.6.0.md](./v0.6.0.md) - PySpark, Source/Entity abstractions, GCS
- [v1.0.0.md](./v1.0.0.md) - Production ready definition of done
