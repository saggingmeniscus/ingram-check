"""Cover barcode analysis."""

from __future__ import annotations

from pathlib import Path

from ..models import BookSpec, CheckResult, CheckStatus, ProductType, Severity
from .base import BaseCheck


class BarcodeCheck(BaseCheck):
    name = "barcode"
    description = "Cover barcode should be 100% black vector"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.COVER:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.SKIP,
                message="Barcode check only applies to covers",
                severity=Severity.INFO,
            )]

        # Barcode analysis requires visual inspection and is complex to automate
        # For now, return informational result
        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.WARN,
            message="Barcode check requires manual verification — ensure barcode is 100% black vector",
            severity=Severity.WARNING,
        )]
