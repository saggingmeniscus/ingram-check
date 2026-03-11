"""Crop/registration mark detection."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from ..models import BookSpec, CheckResult, CheckStatus, Severity
from ..page_ranges import format_page_ranges
from ..pdf_info import get_page_boxes
from .base import BaseCheck


class CropMarksCheck(BaseCheck):
    name = "crop_marks"
    description = "No crop or registration marks should be present"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        boxes = get_page_boxes(pdf_path)

        affected_pages: list[int] = []
        doc = fitz.open(str(pdf_path))
        try:
            for i, box in enumerate(boxes):
                if box.trim_box is None:
                    continue

                page = doc[i]
                trim = fitz.Rect(box.trim_box)
                media = fitz.Rect(box.media_box)

                if abs(media.width - trim.width) < 1 and abs(media.height - trim.height) < 1:
                    continue

                drawings = page.get_drawings()
                for d in drawings:
                    rect = fitz.Rect(d["rect"])
                    if not trim.contains(rect) and not rect.is_empty:
                        if rect.width < 36 or rect.height < 36:
                            affected_pages.append(i + 1)
                            break
        finally:
            doc.close()

        if affected_pages:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"{len(affected_pages)} page(s) have crop/registration marks",
                    severity=Severity.ERROR,
                    details=[f"  Pages {format_page_ranges(affected_pages)}"],
                    fixable=True,
                )
            ]

        return [
            CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No crop/registration marks detected",
                severity=Severity.ERROR,
            )
        ]
