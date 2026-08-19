"""Native PDF operations using PyMuPDF, pikepdf, Pillow, and numpy.

Replaces Ghostscript subprocess calls with pure-Python implementations.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
import pikepdf
from PIL import Image

from .config import RESOLUTION_WARN_HIGH
from .ghostscript import InkCoverage

# Keys that describe masking/rendering and are orthogonal to color space and sampling.
# When replacing an image XObject, these must be copied across — most importantly
# /SMask, which carries transparency for images whose RGB plane is a solid color
# (common for black-on-transparent logos embedded from PNG).
_PRESERVED_IMAGE_KEYS = ("/SMask", "/Mask", "/Intent", "/Interpolate", "/Metadata")


def _copy_preserved_image_keys(src: pikepdf.Object, dst: pikepdf.Stream) -> None:
    for key in _PRESERVED_IMAGE_KEYS:
        if key in src:
            dst[key] = src[key]


def _strip_jpeg_app14(data: bytes) -> bytes:
    """Remove the Adobe APP14 marker segment from JPEG data.

    Pillow's CMYK JPEG output includes an APP14 marker (transform=0) that
    some viewers interpret as a signal to invert the sample bytes. Since we
    take care to encode the CMYK bytes in PDF convention ourselves, the
    marker only confuses such viewers — strip it to make the output render
    consistently.
    """
    i = data.find(b"\xff\xee")
    if i < 0:
        return data
    seg_len = int.from_bytes(data[i + 2 : i + 4], "big")
    return data[:i] + data[i + 2 + seg_len :]


def _source_is_dct(xo: pikepdf.Object) -> bool:
    """Return True if the image XObject's sample data is JPEG (DCTDecode)."""
    filt = xo.get("/Filter")
    if filt is None:
        return False
    if isinstance(filt, pikepdf.Name):
        return str(filt) == "/DCTDecode"
    if isinstance(filt, pikepdf.Array):
        return any(isinstance(f, pikepdf.Name) and str(f) == "/DCTDecode" for f in filt)
    return False


def _has_inverting_decode(xo: pikepdf.Object) -> bool:
    """Return True for a /Decode array that inverts samples, e.g. [1 0 1 0 1 0 1 0]."""
    decode = xo.get("/Decode")
    if not isinstance(decode, pikepdf.Array) or len(decode) < 2:
        return False
    return float(decode[0]) > float(decode[1])


def _cmyk_load_is_inverted(xo: pikepdf.Object) -> bool:
    """Return True if as_pil_image() hands back CMYK values inverted vs PIL's convention.

    Both PDF DeviceCMYK and Pillow's in-memory CMYK use 0=no ink, so the two
    agree by default. Two independent things can flip the sense:

    * Pillow's JPEG codec always inverts CMYK samples on read (and on write),
      following the Adobe convention -- regardless of whether the JPEG carries
      an APP14 marker. So a DCTDecode source arrives inverted.
    * A /Decode [1 0 ...] array means the PDF itself inverts the stored samples.
      pikepdf does not apply /Decode when handing the JPEG to Pillow, so this
      flips the sense back.

    The two cancel, hence XOR. Non-DCT sources (raw FlateDecode CMYK, Indexed
    palettes) reach Pillow byte-for-byte, so only /Decode matters for them.
    """
    return _source_is_dct(xo) != _has_inverting_decode(xo)


def _load_cmyk_in_pil_convention(xo: pikepdf.Object) -> Image.Image:
    """Decode a CMYK image XObject into a PIL image with 0=no ink.

    Any in-memory operation that interprets pixel values -- most importantly
    .convert("L") -- needs the values the page actually renders, not whatever
    convention the source encoding happened to use.
    """
    pil_img = pikepdf.PdfImage(xo).as_pil_image()
    if pil_img.mode == "CMYK" and _cmyk_load_is_inverted(xo):
        pil_img = Image.eval(pil_img, lambda v: 255 - v)
    return pil_img


def _save_cmyk_jpeg(pil_img: Image.Image, quality: int = 95) -> bytes:
    """Encode a CMYK PIL image as JPEG bytes safe for PDF embedding.

    `pil_img` must hold PIL-convention values (0=no ink). Pillow's JPEG writer
    inverts CMYK on save, and the streams we emit carry no /Decode array, so we
    pre-invert to land plain PDF-convention samples on disk.
    """
    pil_img = Image.eval(pil_img, lambda v: 255 - v)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality)
    return _strip_jpeg_app14(buf.getvalue())


def _rgb_to_cmyk_coverage(pixels: np.ndarray) -> tuple[float, float, float, float]:
    """Convert an RGB pixel array to average CMYK percentages.

    pixels: shape (H, W, 3), dtype uint8, values 0-255 (0=black, 255=white).
    Returns (C, M, Y, K) each as a percentage 0-100.
    """
    rgb = pixels.astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    k = 1.0 - np.maximum(np.maximum(r, g), b)
    denom = np.where(k < 1.0, 1.0 - k, 1.0)
    c = np.where(k < 1.0, (1.0 - r - k) / denom, 0.0)
    m = np.where(k < 1.0, (1.0 - g - k) / denom, 0.0)
    y = np.where(k < 1.0, (1.0 - b - k) / denom, 0.0)

    return (
        float(np.mean(c)) * 100.0,
        float(np.mean(m)) * 100.0,
        float(np.mean(y)) * 100.0,
        float(np.mean(k)) * 100.0,
    )


def _rgb_pixels_to_cmyk_density(pixels: np.ndarray) -> np.ndarray:
    """Convert RGB pixels to per-pixel CMYK density sum (0-400 scale).

    Returns a 2D array of C+M+Y+K percentage sums per pixel.
    """
    rgb = pixels.astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    k = 1.0 - np.maximum(np.maximum(r, g), b)
    denom = np.where(k < 1.0, 1.0 - k, 1.0)
    c = np.where(k < 1.0, (1.0 - r - k) / denom, 0.0)
    m = np.where(k < 1.0, (1.0 - g - k) / denom, 0.0)
    y = np.where(k < 1.0, (1.0 - b - k) / denom, 0.0)

    return (c + m + y + k) * 100.0


def measure_ink_coverage(pdf_path: str | Path, resolution: int = 72) -> list[InkCoverage]:
    """Measure per-page average CMYK ink coverage using PyMuPDF rendering."""
    doc = fitz.open(str(pdf_path))
    coverages = []
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(resolution / 72.0, resolution / 72.0)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            c, m, y, k = _rgb_to_cmyk_coverage(pixels)
            coverages.append(
                InkCoverage(
                    page=page_num + 1,
                    cyan=c,
                    magenta=m,
                    yellow=y,
                    black=k,
                )
            )
    finally:
        doc.close()
    return coverages


def measure_max_pixel_ink_density(
    pdf_path: str | Path,
    pages: list[int] | None = None,
    resolution: int = 72,
) -> dict[int, float]:
    """Measure maximum per-pixel ink density for specific pages using PyMuPDF.

    Returns {page_number: max_density_percent} where density is C+M+Y+K sum.
    """
    doc = fitz.open(str(pdf_path))
    results: dict[int, float] = {}
    try:
        target_pages = pages or list(range(1, len(doc) + 1))
        for page_num in target_pages:
            if page_num < 1 or page_num > len(doc):
                continue
            page = doc[page_num - 1]
            mat = fitz.Matrix(resolution / 72.0, resolution / 72.0)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            density = _rgb_pixels_to_cmyk_density(pixels)
            results[page_num] = float(density.max())
    finally:
        doc.close()
    return results


def resample_images(
    input_path: str | Path,
    output_path: str | Path,
    target_dpi: int = 300,
) -> None:
    """Resample images to target DPI using pikepdf + Pillow.

    Uses PyMuPDF to get accurate display dimensions for DPI calculation,
    then pikepdf to replace image XObjects with resampled versions.
    """
    # Phase 1: Build (page, name) -> per-pixel-axis display extents in points.
    #
    # Using the content-stream transform matrix (a b c d e f) rather than the
    # axis-aligned bounding box: for a rotated image the bbox swaps width
    # and height, but the column-vector magnitudes ‖(a,b)‖ and ‖(c,d)‖ tell
    # us how many points the image's pixel-W and pixel-H axes actually span
    # on the page. Without this, a 720x130 px image rotated 90° onto a
    # 2.0"x0.36" spine reads as 18/2000 ppi instead of its true 360 ppi.
    doc = fitz.open(str(input_path))
    image_extent: dict[tuple[int, str], tuple[int, int, float, float]] = {}
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            # xref -> (extent_w_pts, extent_h_pts) for this page's draws.
            xref_to_extent: dict[int, tuple[float, float]] = {}
            for info in page.get_image_info(xrefs=True):
                xref = info.get("xref", 0)
                tr = info.get("transform")
                if not xref or not tr or len(tr) < 4:
                    continue
                a, b, c, d = tr[0], tr[1], tr[2], tr[3]
                ext_w_pts = (a * a + b * b) ** 0.5
                ext_h_pts = (c * c + d * d) ** 0.5
                if ext_w_pts > 0 and ext_h_pts > 0:
                    xref_to_extent[xref] = (ext_w_pts, ext_h_pts)

            for img in page.get_images(full=True):
                xref = img[0]
                img_name = img[7] if len(img) > 7 else ""
                if not img_name or xref not in xref_to_extent:
                    continue
                try:
                    img_info = doc.extract_image(xref)
                    if img_info is None:
                        continue
                    pix_w = img_info.get("width", 0)
                    pix_h = img_info.get("height", 0)
                    if pix_w == 0 or pix_h == 0:
                        continue
                    ext_w_pts, ext_h_pts = xref_to_extent[xref]
                    image_extent[(page_num, img_name)] = (
                        pix_w,
                        pix_h,
                        ext_w_pts,
                        ext_h_pts,
                    )
                except Exception:
                    continue
    finally:
        doc.close()

    # Phase 2: Walk with pikepdf and resample
    shutil.copy2(str(input_path), str(output_path))
    with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            resources = page.get("/Resources")
            if resources is None:
                continue
            xobjects = resources.get("/XObject")
            if xobjects is None:
                continue
            for xo_name, xo_ref in dict(xobjects).items():
                try:
                    xo = xo_ref
                    if str(xo.get("/Subtype", "")) != "/Image":
                        continue

                    width = int(xo.get("/Width", 0))
                    height = int(xo.get("/Height", 0))
                    if width == 0 or height == 0:
                        continue

                    # Look up extent. The pikepdf name has a leading /
                    clean_name = str(xo_name).lstrip("/")
                    extent = image_extent.get((page_idx, clean_name))
                    if extent is None:
                        continue

                    _, _, ext_w_pts, ext_h_pts = extent
                    if ext_w_pts <= 0 or ext_h_pts <= 0:
                        continue
                    dpi_x = width * 72.0 / ext_w_pts
                    dpi_y = height * 72.0 / ext_h_pts
                    # Skip when both axes are already inside the acceptable
                    # band [target_dpi-10, RESOLUTION_WARN_HIGH]. Above the
                    # band, downsampling saves file size; below, we must
                    # upsample to meet the minimum.
                    if (target_dpi - 10) <= dpi_x <= RESOLUTION_WARN_HIGH and (
                        target_dpi - 10
                    ) <= dpi_y <= RESOLUTION_WARN_HIGH:
                        continue

                    # Per-pixel-axis target: enough pixels to hit target_dpi
                    # along the *true* display extent of each pixel axis
                    # (transform-derived, so rotation is handled correctly).
                    new_width = max(1, round(target_dpi * ext_w_pts / 72.0))
                    new_height = max(1, round(target_dpi * ext_h_pts / 72.0))

                    pil_img = _load_cmyk_in_pil_convention(xo)
                    pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

                    if pil_img.mode == "CMYK":
                        jpeg_bytes = _save_cmyk_jpeg(pil_img)
                        cs_name = pikepdf.Name.DeviceCMYK
                    elif pil_img.mode in ("L", "1"):
                        if pil_img.mode == "1":
                            pil_img = pil_img.convert("L")
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=95)
                        jpeg_bytes = buf.getvalue()
                        cs_name = pikepdf.Name.DeviceGray
                    else:
                        pil_img = pil_img.convert("RGB")
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=95)
                        jpeg_bytes = buf.getvalue()
                        cs_name = pikepdf.Name.DeviceRGB

                    new_stream = pikepdf.Stream(pdf, jpeg_bytes)
                    new_stream["/Type"] = pikepdf.Name.XObject
                    new_stream["/Subtype"] = pikepdf.Name.Image
                    new_stream["/Width"] = new_width
                    new_stream["/Height"] = new_height
                    new_stream["/BitsPerComponent"] = 8
                    new_stream["/Filter"] = pikepdf.Name.DCTDecode
                    new_stream["/ColorSpace"] = cs_name
                    _copy_preserved_image_keys(xo, new_stream)
                    xobjects[xo_name] = new_stream

                except Exception:
                    continue

        pdf.save(output_path)


def _convert_image_xobject(
    pdf: pikepdf.Pdf,
    xo: pikepdf.Stream,
    target_mode: str,
) -> pikepdf.Stream | None:
    """Convert an image XObject to the target Pillow color mode.

    target_mode: 'L' for grayscale, 'CMYK' for CMYK.
    Returns new stream or None if conversion not needed/possible.
    """
    cs = xo.get("/ColorSpace")
    cs_str = str(cs) if isinstance(cs, pikepdf.Name) else ""

    if cs_str == "/DeviceGray" and target_mode == "L":
        return None
    if cs_str == "/DeviceCMYK" and target_mode == "CMYK":
        return None

    width = int(xo.get("/Width", 0))
    height = int(xo.get("/Height", 0))
    if width == 0 or height == 0:
        return None

    try:
        pil_img = _load_cmyk_in_pil_convention(xo)
    except Exception:
        return None

    pil_img = pil_img.convert(target_mode)

    if target_mode == "CMYK":
        jpeg_bytes = _save_cmyk_jpeg(pil_img)
    else:
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=95)
        jpeg_bytes = buf.getvalue()

    new_stream = pikepdf.Stream(pdf, jpeg_bytes)
    new_stream["/Type"] = pikepdf.Name.XObject
    new_stream["/Subtype"] = pikepdf.Name.Image
    new_stream["/Width"] = width
    new_stream["/Height"] = height
    new_stream["/BitsPerComponent"] = 8
    new_stream["/Filter"] = pikepdf.Name.DCTDecode
    if target_mode == "L":
        new_stream["/ColorSpace"] = pikepdf.Name.DeviceGray
    elif target_mode == "CMYK":
        new_stream["/ColorSpace"] = pikepdf.Name.DeviceCMYK
    _copy_preserved_image_keys(xo, new_stream)
    return new_stream


def _convert_pdf_images(
    input_path: str | Path,
    output_path: str | Path,
    target_mode: str,
) -> None:
    """Convert all image XObjects in a PDF to target color mode."""
    shutil.copy2(str(input_path), str(output_path))
    with pikepdf.open(output_path, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            resources = page.get("/Resources")
            if resources is None:
                continue

            xobjects = resources.get("/XObject")
            if xobjects is not None:
                for xo_name, xo_ref in dict(xobjects).items():
                    try:
                        xo = xo_ref
                        if str(xo.get("/Subtype", "")) != "/Image":
                            continue
                        new_stream = _convert_image_xobject(pdf, xo, target_mode)
                        if new_stream is not None:
                            xobjects[xo_name] = new_stream
                    except Exception:
                        continue

            # Replace DeviceRGB references in ColorSpace dict
            cs_dict = resources.get("/ColorSpace")
            if cs_dict is not None:
                target_name = (
                    pikepdf.Name.DeviceGray if target_mode == "L" else pikepdf.Name.DeviceCMYK
                )
                to_replace = []
                for cs_name, cs_obj in dict(cs_dict).items():
                    if isinstance(cs_obj, pikepdf.Name) and str(cs_obj) == "/DeviceRGB":
                        to_replace.append(cs_name)
                for name in to_replace:
                    cs_dict[name] = target_name

        pdf.save(output_path)


def convert_to_grayscale(
    input_path: str | Path,
    output_path: str | Path,
) -> None:
    """Convert a PDF's images to grayscale using Pillow."""
    _convert_pdf_images(input_path, output_path, "L")


def convert_to_cmyk(
    input_path: str | Path,
    output_path: str | Path,
) -> None:
    """Convert a PDF's images to CMYK using Pillow."""
    _convert_pdf_images(input_path, output_path, "CMYK")
