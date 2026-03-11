"""Convert PDF color space (RGB to CMYK or Grayscale) via Ghostscript."""

from __future__ import annotations

from pathlib import Path

from ..backend import convert_to_cmyk, convert_to_grayscale
from ..models import BookSpec, ColorType, FixResult
from .base import BaseFixer


class ColorConverter(BaseFixer):
    name = "color_converter"
    description = "Convert color space to CMYK or Grayscale via Ghostscript"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        try:
            if spec.color_type == ColorType.BW:
                convert_to_grayscale(pdf_path, output_path)
                return FixResult(
                    fixer_name=self.name,
                    success=True,
                    message="Converted to Grayscale",
                    changes=["Converted all color spaces to DeviceGray via Ghostscript"],
                )
            else:
                convert_to_cmyk(pdf_path, output_path)
                return FixResult(
                    fixer_name=self.name,
                    success=True,
                    message="Converted to CMYK",
                    changes=["Converted all color spaces to DeviceCMYK via Ghostscript"],
                )
        except Exception as e:
            return FixResult(
                fixer_name=self.name,
                success=False,
                message=f"Color conversion failed: {e}",
            )
