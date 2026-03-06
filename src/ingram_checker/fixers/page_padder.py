"""Add blank page to make page count even."""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf

from ..models import BookSpec, FixResult
from .base import BaseFixer


class PagePadder(BaseFixer):
    name = "page_padder"
    description = "Append blank page to make page count even"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        shutil.copy2(pdf_path, output_path)

        with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
            if len(pdf.pages) % 2 == 0:
                return FixResult(
                    fixer_name=self.name,
                    success=False,
                    message="Page count already even, no change needed",
                )

            last_page = pdf.pages[-1]
            media_box = last_page.MediaBox
            width = float(media_box[2]) - float(media_box[0])
            height = float(media_box[3]) - float(media_box[1])

            pdf.add_blank_page(page_size=(width, height))

            # Copy TrimBox/BleedBox from last content page to new blank page
            new_page = pdf.pages[-1]
            if "/TrimBox" in last_page:
                new_page.TrimBox = last_page.TrimBox
            if "/BleedBox" in last_page:
                new_page.BleedBox = last_page.BleedBox

            new_count = len(pdf.pages)
            pdf.save(output_path)

        return FixResult(
            fixer_name=self.name,
            success=True,
            message=f"Added blank page (now {new_count} pages)",
            changes=["Appended blank page to make page count even"],
        )
