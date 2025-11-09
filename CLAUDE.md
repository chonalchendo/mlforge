# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mlforge is an ML Platform for your local machine that integrates Dagster (for orchestration), FastAPI (for APIs), and MLflow (for experiment tracking). This is an early-stage project built with Python 3.13.

## Package Management

This project uses `uv` for dependency management and builds:

```bash
# Install dependencies
uv sync

# Install with specific dependency groups
uv sync --group dev
uv sync --group check
uv sync --group commit
```

## Development Commands

### Code Quality

The project uses Ruff for linting and formatting, and `ty` for type checking:

```bash
# Lint and format with Ruff
ruff check .
ruff format .

# Type check with ty
ty check
```

### Task Automation

The project includes `rust-just` as a dev dependency for task automation. Look for a `justfile` or `Justfile` in the repository root for available commands.

### Commit Workflow

The project uses commitizen and prek for commit management:

```bash
# Create a conventional commit
cz commit

# Pre-commit checks (if configured)
prek
```

## Architecture Notes

The project follows a standard Python package structure with source code in `src/mlforge/`. The package includes a `py.typed` marker file, indicating that it supports type hints for external type checkers.

Key dependencies that shape the architecture:
- **Dagster (>=1.12.1)**: Data orchestration framework - expect to find pipeline/asset definitions
- **FastAPI (>=0.121.1)**: Web framework - expect REST API endpoints
- **MLflow (>=3.6.0)**: ML experiment tracking - expect experiment logging and model registry integration

## Python Version

This project requires Python 3.13.0 or higher. Ensure your environment is set up accordingly.
