#!/bin/bash
#
# Convenience script for running the PySpark example in Docker
#
# Usage:
#   ./run.sh                    # Show help
#   ./run.sh list features      # List all features
#   ./run.sh build              # Build all features
#   ./run.sh build --features merchant_spend_pyspark
#   ./run.sh inspect feature merchant_spend_pyspark
#   ./run.sh shell              # Interactive bash shell
#
# First run will build the Docker image (takes ~2 minutes)

set -e

cd "$(dirname "$0")"

# Build image if needed
if ! docker images | grep -q "mlforge-pyspark"; then
    echo "Building Docker image (first time only)..."
    docker compose build
fi

# Handle special 'shell' command
if [ "$1" = "shell" ]; then
    docker compose run --rm mlforge-pyspark bash
    exit 0
fi

# Pass all arguments to mlforge CLI
if [ $# -eq 0 ]; then
    docker compose run --rm mlforge-pyspark mlforge --help
else
    docker compose run --rm mlforge-pyspark mlforge "$@"
fi
