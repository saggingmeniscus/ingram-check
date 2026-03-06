"""Downsample high-resolution images via Ghostscript."""

from __future__ import annotations

from pathlib import Path

from ..config import RESOLUTION_WARN_LOW
from ..ghostscript import downsample_images
from ..models import BookSpec, FixResult
from .base import BaseFixer


class ImageDownsampler(BaseFixer):
    name = "image_downsampler"
    description = "Downsample images above threshold to 300ppi via Ghostscript"

    def fix(self, pdf_path: Path, output_path: Path, spec: BookSpec) -> FixResult:
        try:
            downsample_images(pdf_path, output_path, target_dpi=RESOLUTION_WARN_LOW)
            return FixResult(
                fixer_name=self.name,
                success=True,
                message=f"Downsampled images to {RESOLUTION_WARN_LOW}ppi",
                changes=[f"Resampled all images above {RESOLUTION_WARN_LOW}ppi using bicubic interpolation"],
            )
        except Exception as e:
            return FixResult(
                fixer_name=self.name,
                success=False,
                message=f"Image downsampling failed: {e}",
            )
