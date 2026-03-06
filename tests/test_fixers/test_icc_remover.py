"""Tests for the ICC remover fixer."""

from pathlib import Path

from ingram_checker.checks.color import ICCProfileCheck
from ingram_checker.fixers.icc_remover import ICCRemover
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


def test_remove_icc(pdf_with_icc: Path, tmp_path: Path):
    output = tmp_path / "fixed.pdf"
    fixer = ICCRemover()
    result = fixer.fix(pdf_with_icc, output, SPEC_6X9)

    assert result.success
    assert output.exists()

    # Verify ICC is gone
    check = ICCProfileCheck()
    check_results = check.run(output, SPEC_6X9)
    assert check_results[0].status == CheckStatus.PASS
