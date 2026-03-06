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
    result = runner.invoke(cli, [
        "interior", str(simple_pdf),
        "--trim-size", "6x9",
        "--color-type", "bw",
    ])
    # Should run without crashing
    assert result.exit_code in (0, 1)


def test_interior_json_output(simple_pdf: Path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "interior", str(simple_pdf),
        "--trim-size", "6x9",
        "--format", "json",
    ])
    assert result.exit_code in (0, 1)
    assert '"checks"' in result.output
    assert '"summary"' in result.output
