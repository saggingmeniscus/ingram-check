"""Base check abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import BookSpec, CheckResult


class BaseCheck(ABC):
    """Abstract base class for all PDF compliance checks."""

    name: str = "unnamed_check"
    description: str = ""
    enabled_by_default: bool = True

    @abstractmethod
    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        """Run the check and return results."""
        ...
