"""Tests for the page padder fixer."""

from pathlib import Path

import pikepdf

from ingram_checker.fixers.page_padder import PagePadder
from ingram_checker.models import (
    BookSpec,
    ColorType,
    ProductType,
    TrimSize,
)

SPEC_6X9 = BookSpec(
    product_type=ProductType.INTERIOR,
    trim_size=TrimSize(6.0, 9.0, "6x9"),
    color_type=ColorType.BW,
)


def test_pad_odd_pages(odd_page_pdf: Path, tmp_path: Path):
    output = tmp_path / "fixed.pdf"
    fixer = PagePadder()
    result = fixer.fix(odd_page_pdf, output, SPEC_6X9)

    assert result.success
    assert output.exists()

    with pikepdf.open(output) as pdf:
        assert len(pdf.pages) == 4  # 3 + 1 blank


def test_pad_even_pages_noop(simple_pdf: Path, tmp_path: Path):
    output = tmp_path / "fixed.pdf"
    fixer = PagePadder()
    result = fixer.fix(simple_pdf, output, SPEC_6X9)

    assert not result.success  # no change needed
