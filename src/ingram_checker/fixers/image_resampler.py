"""Resample images to target resolution via Ghostscript."""

from __future__ import annotations

from pathlib import Path

from ..backend import resample_images
from ..config import RESOLUTION_WARN_LOW
from ..models import BookSpec, FixResult
from .base import BaseFixer


class ImageResampler(BaseFixer):
    name = "image_resampler"
    description = "Resample images to 300ppi via Ghostscript"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        try:
            resample_images(pdf_path, output_path, target_dpi=RESOLUTION_WARN_LOW)
            return FixResult(
                fixer_name=self.name,
                success=True,
                message=f"Resampled images to {RESOLUTION_WARN_LOW}ppi",
                changes=[
                    f"Resampled all images to {RESOLUTION_WARN_LOW}ppi using bicubic interpolation"
                ],
            )
        except Exception as e:
            return FixResult(
                fixer_name=self.name,
                success=False,
                message=f"Image resampling failed: {e}",
            )
