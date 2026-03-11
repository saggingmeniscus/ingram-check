"""Tests for backend dispatch."""

from ingram_checker import backend


def test_default_backend_is_native():
    """By default, the backend should use native implementations."""
    backend.set_backend(use_ghostscript=False)
    assert "native_ops" in backend.measure_ink_coverage.__module__
    assert "native_ops" in backend.convert_to_grayscale.__module__


def test_use_ghostscript_backend():
    """Setting use_ghostscript should switch to ghostscript implementations."""
    backend.set_backend(use_ghostscript=True)
    try:
        assert "ghostscript" in backend.measure_ink_coverage.__module__
        assert "ghostscript" in backend.convert_to_grayscale.__module__
    finally:
        backend.set_backend(use_ghostscript=False)
