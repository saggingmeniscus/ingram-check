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
            message=f"Removed {len(changes)} ICC reference(s)"
            if changes
            else "No ICC profiles found",
            changes=changes,
        )

    def _icc_to_device_colorspace(self, cs_obj: pikepdf.Array) -> pikepdf.Name:
        """Map an ICCBased color space to the equivalent Device color space."""
        icc_stream = cs_obj[1]
        n = int(icc_stream.get("/N", 3))
        if n == 1:
            return pikepdf.Name.DeviceGray
        if n == 4:
            return pikepdf.Name.DeviceCMYK
        return pikepdf.Name.DeviceRGB

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

        # Clean image XObjects
        xobjects = resources.get("/XObject")
        if xobjects is not None:
            for xo_name, xo_ref in dict(xobjects).items():
                try:
                    xo = xo_ref
                    if str(xo.get("/Subtype", "")) != "/Image":
                        continue
                    cs = xo.get("/ColorSpace")
                    if isinstance(cs, pikepdf.Array) and len(cs) > 0 and str(cs[0]) == "/ICCBased":
                        device_cs = self._icc_to_device_colorspace(cs)
                        xo["/ColorSpace"] = device_cs
                        clean_name = str(xo_name).lstrip("/")
                        changes.append(
                            f"Page {page_num}: replaced ICCBased on image"
                            f" {clean_name} with {device_cs}"
                        )
                except Exception:
                    continue

        return changes
