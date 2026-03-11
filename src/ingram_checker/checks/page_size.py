"""Page size, bleed, and page count checks."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..config import (
    INTERIOR_BLEED_TOP_BOTTOM,
    INTERIOR_BLEED_TRIM_EDGE,
    TOLERANCE,
    expected_interior_page_size,
)
from ..models import (
    BookSpec,
    CheckResult,
    CheckStatus,
    ProductType,
    Severity,
)
from ..page_ranges import format_page_ranges
from ..pdf_info import get_page_boxes, get_page_count
from .base import BaseCheck


class PageCountCheck(BaseCheck):
    name = "page_count"
    description = "Interior page count must be divisible by 2"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.INTERIOR:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.SKIP,
                    message="Not an interior file",
                    severity=Severity.INFO,
                )
            ]

        count = get_page_count(pdf_path)
        if count % 2 == 0:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.PASS,
                    message=f"Page count ({count}) is even",
                    severity=Severity.ERROR,
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.FAIL,
                message=f"Page count ({count}) is odd — must be divisible by 2",
                severity=Severity.ERROR,
                fixable=True,
                data={"page_count": count},
            )
        ]


class PageSizeCheck(BaseCheck):
    name = "page_size"
    description = "Page size must match expected dimensions"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.INTERIOR:
            return []

        trim_w = spec.trim_size.width
        trim_h = spec.trim_size.height
        bleed_w, bleed_h = expected_interior_page_size(spec.trim_size)

        if spec.bleed:
            expected_w, expected_h = bleed_w, bleed_h
            size_label = f'{bleed_w:.3f}x{bleed_h:.3f}" (with bleed)'
        else:
            expected_w, expected_h = trim_w, trim_h
            size_label = f'{trim_w:.3f}x{trim_h:.3f}" (no bleed)'

        boxes = get_page_boxes(pdf_path)

        # Group wrong pages by their actual size
        size_groups: dict[str, list[int]] = defaultdict(list)
        for i, box in enumerate(boxes, 1):
            w_in = box.width_in
            h_in = box.height_in
            if abs(w_in - expected_w) > TOLERANCE or abs(h_in - expected_h) > TOLERANCE:
                actual = f'{w_in:.3f}x{h_in:.3f}"'
                size_groups[actual].append(i)

        if size_groups:
            total = sum(len(pages) for pages in size_groups.values())
            details = [
                f"  {actual} on pages {format_page_ranges(pages)}"
                for actual, pages in size_groups.items()
            ]
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"{total} page(s) have incorrect dimensions (expected {size_label})",
                    severity=Severity.ERROR,
                    details=details,
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=f"All pages match expected size ({size_label})",
                severity=Severity.ERROR,
            )
        ]


class BleedCheck(BaseCheck):
    name = "bleed"
    description = 'Interior must have 0.125" bleed on trim edges'

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.INTERIOR:
            return []

        if not spec.bleed:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.SKIP,
                    message="No bleed specified — skipping bleed check",
                    severity=Severity.INFO,
                )
            ]

        boxes = get_page_boxes(pdf_path)

        # Group by edge
        edge_violations: dict[str, list[tuple[int, float]]] = defaultdict(list)

        for i, box in enumerate(boxes, 1):
            if box.trim_box is None:
                continue

            tb = box.trim_box
            mb = box.media_box

            bottom_bleed = (tb[1] - mb[1]) / 72.0
            top_bleed = (mb[3] - tb[3]) / 72.0

            min_bleed = INTERIOR_BLEED_TRIM_EDGE - TOLERANCE
            if bottom_bleed < min_bleed:
                edge_violations["bottom"].append((i, bottom_bleed))
            if top_bleed < min_bleed:
                edge_violations["top"].append((i, top_bleed))

        if edge_violations:
            all_pages: set[int] = set()
            for entries in edge_violations.values():
                all_pages.update(p for p, _ in entries)

            details: list[str] = []
            for edge in ("top", "bottom"):
                entries = edge_violations.get(edge)
                if not entries:
                    continue
                pages = [p for p, _ in entries]
                measurements = [m for _, m in entries]
                min_m = min(measurements)
                max_m = max(measurements)
                expected = INTERIOR_BLEED_TOP_BOTTOM if edge == "top" else INTERIOR_BLEED_TRIM_EDGE
                if abs(min_m - max_m) < 0.001:
                    val_str = f'{min_m:.3f}"'
                else:
                    val_str = f'{min_m:.3f}"-{max_m:.3f}"'
                details.append(
                    f'  {edge}: {val_str} < {expected}" on pages {format_page_ranges(pages)}'
                )

            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"{len(all_pages)} page(s) have insufficient bleed",
                    severity=Severity.ERROR,
                    details=details,
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="Bleed dimensions are correct",
                severity=Severity.ERROR,
            )
        ]
