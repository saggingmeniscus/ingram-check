"""Test fixtures for ingram_checker tests."""

from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


def _add_blank_page(pdf: pikepdf.Pdf, width_pts: float, height_pts: float) -> None:
    pdf.add_blank_page(page_size=(width_pts, height_pts))


@pytest.fixture
def simple_pdf(tmp_path: Path) -> Path:
    """Create a minimal valid PDF with correct 6x9 bleed size."""
    pdf_path = tmp_path / "simple.pdf"
    width_pts = 6.125 * 72
    height_pts = 9.25 * 72

    pdf = pikepdf.Pdf.new()
    for _ in range(2):
        _add_blank_page(pdf, width_pts, height_pts)
    pdf.save(pdf_path)
    return pdf_path


@pytest.fixture
def odd_page_pdf(tmp_path: Path) -> Path:
    """Create a PDF with 3 pages (odd count)."""
    pdf_path = tmp_path / "odd.pdf"
    width_pts = 6.125 * 72
    height_pts = 9.25 * 72

    pdf = pikepdf.Pdf.new()
    for _ in range(3):
        _add_blank_page(pdf, width_pts, height_pts)
    pdf.save(pdf_path)
    return pdf_path


@pytest.fixture
def wrong_size_pdf(tmp_path: Path) -> Path:
    """Create a PDF with wrong page size (letter instead of 6x9+bleed)."""
    pdf_path = tmp_path / "wrong_size.pdf"
    width_pts = 8.5 * 72
    height_pts = 11 * 72

    pdf = pikepdf.Pdf.new()
    for _ in range(2):
        _add_blank_page(pdf, width_pts, height_pts)
    pdf.save(pdf_path)
    return pdf_path


@pytest.fixture
def pdf_with_icc(tmp_path: Path) -> Path:
    """Create a PDF with an ICCBased color space."""
    pdf_path = tmp_path / "icc.pdf"
    width_pts = 6.125 * 72
    height_pts = 9.25 * 72

    pdf = pikepdf.Pdf.new()

    # Create a dummy ICC profile stream
    icc_stream = pdf.make_stream(b"\x00" * 128)
    icc_stream["/N"] = 3

    # Add page then modify its resources
    _add_blank_page(pdf, width_pts, height_pts)
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(
        ColorSpace=pikepdf.Dictionary({
            "/CS1": pikepdf.Array([pikepdf.Name.ICCBased, icc_stream]),
        }),
    )

    # Add second page for even count
    _add_blank_page(pdf, width_pts, height_pts)
    pdf.save(pdf_path)
    return pdf_path
