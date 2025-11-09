# MLforge Infrastructure

Local ML platform infrastructure using Docker Compose.

## What

A containerized ML platform stack featuring:
- **Dagster** - Pipeline orchestration
- **MLflow** - Experiment tracking & model registry
- **MinIO** - S3-compatible artifact storage
- **PostgreSQL** - Shared metadata store
- **DuckDB** - Embedded analytical database (in your code)

## Why

Provides a complete, reproducible local ML development environment with:
- Unified experiment tracking across projects
- Centralized artifact storage
- Automated pipeline orchestration
- Production-like infrastructure locally

## How

### Architecture

```
┌─────────────────────────────────────────────┐
│           MLforge Network                   │
│                                             │
│  Dagster ──▶ MLflow ──▶ MinIO              │
│   :3000      :5001      :9000/:9001         │
│     │          │                             │
│     └──────────┴────────▶ PostgreSQL        │
│                             :5432            │
└─────────────────────────────────────────────┘
```

### Quick Start

```bash
# Start all services
just docker-up

# View status
just docker-status

# View logs
just docker-logs

# Stop services
just docker-down
```

### Service Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Dagster UI | http://localhost:3000 | None |
| MLflow UI | http://localhost:5001 | None |
| MinIO Console | http://localhost:9001 | `minio_admin` / `minio_password` |

### Integration Example

```python
import mlflow
import duckdb

# Track experiments
mlflow.set_tracking_uri("http://localhost:5001")

with mlflow.start_run():
    mlflow.log_metric("accuracy", 0.95)
    mlflow.log_artifact("model.pkl")

# Query with DuckDB
conn = duckdb.connect(':memory:')
df = conn.execute("SELECT * FROM 's3://bucket/data.parquet'").df()
```

### Files

- `docker-compose.yaml` - Service definitions
- `Dockerfile.dagster` - Dagster services image (built with `uv`)
- `Dockerfile.mlflow` - MLflow image with PostgreSQL support
- `dagster.yaml` - Dagster configuration
- `workspace.yaml` - Dagster workspace definition
- `.env.example` - Environment variables template

### Data Persistence

Volumes:
- `postgres-data` - Database files
- `minio-data` - Object storage
- `dagster-tmp` - Dagster logs

### Troubleshooting

**Services not starting?**
```bash
just logs <service-name>
```

**Port conflicts?**
Edit port mappings in `docker-compose.yaml`

**Clean restart?**
```bash
just down
docker volume rm docker_postgres-data docker_minio-data docker_dagster-tmp
just up
```

### Production Notes

⚠️ **This is a development setup.** For production:
- Change all default passwords
- Enable TLS/SSL
- Use managed PostgreSQL
- Configure proper access controls
- Set up monitoring & backups
