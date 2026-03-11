"""Tests for the CLI."""

from pathlib import Path

from click.testing import CliRunner

from ingram_checker.cli import cli


def test_interior_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["interior", "--help"])
    assert result.exit_code == 0
    assert "trim-size" in result.output


def test_cover_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["cover", "--help"])
    assert result.exit_code == 0
    assert "trim-size" in result.output


def test_interior_simple_pdf(simple_pdf: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interior",
            str(simple_pdf),
            "--trim-size",
            "6x9",
            "--color-type",
            "bw",
        ],
    )
    # Should run without crashing
    assert result.exit_code in (0, 1)


def test_interior_json_output(simple_pdf: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interior",
            str(simple_pdf),
            "--trim-size",
            "6x9",
            "--format",
            "json",
        ],
    )
    assert result.exit_code in (0, 1)
    assert '"checks"' in result.output
    assert '"summary"' in result.output


def test_interior_auto_detect_trim_size(simple_pdf: Path):
    """When --trim-size is omitted, detect page size and report it."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interior",
            str(simple_pdf),
            "--color-type",
            "bw",
        ],
    )
    assert result.exit_code in (0, 1)
    assert "(detected)" in result.output


def test_interior_auto_detect_inconsistent(tmp_path: Path):
    """When pages have different sizes and no --trim-size, report error."""
    import pikepdf

    pdf_path = tmp_path / "mixed.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(6.0 * 72, 9.0 * 72))
    pdf.add_blank_page(page_size=(8.5 * 72, 11.0 * 72))
    pdf.save(pdf_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interior",
            str(pdf_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1
    assert "incorrect dimensions" in result.output
