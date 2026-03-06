"""Ink density check via Ghostscript."""

from __future__ import annotations

from pathlib import Path

from ..config import INK_DENSITY_ERROR, INK_DENSITY_WARN
from ..ghostscript import measure_ink_coverage, measure_max_pixel_ink_density
from ..models import BookSpec, CheckResult, CheckStatus, Severity
from .base import BaseCheck


class InkDensityCheck(BaseCheck):
    name = "ink_density"
    description = "Maximum ink density must be ≤240% (warn) / ≤300% (error)"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        try:
            coverages = measure_ink_coverage(pdf_path)
        except Exception as e:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.SKIP,
                message=f"Could not measure ink coverage: {e}",
                severity=Severity.INFO,
            )]

        if not coverages:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.SKIP,
                message="No ink coverage data returned",
                severity=Severity.INFO,
            )]

        # Find pages with high average ink
        high_pages = [c for c in coverages if c.total > INK_DENSITY_WARN]

        if not high_pages:
            max_cov = max(c.total for c in coverages)
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=f"Max average ink density: {max_cov:.0f}%",
                severity=Severity.ERROR,
            )]

        # For pages with high average, do pixel-level check
        high_page_nums = [c.page for c in high_pages]
        try:
            pixel_densities = measure_max_pixel_ink_density(
                pdf_path, pages=high_page_nums
            )
        except Exception:
            pixel_densities = {}

        results: list[CheckResult] = []
        error_pages: list[str] = []
        warn_pages: list[str] = []

        for cov in high_pages:
            pixel_max = pixel_densities.get(cov.page)
            if pixel_max is not None and pixel_max > INK_DENSITY_ERROR:
                error_pages.append(
                    f"  Page {cov.page}: avg {cov.total:.0f}%, "
                    f"max pixel {pixel_max:.0f}%"
                )
            elif pixel_max is not None and pixel_max > INK_DENSITY_WARN:
                warn_pages.append(
                    f"  Page {cov.page}: avg {cov.total:.0f}%, "
                    f"max pixel {pixel_max:.0f}%"
                )
            else:
                warn_pages.append(
                    f"  Page {cov.page}: avg {cov.total:.0f}%"
                )

        if error_pages:
            results.append(CheckResult(
                check_name=self.name,
                status=CheckStatus.FAIL,
                message=f"{len(error_pages)} page(s) exceed {INK_DENSITY_ERROR}% ink density",
                severity=Severity.ERROR,
                details=error_pages,
            ))

        if warn_pages:
            results.append(CheckResult(
                check_name=self.name,
                status=CheckStatus.WARN,
                message=f"{len(warn_pages)} page(s) have ink density above {INK_DENSITY_WARN}%",
                severity=Severity.WARNING,
                details=warn_pages,
            ))

        if not results:
            max_cov = max(c.total for c in coverages)
            results.append(CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=f"Max average ink density: {max_cov:.0f}%",
                severity=Severity.ERROR,
            ))

        return results
