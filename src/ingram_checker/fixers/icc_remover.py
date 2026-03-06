"""Remove ICC profiles from PDF."""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf

from ..models import BookSpec, FixResult
from .base import BaseFixer


class ICCRemover(BaseFixer):
    name = "icc_remover"
    description = "Remove ICC profiles and OutputIntents"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        shutil.copy2(pdf_path, output_path)
        changes: list[str] = []

        with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
            # Remove document-level OutputIntents
            if "/OutputIntents" in pdf.Root:
                del pdf.Root["/OutputIntents"]
                changes.append("Removed document OutputIntents")

            # Walk all pages and replace ICCBased color spaces
            for page_num, page in enumerate(pdf.pages, 1):
                page_changes = self._clean_page(page, page_num)
                changes.extend(page_changes)

            pdf.save(output_path)

        return FixResult(
            fixer_name=self.name,
            success=len(changes) > 0,
            message=f"Removed {len(changes)} ICC reference(s)" if changes else "No ICC profiles found",
            changes=changes,
        )

    def _clean_page(self, page: pikepdf.Page, page_num: int) -> list[str]:
        changes: list[str] = []
        resources = page.get("/Resources")
        if resources is None:
            return changes

        # Clean ColorSpace dictionary
        cs_dict = resources.get("/ColorSpace")
        if cs_dict is not None:
            to_remove = []
            for cs_name, cs_obj in dict(cs_dict).items():
                if isinstance(cs_obj, pikepdf.Array) and len(cs_obj) > 0:
                    if str(cs_obj[0]) == "/ICCBased":
                        to_remove.append(cs_name)
            for name in to_remove:
                del cs_dict[name]
                changes.append(f"Page {page_num}: removed ICCBased color space {name}")

        return changes
