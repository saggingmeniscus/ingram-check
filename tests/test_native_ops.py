"""Tests for native PDF operations (no Ghostscript)."""

from pathlib import Path

import pikepdf

from ingram_checker.native_ops import (
    convert_to_cmyk,
    convert_to_grayscale,
    measure_ink_coverage,
    measure_max_pixel_ink_density,
)
from ingram_checker.pdf_info import get_color_spaces


def test_ink_coverage_blank_pages(tmp_path: Path):
    """Blank white pages should have near-zero ink coverage."""
    pdf_path = tmp_path / "blank.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    pdf.save(pdf_path)

    coverages = measure_ink_coverage(pdf_path)
    assert len(coverages) == 2
    for cov in coverages:
        assert cov.total < 1.0


def test_max_pixel_ink_density_blank(tmp_path: Path):
    """Blank pages should have near-zero max pixel density."""
    pdf_path = tmp_path / "blank.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    pdf.save(pdf_path)

    densities = measure_max_pixel_ink_density(pdf_path, pages=[1])
    assert 1 in densities
    assert densities[1] < 1.0


def _make_pdf_with_rgb_image(tmp_path: Path, filename: str = "rgb.pdf") -> Path:
    """Helper: create a PDF with a single RGB JPEG image."""
    import io

    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    pdf_path = tmp_path / filename
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    page = pdf.pages[0]

    raw_img = pikepdf.Stream(pdf, img_bytes.read())
    raw_img["/Type"] = pikepdf.Name.XObject
    raw_img["/Subtype"] = pikepdf.Name.Image
    raw_img["/Width"] = 100
    raw_img["/Height"] = 100
    raw_img["/ColorSpace"] = pikepdf.Name.DeviceRGB
    raw_img["/BitsPerComponent"] = 8
    raw_img["/Filter"] = pikepdf.Name.DCTDecode

    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({"/Im0": raw_img}))
    content = b"q 72 0 0 72 0 0 cm /Im0 Do Q"
    page.Contents = pikepdf.Stream(pdf, content)
    pdf.save(pdf_path)
    return pdf_path


def test_convert_rgb_image_to_grayscale(tmp_path: Path):
    """An RGB image should be converted to grayscale."""
    pdf_path = _make_pdf_with_rgb_image(tmp_path)
    output_path = tmp_path / "gray.pdf"
    convert_to_grayscale(pdf_path, output_path)

    color_spaces = get_color_spaces(output_path)
    image_cs = [cs for cs in color_spaces if cs.context == "image"]
    assert all(cs.cs_type == "DeviceGray" for cs in image_cs)


def test_convert_rgb_image_to_cmyk(tmp_path: Path):
    """An RGB image should be converted to CMYK."""
    pdf_path = _make_pdf_with_rgb_image(tmp_path)
    output_path = tmp_path / "cmyk.pdf"
    convert_to_cmyk(pdf_path, output_path)

    color_spaces = get_color_spaces(output_path)
    image_cs = [cs for cs in color_spaces if cs.context == "image"]
    assert all(cs.cs_type == "DeviceCMYK" for cs in image_cs)
