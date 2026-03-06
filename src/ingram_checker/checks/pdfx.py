"""PDF/X compliance check (informational)."""

from __future__ import annotations

from pathlib import Path

import pikepdf

from ..models import BookSpec, CheckResult, CheckStatus, Severity
from .base import BaseCheck


class PDFXCheck(BaseCheck):
    name = "pdfx_compliance"
    description = "PDF/X-1a:2001 compliance (informational)"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        with pikepdf.open(pdf_path) as pdf:
            root = pdf.Root

            if "/OutputIntents" not in root:
                return [CheckResult(
                    check_name=self.name,
                    status=CheckStatus.WARN,
                    message="No OutputIntents found — not PDF/X compliant",
                    severity=Severity.INFO,
                )]

            intents = root["/OutputIntents"]
            for intent in intents:
                subtype = str(intent.get("/S", ""))
                output_condition = str(intent.get("/OutputConditionIdentifier", ""))
                if "GTS_PDFX" in subtype:
                    return [CheckResult(
                        check_name=self.name,
                        status=CheckStatus.PASS,
                        message=f"PDF/X compliant ({output_condition})",
                        severity=Severity.INFO,
                    )]

        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.WARN,
            message="OutputIntents present but no PDF/X conformance found",
            severity=Severity.INFO,
        )]
