"""Base fixer abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import BookSpec, FixResult


class BaseFixer(ABC):
    """Abstract base class for PDF auto-fixers."""

    name: str = "unnamed_fixer"
    description: str = ""

    @abstractmethod
    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        """Apply the fix. Always writes to output_path, never modifies input."""
        ...
