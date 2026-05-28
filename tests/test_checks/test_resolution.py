"""Tests for resolution check formatting."""

from ingram_checker.checks.resolution import _format_image
from ingram_checker.pdf_info import ImageInfo


def _img(width_px: int, height_px: int, display_w_in: float, display_h_in: float) -> ImageInfo:
    return ImageInfo(
        page=1,
        width_px=width_px,
        height_px=height_px,
        effective_dpi_x=width_px / display_w_in,
        effective_dpi_y=height_px / display_h_in,
        color_space="DeviceRGB",
        position=(0.0, 0.0, display_w_in * 72.0, display_h_in * 72.0),
    )


def test_format_image_uniform_dpi_shows_single_value():
    # 1031x1496 px displayed at 5.96"x8.48" → dpi_x ≈ 173, dpi_y ≈ 176 (essentially uniform)
    img = _img(1031, 1496, 5.96, 8.48)
    line = _format_image(img)
    assert "176ppi" in line or "173ppi" in line
    # Must not render as "XxYppi" when essentially uniform
    assert "×" not in line


def test_format_image_non_uniform_dpi_shows_both_axes():
    # 720 px / 0.36" = 2000 dpi_x ; 130 px / 2.0" = 65 dpi_y
    # The check fails on the low (vertical) axis; the format string must surface that.
    img = _img(720, 130, 0.36, 2.00)
    line = _format_image(img)
    assert "2000" in line
    assert "65" in line
    assert "×" in line  # axis separator


def test_format_image_extremely_stretched_shows_low_axis():
    # 1000 px / 0.5" = 2000 dpi_x ; 100 px / 2.0" = 50 dpi_y
    img = _img(1000, 100, 0.5, 2.0)
    line = _format_image(img)
    assert "50" in line
    assert "2000" in line
