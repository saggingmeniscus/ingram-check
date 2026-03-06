"""Font embedding check."""

from __future__ import annotations

from pathlib import Path

from ..models import BookSpec, CheckResult, CheckStatus, Severity
from ..pdf_info import get_fonts
from .base import BaseCheck


class FontEmbeddingCheck(BaseCheck):
    name = "font_embedding"
    description = "All fonts must be embedded"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        fonts = get_fonts(pdf_path)
        unembedded = [f for f in fonts if not f.embedded]

        if not unembedded:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=f"All {len(fonts)} fonts are embedded",
                severity=Severity.ERROR,
            )]

        details = [
            f"  {f.name} (page {f.page})" for f in unembedded
        ]
        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"{len(unembedded)} font(s) not embedded",
            severity=Severity.ERROR,
            details=details,
        )]
