"""Margin/type safety check."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

from ..config import RECOMMENDED_MARGIN
from ..models import BookSpec, CheckResult, CheckStatus, ProductType, Severity
from ..page_ranges import format_page_ranges
from ..pdf_info import get_page_boxes
from .base import BaseCheck


class MarginCheck(BaseCheck):
    name = "margins"
    description = f'Content should have ≥{RECOMMENDED_MARGIN}" margins from trim'

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        if spec.product_type != ProductType.INTERIOR:
            return []

        boxes = get_page_boxes(pdf_path)
        doc = fitz.open(str(pdf_path))

        # Collect per-edge violations: edge_name -> list of (page, measurement)
        edge_violations: dict[str, list[tuple[int, float]]] = defaultdict(list)

        try:
            for i in range(len(doc)):
                page = doc[i]
                text_rect = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                blocks = text_rect.get("blocks", [])
                if not blocks:
                    continue

                content_rect = fitz.Rect()
                for block in blocks:
                    block_rect = fitz.Rect(block["bbox"])
                    content_rect |= block_rect

                if content_rect.is_empty or content_rect.is_infinite:
                    continue

                box = boxes[i] if i < len(boxes) else None
                if box is None:
                    continue

                if box.trim_box:
                    trim_rect = fitz.Rect(box.trim_box)
                else:
                    trim_rect = fitz.Rect(box.media_box)

                margin_pts = RECOMMENDED_MARGIN * 72
                page_num = i + 1

                left = content_rect.x0 - trim_rect.x0
                if left < margin_pts:
                    edge_violations["left"].append((page_num, left / 72))

                right = trim_rect.x1 - content_rect.x1
                if right < margin_pts:
                    edge_violations["right"].append((page_num, right / 72))

                top = content_rect.y0 - trim_rect.y0
                if top < margin_pts:
                    edge_violations["top"].append((page_num, top / 72))

                bottom = trim_rect.y1 - content_rect.y1
                if bottom < margin_pts:
                    edge_violations["bottom"].append((page_num, bottom / 72))
        finally:
            doc.close()

        if not edge_violations:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.PASS,
                    message=f'All pages have ≥{RECOMMENDED_MARGIN}" margins',
                    severity=Severity.WARNING,
                )
            ]

        # Count total affected pages
        all_pages: set[int] = set()
        for entries in edge_violations.values():
            all_pages.update(p for p, _ in entries)

        details: list[str] = []
        for edge in ("top", "bottom", "left", "right"):
            entries = edge_violations.get(edge)
            if not entries:
                continue
            pages = [p for p, _ in entries]
            measurements = [m for _, m in entries]
            min_m = min(measurements)
            max_m = max(measurements)
            if abs(min_m - max_m) < 0.01:
                range_str = f'{min_m:.2f}"'
            else:
                range_str = f'{min_m:.2f}"-{max_m:.2f}"'
            details.append(f"  {edge}: {range_str} on pages {format_page_ranges(pages)}")

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.WARN,
                message=f'{len(all_pages)} page(s) have margins <{RECOMMENDED_MARGIN}"',
                severity=Severity.WARNING,
                details=details,
            )
        ]
