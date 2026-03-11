"""Image resolution check."""

from __future__ import annotations

from pathlib import Path

from ..config import (
    RESOLUTION_ERROR_COVER,
    RESOLUTION_ERROR_INTERIOR,
    RESOLUTION_WARN_HIGH,
    RESOLUTION_WARN_LOW,
)
from ..models import BookSpec, CheckResult, CheckStatus, ProductType, Severity
from ..pdf_info import ImageInfo, get_images
from .base import BaseCheck


def _format_position(img: ImageInfo) -> str:
    """Format image position as a human-readable location on the page."""
    if img.position is None:
        return ""
    x0, y0, x1, y1 = img.position
    return f' at ({x0 / 72:.1f}",{y0 / 72:.1f}")-({x1 / 72:.1f}",{y1 / 72:.1f}")'


def _format_image(img: ImageInfo) -> str:
    max_dpi = max(img.effective_dpi_x, img.effective_dpi_y)
    pos = _format_position(img)
    display_w = (img.position[2] - img.position[0]) / 72 if img.position else 0
    display_h = (img.position[3] - img.position[1]) / 72 if img.position else 0
    size_str = f'{display_w:.2f}x{display_h:.2f}"' if img.position else ""
    return (
        f"  Page {img.page}: {img.width_px}x{img.height_px}px "
        f"at {max_dpi:.0f}ppi, displayed {size_str}{pos}"
    )


class ResolutionCheck(BaseCheck):
    name = "resolution"
    description = "Image resolution check (error/warn thresholds vary by product)"

    def run(self, pdf_path: Path, spec: BookSpec) -> list[CheckResult]:
        images = get_images(pdf_path)
        if not images:
            return [
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.PASS,
                    message="No images found",
                    severity=Severity.INFO,
                )
            ]

        if spec.product_type == ProductType.COVER:
            error_threshold = RESOLUTION_ERROR_COVER
        else:
            error_threshold = RESOLUTION_ERROR_INTERIOR

        error_images: list[str] = []
        warn_low_images: list[str] = []
        warn_high_images: list[str] = []

        for img in images:
            min_dpi = min(img.effective_dpi_x, img.effective_dpi_y)
            max_dpi = max(img.effective_dpi_x, img.effective_dpi_y)
            if min_dpi < error_threshold:
                error_images.append(_format_image(img))
            elif min_dpi < RESOLUTION_WARN_LOW:
                warn_low_images.append(_format_image(img))
            elif max_dpi > RESOLUTION_WARN_HIGH:
                warn_high_images.append(_format_image(img))

        results: list[CheckResult] = []

        if error_images:
            results.append(
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.FAIL,
                    message=f"{len(error_images)} image(s) below {error_threshold}ppi minimum",
                    severity=Severity.ERROR,
                    details=error_images,
                )
            )

        if warn_low_images:
            results.append(
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.WARN,
                    message=(
                        f"{len(warn_low_images)} image(s)"
                        f" below {RESOLUTION_WARN_LOW}ppi recommended"
                    ),
                    severity=Severity.WARNING,
                    details=warn_low_images,
                )
            )

        if warn_high_images:
            results.append(
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.WARN,
                    message=(
                        f"{len(warn_high_images)} image(s)"
                        f" above {RESOLUTION_WARN_HIGH}ppi (increases file size)"
                    ),
                    severity=Severity.WARNING,
                    details=warn_high_images,
                    fixable=True,
                )
            )

        if not results:
            min_overall = min(min(img.effective_dpi_x, img.effective_dpi_y) for img in images)
            max_overall = max(max(img.effective_dpi_x, img.effective_dpi_y) for img in images)
            results.append(
                CheckResult(
                    check_name=self.name,
                    status=CheckStatus.PASS,
                    message=f"All {len(images)} image(s) OK "
                    f"({min_overall:.0f}–{max_overall:.0f}ppi)",
                    severity=Severity.ERROR,
                )
            )

        return results
