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


def _make_pdf_with_cmyk_image(
    tmp_path: Path,
    filename: str = "cmyk.pdf",
    img_size: tuple[int, int] = (200, 200),
    display_pts: tuple[float, float] = (72.0, 72.0),
) -> Path:
    """Helper: create a PDF with a single CMYK JPEG image."""
    import io

    from PIL import Image

    w, h = img_size
    img = Image.new("CMYK", (w, h), color=(100, 50, 25, 10))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=95)
    img_bytes.seek(0)

    pdf_path = tmp_path / filename
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    page = pdf.pages[0]

    raw_img = pikepdf.Stream(pdf, img_bytes.read())
    raw_img["/Type"] = pikepdf.Name.XObject
    raw_img["/Subtype"] = pikepdf.Name.Image
    raw_img["/Width"] = w
    raw_img["/Height"] = h
    raw_img["/ColorSpace"] = pikepdf.Name.DeviceCMYK
    raw_img["/BitsPerComponent"] = 8
    raw_img["/Filter"] = pikepdf.Name.DCTDecode
    # Source JPEG was written by Pillow with Adobe inverted convention; mark accordingly
    # so the synthetic input PDF renders correctly and pikepdf+PIL decode round-trip cleanly.
    raw_img["/Decode"] = pikepdf.Array([1, 0, 1, 0, 1, 0, 1, 0])

    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({"/Im0": raw_img}))
    dw, dh = display_pts
    page.Contents = pikepdf.Stream(pdf, f"q {dw} 0 0 {dh} 0 0 cm /Im0 Do Q".encode())
    pdf.save(pdf_path)
    return pdf_path


def _first_image_dims(pdf_path: Path) -> tuple[int, int]:
    with pikepdf.open(pdf_path) as pdf:
        xobjects = pdf.pages[0]["/Resources"]["/XObject"]
        for _, xo in dict(xobjects).items():
            if str(xo.get("/Subtype", "")) == "/Image":
                return int(xo["/Width"]), int(xo["/Height"])
    raise AssertionError("no image xobject found")


def _first_image_jpeg_bytes(pdf_path: Path) -> bytes:
    with pikepdf.open(pdf_path) as pdf:
        xobjects = pdf.pages[0]["/Resources"]["/XObject"]
        for _, xo in dict(xobjects).items():
            if str(xo.get("/Subtype", "")) == "/Image":
                return bytes(xo.get_raw_stream_buffer())
    raise AssertionError("no image xobject found")


def test_resample_cmyk_strips_app14_marker(tmp_path: Path):
    """CMYK JPEG output must omit the Adobe APP14 marker. Pillow writes raw CMYK
    bytes but adds an APP14 marker that claims they're Adobe-inverted, causing
    viewers that honor APP14 (e.g. PDFExpert) to invert the (already correct)
    bytes — producing inverted colors. Stripping APP14 makes the output render
    consistently across viewers."""
    pdf_path = _make_pdf_with_cmyk_image(tmp_path, img_size=(100, 100), display_pts=(72, 72))
    output_path = tmp_path / "resampled.pdf"
    resample_images(pdf_path, output_path, target_dpi=300)

    assert b"\xff\xee" not in _first_image_jpeg_bytes(output_path)


def test_convert_to_cmyk_strips_app14_marker(tmp_path: Path):
    """convert_to_cmyk must also strip APP14."""
    pdf_path = _make_pdf_with_rgb_image(tmp_path)
    output_path = tmp_path / "cmyk.pdf"
    convert_to_cmyk(pdf_path, output_path)

    assert b"\xff\xee" not in _first_image_jpeg_bytes(output_path)


def test_resample_uses_per_axis_scale(tmp_path: Path):
    """Non-uniformly scaled images must be resampled per-axis so the axis that
    is already over-resolution does not get bloated further. 100x400 px displayed
    at 1"x2" = 100 dpi_x, 200 dpi_y → at target 300 the output should be 300x600,
    not 300x1200 (which is what scale=300/min_dpi applied to both axes produces)."""
    pdf_path = _make_pdf_with_cmyk_image(tmp_path, img_size=(100, 400), display_pts=(72, 144))
    output_path = tmp_path / "resampled.pdf"
    resample_images(pdf_path, output_path, target_dpi=300)

    assert _first_image_dims(output_path) == (300, 600)


def _make_pdf_with_indexed_cmyk_image(
    tmp_path: Path,
    palette_cmyk: tuple[int, int, int, int] = (200, 100, 50, 30),
    img_size: tuple[int, int] = (100, 100),
    display_pts: tuple[float, float] = (72.0, 72.0),
    filename: str = "indexed_cmyk.pdf",
) -> Path:
    """Helper: create a PDF whose only image is a solid color Indexed CMYK palette image.

    The palette entry is in PDF CMYK convention (0=no ink, 255=full ink).
    """
    w, h = img_size
    pdf_path = tmp_path / filename
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6 * 72, 9 * 72))
    page = pdf.pages[0]

    # Palette stream: one entry of 4 CMYK bytes (rest of the 252+1 slots stay
    # implicit / unused since every pixel references index 0).
    palette_bytes = bytes(palette_cmyk)
    palette = pikepdf.Stream(pdf, palette_bytes)

    # Index data: solid color = all zeros (every pixel uses palette[0]).
    indices = bytes(w * h)

    raw_img = pikepdf.Stream(pdf, indices)
    raw_img["/Type"] = pikepdf.Name.XObject
    raw_img["/Subtype"] = pikepdf.Name.Image
    raw_img["/Width"] = w
    raw_img["/Height"] = h
    raw_img["/ColorSpace"] = pikepdf.Array(
        [pikepdf.Name.Indexed, pikepdf.Name.DeviceCMYK, 0, palette]
    )
    raw_img["/BitsPerComponent"] = 8

    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({"/Im0": raw_img}))
    dw, dh = display_pts
    page.Contents = pikepdf.Stream(pdf, f"q {dw} 0 0 {dh} 0 0 cm /Im0 Do Q".encode())
    pdf.save(pdf_path)
    return pdf_path


def _render_first_image_mean_rgb(pdf_path: Path) -> tuple[int, int, int]:
    """Render the PDF and average RGB samples from the image area.

    `_make_pdf_with_indexed_cmyk_image` draws the image at the PDF origin
    (bottom-left). Pixmaps have top-left origin, so the image lands at the
    bottom of the rendered pixmap.
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=72)
    h = pix.height
    samples = []
    # 50×50 block centered roughly in the bottom-left image region (the image
    # is 72×72 pts at dpi=72 = 72×72 px in the bottom-left corner).
    for y in range(h - 60, h - 10):
        for x in range(10, 60):
            r, g, b = pix.pixel(x, y)[:3]
            samples.append((r, g, b))
    doc.close()
    avg = (
        sum(s[0] for s in samples) // len(samples),
        sum(s[1] for s in samples) // len(samples),
        sum(s[2] for s in samples) // len(samples),
    )
    return avg


def test_resample_indexed_cmyk_preserves_color(tmp_path: Path):
    """Indexed CMYK source images must render the same color after resampling.

    Pillow's CMYK convention is 0=full ink (RGB-like), while PDF uses 0=no ink.
    When pikepdf decodes Indexed CMYK images, it hands PIL raw PDF-convention
    bytes from the palette lookup — but PIL operates on them in its own
    inverted convention. Pillow's invert-on-save then produces JPEG bytes that
    render as the COLOR INVERSE of the source. The fix: pre-invert PIL values
    for non-DCT sources before passing to Pillow's JPEG writer."""
    # Dark palette entry: 78% C, 39% M, 20% Y, 12% K. This is the kind of
    # value the user's spine logo uses (dark blue-purple-ish).
    pdf_path = _make_pdf_with_indexed_cmyk_image(
        tmp_path,
        palette_cmyk=(200, 100, 50, 30),
        # 0.25 dpi — guarantees the resampler decides to resample.
        img_size=(100, 100),
        display_pts=(72, 72),
    )
    output_path = tmp_path / "resampled.pdf"
    resample_images(pdf_path, output_path, target_dpi=300)

    src_rgb = _render_first_image_mean_rgb(pdf_path)
    out_rgb = _render_first_image_mean_rgb(output_path)
    # Allow some JPEG quantization slack.
    for s, o, ch in zip(src_rgb, out_rgb, "RGB", strict=True):
        assert abs(s - o) <= 5, f"channel {ch} drifted from source: src={src_rgb} out={out_rgb}"
