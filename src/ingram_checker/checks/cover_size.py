"""Cover page size and spine checks."""

from __future__ import annotations

from pathlib import Path

from ..config import COVER_BLEED
from ..models import BookSpec, CheckResult, CheckStatus, ProductType, Severity
from ..pdf_info import get_content_bbox, get_cover_template_geometry, get_page_count
from .base import BaseCheck

# Tolerance in points for coverage checks
_COVERAGE_TOLERANCE = 2.0  # ~0.03"


class CoverPageCountCheck(BaseCheck):
    name = "cover_page_count"
    description = "Cover PDF should have 1 page (simplex) or 2 pages (duplex)"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.COVER:
            return []

        count = get_page_count(pdf_path)
        if count in (1, 2):
            label = "simplex" if count == 1 else "duplex"
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=f"Cover has {count} page(s) ({label})",
                severity=Severity.ERROR,
            )]

        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"Cover has {count} pages — expected 1 (simplex) or 2 (duplex)",
            severity=Severity.ERROR,
        )]


class CoverSizeCheck(BaseCheck):
    name = "cover_size"
    description = "Cover artwork must fully cover the template bleed area"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.COVER:
            return []

        geom = get_cover_template_geometry(pdf_path)
        if geom is None:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.SKIP,
                message="No crop marks detected — cannot determine template geometry",
                severity=Severity.INFO,
            )]

        # Calculate bleed rectangle (trim expanded by COVER_BLEED)
        bleed_pts = COVER_BLEED * 72
        bx0 = geom.trim_rect[0] - bleed_pts
        by0 = geom.trim_rect[1] - bleed_pts
        bx1 = geom.trim_rect[2] + bleed_pts
        by1 = geom.trim_rect[3] + bleed_pts

        spine_in = geom.spine_width_in
        spine_info = f", spine {spine_in:.3f}\"" if spine_in is not None else ""

        details = [
            f"  Trim: {geom.trim_width_in:.3f}x{geom.trim_height_in:.3f}\"{spine_info}",
            f"  Bleed rect: ({bx0/72:.3f}, {by0/72:.3f}) to ({bx1/72:.3f}, {by1/72:.3f})",
        ]

        # Get bounding box of artwork on the page
        bbox = get_content_bbox(pdf_path)
        if bbox is None:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.FAIL,
                message="No visible content found on cover page",
                severity=Severity.ERROR,
                details=details,
            )]

        details.append(
            f"  Content bbox: ({bbox[0]/72:.3f}, {bbox[1]/72:.3f}) "
            f"to ({bbox[2]/72:.3f}, {bbox[3]/72:.3f})"
        )

        # Check that artwork covers the entire bleed rectangle
        gaps = []
        if bbox[0] > bx0 + _COVERAGE_TOLERANCE:
            gap = (bbox[0] - bx0) / 72
            gaps.append(f"left edge short by {gap:.3f}\"")
        if bbox[1] > by0 + _COVERAGE_TOLERANCE:
            gap = (bbox[1] - by0) / 72
            gaps.append(f"top edge short by {gap:.3f}\"")
        if bbox[2] < bx1 - _COVERAGE_TOLERANCE:
            gap = (bx1 - bbox[2]) / 72
            gaps.append(f"right edge short by {gap:.3f}\"")
        if bbox[3] < by1 - _COVERAGE_TOLERANCE:
            gap = (by1 - bbox[3]) / 72
            gaps.append(f"bottom edge short by {gap:.3f}\"")

        if gaps:
            return [CheckResult(
                check_name=self.name,
                status=CheckStatus.FAIL,
                message=f"Artwork doesn't cover bleed area: {', '.join(gaps)}",
                severity=Severity.ERROR,
                details=details,
            )]

        msg = f"Artwork covers bleed area ({geom.trim_width_in:.3f}x{geom.trim_height_in:.3f}\"{spine_info})"
        return [CheckResult(
            check_name=self.name,
            status=CheckStatus.PASS,
            message=msg,
            severity=Severity.ERROR,
            details=details,
        )]


# TODO: CoverBleedCheck — verify bleed artwork extends uniformly (not just bbox)
#       Would require rendering and pixel-level analysis.

# TODO: CoverTypeSafetyCheck — verify text/logos are ≥0.25" inside trim edges
#       (requires mapping trim/fold lines within the page)

# TODO: DuplexCoverCheck — for 2-page covers, check inside cover dimensions

# TODO: Support non-template covers (content-area sized PDFs without crop marks)
