"""Strip crop marks by clipping content to TrimBox."""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf

from ..models import BookSpec, FixResult
from .base import BaseFixer


class CropStripper(BaseFixer):
    name = "crop_stripper"
    description = "Strip crop/registration marks by setting CropBox to TrimBox"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        shutil.copy2(pdf_path, output_path)
        changes: list[str] = []

        with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                if "/TrimBox" in page:
                    # Set CropBox to TrimBox to clip visible content
                    page.CropBox = page.TrimBox
                    changes.append(f"Page {page_num}: set CropBox = TrimBox")

            if changes:
                pdf.save(output_path)

        return FixResult(
            fixer_name=self.name,
            success=len(changes) > 0,
            message=f"Clipped {len(changes)} page(s) to TrimBox"
            if changes
            else "No TrimBox found to clip to",
            changes=changes,
        )
