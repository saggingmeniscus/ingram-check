"""Ghostscript subprocess wrapper for ink density measurement."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
import numpy as np


@dataclass
class InkCoverage:
    """Per-page ink coverage percentages."""
    page: int
    cyan: float
    magenta: float
    yellow: float
    black: float

    @property
    def total(self) -> float:
        return self.cyan + self.magenta + self.yellow + self.black


def _find_gs() -> str:
    """Find the Ghostscript executable."""
    import shutil
    for name in ("gs", "gswin64c", "gswin32c"):
        path = shutil.which(name)
        if path:
            return path
    raise FileNotFoundError(
        "Ghostscript not found. Install it: brew install ghostscript"
    )


def measure_ink_coverage(pdf_path: str | Path) -> list[InkCoverage]:
    """Measure per-page average CMYK ink coverage using gs inkcov device."""
    gs = _find_gs()
    result = subprocess.run(
        [
            gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            "-sDEVICE=inkcov",
            "-o", "-",
            str(pdf_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript inkcov failed: {result.stderr}")

    coverages = []
    page_num = 0
    # Each output line: C M Y K  CMYK OK
    pattern = re.compile(
        r"^\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+CMYK\s+OK"
    )
    for line in result.stdout.splitlines():
        m = pattern.match(line)
        if m:
            page_num += 1
            coverages.append(InkCoverage(
                page=page_num,
                cyan=float(m.group(1)) * 100,
                magenta=float(m.group(2)) * 100,
                yellow=float(m.group(3)) * 100,
                black=float(m.group(4)) * 100,
            ))
    return coverages


def measure_max_pixel_ink_density(
    pdf_path: str | Path,
    pages: list[int] | None = None,
    resolution: int = 72,
) -> dict[int, float]:
    """Measure maximum per-pixel ink density for specific pages.

    Renders pages to CMYK TIFF and finds the max C+M+Y+K pixel sum.
    Returns {page_number: max_density_percent}.
    """
    gs = _find_gs()
    results: dict[int, float] = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_pattern = str(Path(tmpdir) / "page_%04d.tif")

        cmd = [
            gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            "-sDEVICE=tiff32nc",
            f"-r{resolution}",
            f"-sOutputFile={output_pattern}",
        ]

        # If specific pages requested, add page range
        if pages:
            first = min(pages)
            last = max(pages)
            cmd.extend([f"-dFirstPage={first}", f"-dLastPage={last}"])

        cmd.append(str(pdf_path))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Ghostscript tiff32nc failed: {result.stderr}")

        # Read TIFF files and compute max ink density
        tiff_dir = Path(tmpdir)
        for tiff_file in sorted(tiff_dir.glob("page_*.tif")):
            # Extract page number from filename
            page_str = tiff_file.stem.split("_")[1]
            page_offset = int(page_str)
            if pages:
                actual_page = min(pages) + page_offset - 1
            else:
                actual_page = page_offset

            if pages and actual_page not in pages:
                continue

            try:
                img = Image.open(tiff_file)
                # CMYK image: 4 channels, each 0-255
                arr = np.array(img, dtype=np.float32)
                if arr.ndim == 3 and arr.shape[2] == 4:
                    # Sum all 4 channels per pixel, find max
                    pixel_sums = arr.sum(axis=2)
                    # Convert from 0-255 scale to 0-100% per channel
                    max_density = float(pixel_sums.max()) / 255.0 * 100.0
                    results[actual_page] = max_density
            except Exception:
                continue

    return results


def downsample_images(
    input_path: str | Path,
    output_path: str | Path,
    target_dpi: int = 300,
) -> None:
    """Downsample images above target_dpi using Ghostscript."""
    gs = _find_gs()
    result = subprocess.run(
        [
            gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress",
            "-dCompatibilityLevel=1.4",
            f"-dColorImageResolution={target_dpi}",
            f"-dGrayImageResolution={target_dpi}",
            f"-dMonoImageResolution={target_dpi}",
            "-dColorImageDownsampleType=/Bicubic",
            "-dGrayImageDownsampleType=/Bicubic",
            "-dMonoImageDownsampleType=/Bicubic",
            "-dDownsampleColorImages=true",
            "-dDownsampleGrayImages=true",
            "-dDownsampleMonoImages=true",
            f"-sOutputFile={output_path}",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript image downsampling failed: {result.stderr}")


def convert_to_cmyk(
    input_path: str | Path,
    output_path: str | Path,
) -> None:
    """Convert a PDF to CMYK color space using Ghostscript."""
    gs = _find_gs()
    result = subprocess.run(
        [
            gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress",
            "-sColorConversionStrategy=CMYK",
            "-dProcessColorModel=/DeviceCMYK",
            f"-sOutputFile={output_path}",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript CMYK conversion failed: {result.stderr}")


def convert_to_grayscale(
    input_path: str | Path,
    output_path: str | Path,
) -> None:
    """Convert a PDF to grayscale using Ghostscript."""
    gs = _find_gs()
    result = subprocess.run(
        [
            gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress",
            "-sColorConversionStrategy=Gray",
            "-dProcessColorModel=/DeviceGray",
            f"-sOutputFile={output_path}",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript grayscale conversion failed: {result.stderr}")
