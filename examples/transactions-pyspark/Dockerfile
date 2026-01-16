# PySpark example container for mlforge
#
# This Dockerfile creates an environment with Java + PySpark + mlforge
# for testing the PySpark engine without local Java installation.

FROM python:3.13-slim

# Install Java (required for PySpark) and basic utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Reduce Spark log verbosity
ENV SPARK_LOG_LEVEL=WARN

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Set working directory to project root
WORKDIR /app

# Copy entire project (respects .dockerignore)
COPY . .

# Install dependencies for the pyspark example
WORKDIR /app/examples/transactions-pyspark
RUN uv sync --frozen || uv sync

# Set entrypoint to use uv run
ENTRYPOINT ["uv", "run"]

# Default command shows help
CMD ["mlforge", "--help"]
