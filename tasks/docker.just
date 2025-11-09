# Start all infrastructure services (Dagster, MLflow, MinIO, PostgreSQL)
[group('docker')]
docker-up:
    cd .docker && docker compose up -d
    @echo "✓ Services started:"
    @echo "  • Dagster UI: http://localhost:3000"
    @echo "  • MLflow UI: http://localhost:5001"
    @echo "  • MinIO Console: http://localhost:9001"

# Stop all infrastructure services
[group('docker')]
docker-down:
    cd .docker && docker compose down

# View service logs (use service=name for specific service)
[group('docker')]
docker-logs service="":
    #!/usr/bin/env bash
    cd .docker
    if [ -z "{{service}}" ]; then
        docker compose logs -f
    else
        docker compose logs -f {{service}}
    fi

# Show service status
[group('docker')]
docker-status:
    cd .docker && docker compose ps

# Rebuild and restart services
[group('docker')]
docker-rebuild:
    cd .docker && docker compose up -d --build
