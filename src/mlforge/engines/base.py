"""
Base engine abstraction for feature computation.

This module defines the abstract interface that all computation engines
must implement.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import mlforge.results as results_

if TYPE_CHECKING:
    import mlforge.core as core


class Engine(ABC):
    """
    Abstract base class for feature computation engines.

    Engines are responsible for loading source data, executing feature
    transformations, and computing metrics.
    """

    @abstractmethod
    def execute(self, feature: "core.Feature") -> results_.ResultKind:
        """
        Execute a feature computation.

        Args:
            feature: Feature definition to execute

        Returns:
            Engine-specific result wrapper containing computed data
        """
        ...
