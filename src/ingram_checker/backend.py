"""Backend dispatch: routes to native or Ghostscript implementations.

By default uses native (PyMuPDF + pikepdf + Pillow) implementations.
Call set_backend(use_ghostscript=True) to switch to Ghostscript subprocess calls.
"""

from __future__ import annotations

from . import ghostscript as _gs
from . import native_ops as _native
from .ghostscript import InkCoverage  # noqa: F401 — re-export data class

# Current function bindings (module-level, swapped by set_backend)
measure_ink_coverage = _native.measure_ink_coverage
measure_max_pixel_ink_density = _native.measure_max_pixel_ink_density
resample_images = _native.resample_images
convert_to_cmyk = _native.convert_to_cmyk
convert_to_grayscale = _native.convert_to_grayscale


def set_backend(*, use_ghostscript: bool = False) -> None:
    """Switch between native and Ghostscript backends."""
    global measure_ink_coverage, measure_max_pixel_ink_density
    global resample_images, convert_to_cmyk, convert_to_grayscale

    if use_ghostscript:
        measure_ink_coverage = _gs.measure_ink_coverage
        measure_max_pixel_ink_density = _gs.measure_max_pixel_ink_density
        resample_images = _gs.resample_images
        convert_to_cmyk = _gs.convert_to_cmyk
        convert_to_grayscale = _gs.convert_to_grayscale
    else:
        measure_ink_coverage = _native.measure_ink_coverage
        measure_max_pixel_ink_density = _native.measure_max_pixel_ink_density
        resample_images = _native.resample_images
        convert_to_cmyk = _native.convert_to_cmyk
        convert_to_grayscale = _native.convert_to_grayscale
