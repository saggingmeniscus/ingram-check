"""Tests for color space checks."""

from pathlib import Path

from ingram_checker.checks.color import ICCProfileCheck
from ingram_checker.models import (
    BookSpec,
    CheckStatus,
    ColorType,
    ProductType,
    TrimSize,
)

SPEC_6X9 = BookSpec(
    product_type=ProductType.INTERIOR,
    trim_size=TrimSize(6.0, 9.0, "6x9"),
    color_type=ColorType.BW,
)


def test_no_icc(simple_pdf: Path):
    check = ICCProfileCheck()
    results = check.run(simple_pdf, SPEC_6X9)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_has_icc(pdf_with_icc: Path):
    check = ICCProfileCheck()
    results = check.run(pdf_with_icc, SPEC_6X9)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert results[0].fixable
