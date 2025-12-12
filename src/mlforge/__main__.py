"""
Entry point for running mlforge as a module.

Allows execution via: python -m mlforge
"""

import mlforge.cli as cli

if __name__ == "__main__":
    exit(cli.app.meta())
