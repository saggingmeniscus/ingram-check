"""Tests for native PDF operations (no Ghostscript)."""

from pathlib import Path

import pikepdf

from ingram_checker.native_ops import (
    convert_to_cmyk,
    convert_to_grayscale,
    measure_ink_coverage,
    measure_max_pixel_ink_density,
    resample_images,
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


def _make_pdf_with_masked_image(
    tmp_path: Path,
    filename: str = "masked.pdf",
    img_size: tuple[int, int] = (200, 200),
) -> Path:
    """Helper: create a PDF with an RGB image plus a grayscale /SMask (transparency)."""
    import io

    from PIL import Image

    w, h = img_size
    img = Image.new("RGB", (w, h), color=(0, 0, 0))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    mask = Image.new("L", (w, h), color=128)
    mask_bytes = io.BytesIO()
    mask.save(mask_bytes, format="JPEG")
    mask_bytes.seek(0)

    pdf_path = tmp_path / filename
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    page = pdf.pages[0]

    smask_obj = pikepdf.Stream(pdf, mask_bytes.read())
    smask_obj["/Type"] = pikepdf.Name.XObject
    smask_obj["/Subtype"] = pikepdf.Name.Image
    smask_obj["/Width"] = w
    smask_obj["/Height"] = h
    smask_obj["/ColorSpace"] = pikepdf.Name.DeviceGray
    smask_obj["/BitsPerComponent"] = 8
    smask_obj["/Filter"] = pikepdf.Name.DCTDecode

    raw_img = pikepdf.Stream(pdf, img_bytes.read())
    raw_img["/Type"] = pikepdf.Name.XObject
    raw_img["/Subtype"] = pikepdf.Name.Image
    raw_img["/Width"] = w
    raw_img["/Height"] = h
    raw_img["/ColorSpace"] = pikepdf.Name.DeviceRGB
    raw_img["/BitsPerComponent"] = 8
    raw_img["/Filter"] = pikepdf.Name.DCTDecode
    raw_img["/SMask"] = smask_obj

    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({"/Im0": raw_img}))
    page.Contents = pikepdf.Stream(pdf, b"q 72 0 0 72 0 0 cm /Im0 Do Q")
    pdf.save(pdf_path)
    return pdf_path


def _first_image_has_smask(pdf_path: Path) -> bool:
    with pikepdf.open(pdf_path) as pdf:
        xobjects = pdf.pages[0]["/Resources"]["/XObject"]
        for _, xo in dict(xobjects).items():
            if str(xo.get("/Subtype", "")) == "/Image":
                return "/SMask" in xo
    raise AssertionError("no image xobject found")


def test_convert_to_grayscale_preserves_smask(tmp_path: Path):
    """Grayscale conversion must preserve /SMask so transparent logos stay transparent."""
    pdf_path = _make_pdf_with_masked_image(tmp_path)
    output_path = tmp_path / "gray.pdf"
    convert_to_grayscale(pdf_path, output_path)

    assert _first_image_has_smask(output_path), "SMask was dropped during grayscale conversion"


def test_convert_to_cmyk_preserves_smask(tmp_path: Path):
    """CMYK conversion must preserve /SMask."""
    pdf_path = _make_pdf_with_masked_image(tmp_path)
    output_path = tmp_path / "cmyk.pdf"
    convert_to_cmyk(pdf_path, output_path)

    assert _first_image_has_smask(output_path), "SMask was dropped during CMYK conversion"


def test_resample_images_preserves_smask(tmp_path: Path):
    """Resampling must preserve /SMask so transparent images stay transparent."""
    # Size chosen so that displayed at 72pt the effective DPI is far from 300,
    # guaranteeing the resampler rewrites this image.
    pdf_path = _make_pdf_with_masked_image(tmp_path, img_size=(1200, 1200))
    output_path = tmp_path / "resampled.pdf"
    resample_images(pdf_path, output_path, target_dpi=300)

    assert _first_image_has_smask(output_path), "SMask was dropped during resampling"
