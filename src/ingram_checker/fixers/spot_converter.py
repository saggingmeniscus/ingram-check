"""Convert spot colors to CMYK via Ghostscript."""

from __future__ import annotations

from pathlib import Path

from ..ghostscript import convert_to_cmyk
from ..models import BookSpec, FixResult
from .base import BaseFixer


class SpotConverter(BaseFixer):
    name = "spot_converter"
    description = "Convert spot colors (Separation/DeviceN) to CMYK"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        try:
            convert_to_cmyk(pdf_path, output_path)
            return FixResult(
                fixer_name=self.name,
                success=True,
                message="Converted spot colors to CMYK",
                changes=["Converted all Separation/DeviceN colors to DeviceCMYK via Ghostscript"],
            )
        except Exception as e:
            return FixResult(
                fixer_name=self.name,
                success=False,
                message=f"Spot color conversion failed: {e}",
            )
