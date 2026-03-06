"""Data models for the Ingram PDF compliance checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class ColorType(Enum):
    BW = "bw"
    COLOR = "color"


class BindingType(Enum):
    PERFECTBOUND = "perfectbound"
    CASEWRAP = "casewrap"
    COIL = "coil"
    SADDLE = "saddle"


class ProductType(Enum):
    INTERIOR = "interior"
    COVER = "cover"


@dataclass
class TrimSize:
    """A standard trim size in inches."""
    width: float
    height: float
    name: str = ""

    def __str__(self) -> str:
        return self.name or f"{self.width}x{self.height}"


@dataclass
class CheckResult:
    """Result of a single compliance check."""
    check_name: str
    status: CheckStatus
    message: str
    severity: Severity = Severity.ERROR
    details: list[str] = field(default_factory=list)
    fixable: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.SKIP)


@dataclass
class BookSpec:
    """Specification for the book being checked."""
    product_type: ProductType
    trim_size: TrimSize
    color_type: ColorType = ColorType.BW
    bleed: bool = False
    binding: BindingType = BindingType.PERFECTBOUND
    page_count: int | None = None


@dataclass
class FixResult:
    """Result of an auto-fix operation."""
    fixer_name: str
    success: bool
    message: str
    changes: list[str] = field(default_factory=list)
