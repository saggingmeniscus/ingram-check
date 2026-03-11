"""Content text scanning checks (manufacturing statements, paper claims, brackets)."""

from __future__ import annotations

import re
from pathlib import Path

from ..config import (
    BRACKET_PATTERN,
    PROHIBITED_MANUFACTURING_PATTERNS,
    PROHIBITED_PAPER_CERT_PATTERNS,
)
from ..models import BookSpec, CheckResult, CheckStatus, Severity
from ..pdf_info import get_text
from .base import BaseCheck


class ManufacturingStatementCheck(BaseCheck):
    name = "manufacturing_statement"
    description = 'No "printed in" or manufacturing location statements'

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        # Scan pages 2-6 (typical copyright page location) plus last few pages
        pages_to_scan = list(range(2, 7))
        text = get_text(pdf_path, pages_to_scan)

        found: list[str] = []
        for page_num, page_text in text.items():
            for pattern in PROHIBITED_MANUFACTURING_PATTERNS:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    found.append(f'  Page {page_num}: "{match}"')

        if found:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"Found {len(found)} manufacturing statement(s)",
                    severity=Severity.ERROR,
                    details=found,
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No manufacturing statements found",
                severity=Severity.ERROR,
            )
        ]


class PaperCertificationCheck(BaseCheck):
    name = "paper_certification"
    description = "No FSC/SFI/PEFC paper certification claims"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        pages_to_scan = list(range(2, 7))
        text = get_text(pdf_path, pages_to_scan)

        found: list[str] = []
        for page_num, page_text in text.items():
            for pattern in PROHIBITED_PAPER_CERT_PATTERNS:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    found.append(f'  Page {page_num}: "{match}"')

        if found:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.WARN,
                    message=f"Found {len(found)} paper certification reference(s)",
                    severity=Severity.WARNING,
                    details=found,
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No paper certification claims found",
                severity=Severity.WARNING,
            )
        ]


class BracketedTextCheck(BaseCheck):
    name = "bracketed_text"
    description = "No bracketed special instructions"
    enabled_by_default = False

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        text = get_text(pdf_path)

        found: list[str] = []
        for page_num, page_text in text.items():
            matches = re.findall(BRACKET_PATTERN, page_text)
            for match in matches:
                # Filter out very short brackets that might be citations [1]
                stripped = match[1:-1].strip()
                if len(stripped) > 3 and not stripped.isdigit():
                    found.append(f"  Page {page_num}: {match[:60]}")

        if found:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.WARN,
                    message=f"Found {len(found)} bracketed text item(s)",
                    severity=Severity.WARNING,
                    details=found[:20],
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No bracketed instructions found",
                severity=Severity.WARNING,
            )
        ]
