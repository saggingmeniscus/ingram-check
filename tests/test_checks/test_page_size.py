"""Tests for page size, count, and bleed checks."""

from pathlib import Path

from ingram_checker.checks.page_size import PageCountCheck, PageSizeCheck
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
    bleed=True,
)


def test_page_count_even(simple_pdf: Path):
    check = PageCountCheck()
    results = check.run(simple_pdf, SPEC_6X9)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_page_count_odd(odd_page_pdf: Path):
    check = PageCountCheck()
    results = check.run(odd_page_pdf, SPEC_6X9)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
    assert results[0].fixable


def test_page_size_correct(simple_pdf: Path):
    check = PageSizeCheck()
    results = check.run(simple_pdf, SPEC_6X9)
    assert len(results) == 1
    assert results[0].status == CheckStatus.PASS


def test_page_size_wrong(wrong_size_pdf: Path):
    check = PageSizeCheck()
    results = check.run(wrong_size_pdf, SPEC_6X9)
    assert len(results) == 1
    assert results[0].status == CheckStatus.FAIL
