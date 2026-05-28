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


def _cmyk_source_needs_preinvert(xo: pikepdf.Object) -> bool:
    """Return True if pikepdf hands PIL CMYK values in PDF convention (0=no ink).

    Pillow stores CMYK in RGB-like convention (0=full ink). When the source
    is a CMYK JPEG (DCTDecode), libjpeg+Pillow auto-invert during read so
    PIL ends up with values in PIL convention and a round-trip through
    PIL's JPEG writer produces correctly-encoded PDF bytes. But when the
    source is an Indexed palette or raw FlateDecode CMYK, pikepdf returns
    the raw PDF-convention bytes unchanged — PIL then treats them as
    PIL-convention and Pillow's invert-on-save lands them upside-down,
    producing color-inverted output. For those sources we must pre-invert
    the PIL values before passing them to the JPEG writer.
    """
    filt = xo.get("/Filter")
    if filt is None:
        return True
    if isinstance(filt, pikepdf.Name):
        return str(filt) != "/DCTDecode"
    if isinstance(filt, pikepdf.Array):
        return not any(isinstance(f, pikepdf.Name) and str(f) == "/DCTDecode" for f in filt)
    return True


def _save_cmyk_jpeg(pil_img: Image.Image, pre_invert: bool = False, quality: int = 95) -> bytes:
    """Encode a CMYK PIL image as JPEG bytes safe for PDF embedding.

    pre_invert: True when PIL holds PDF-convention CMYK values (from a non-DCT
    source). See _cmyk_source_needs_preinvert for the convention details.
    """
    if pre_invert:
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
    # Phase 1: Build a map of (page_index, xobj_name) -> effective DPI using PyMuPDF
    doc = fitz.open(str(input_path))
    # Map (page_0idx, image_name) -> (dpi_x, dpi_y)
    image_dpi: dict[tuple[int, str], tuple[float, float]] = {}
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            for img in page.get_images(full=True):
                xref = img[0]
                img_name = img[7] if len(img) > 7 else ""
                try:
                    img_info = doc.extract_image(xref)
                    if img_info is None:
                        continue
                    pix_w = img_info.get("width", 0)
                    pix_h = img_info.get("height", 0)
                    if pix_w == 0 or pix_h == 0:
                        continue
                    rects = page.get_image_rects(img[7] if len(img) > 7 else xref)
                    if not rects:
                        continue
                    rect = rects[0]
                    if rect.is_empty or rect.is_infinite:
                        continue
                    disp_w = rect.width / 72.0
                    disp_h = rect.height / 72.0
                    dpi_x = pix_w / disp_w if disp_w > 0 else 0
                    dpi_y = pix_h / disp_h if disp_h > 0 else 0
                    if img_name:
                        image_dpi[(page_num, img_name)] = (dpi_x, dpi_y)
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

                    # Look up DPI. The pikepdf name has a leading /
                    clean_name = str(xo_name).lstrip("/")
                    dpi_info = image_dpi.get((page_idx, clean_name))
                    if dpi_info is None:
                        continue

                    dpi_x, dpi_y = dpi_info
                    if dpi_x <= 0 or dpi_y <= 0:
                        continue
                    # Skip only when both axes are already close enough — must
                    # not gate on min() alone, as a non-uniformly scaled image
                    # can have one offending axis while the other is fine.
                    if abs(dpi_x - target_dpi) < 10 and abs(dpi_y - target_dpi) < 10:
                        continue

                    # Per-axis target: matching the displayed size at target_dpi.
                    # Avoids bloating the over-resolution axis of a stretched image.
                    new_width = max(1, round(width * target_dpi / dpi_x))
                    new_height = max(1, round(height * target_dpi / dpi_y))

                    pil_img = pikepdf.PdfImage(xo).as_pil_image()
                    pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)

                    if pil_img.mode == "CMYK":
                        jpeg_bytes = _save_cmyk_jpeg(
                            pil_img, pre_invert=_cmyk_source_needs_preinvert(xo)
                        )
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
        pil_img = pikepdf.PdfImage(xo).as_pil_image()
    except Exception:
        return None

    pil_img = pil_img.convert(target_mode)

    if target_mode == "CMYK":
        # The source's PIL CMYK may be in PDF convention (Indexed-CMYK source
        # decoded by pikepdf) or PIL convention (everything else). Detect from
        # the source filter so we pre-invert only when needed.
        jpeg_bytes = _save_cmyk_jpeg(pil_img, pre_invert=_cmyk_source_needs_preinvert(xo))
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
