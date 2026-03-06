"""CLI entry point using click."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from .checks.barcode import BarcodeCheck
from .checks.color import ColorSpaceCheck, ICCProfileCheck, SpotColorCheck
from .checks.cover_size import CoverPageCountCheck, CoverSizeCheck
from .checks.content import (
    BracketedTextCheck,
    ManufacturingStatementCheck,
    PaperCertificationCheck,
)
from .checks.crop_marks import CropMarksCheck
from .checks.fonts import FontEmbeddingCheck
from .checks.ink_density import InkDensityCheck
from .checks.margins import MarginCheck
from .checks.page_size import BleedCheck, PageCountCheck, PageSizeCheck
from .checks.pdfx import PDFXCheck
from .checks.resolution import ResolutionCheck
from .config import get_trim_size
from .fixers.color_converter import ColorConverter
from .fixers.crop_stripper import CropStripper
from .fixers.icc_remover import ICCRemover
from .fixers.image_downsampler import ImageDownsampler
from .fixers.page_padder import PagePadder
from .fixers.spot_converter import SpotConverter
from .models import (
    BindingType,
    BookSpec,
    CheckResult,
    CheckStatus,
    ColorType,
    FixResult,
    ProductType,
    Severity,
    TrimSize,
)
from .report import render_json, render_terminal

console = Console()

INTERIOR_CHECKS = [
    FontEmbeddingCheck(),
    PageCountCheck(),
    PageSizeCheck(),
    BleedCheck(),
    ICCProfileCheck(),
    SpotColorCheck(),
    ColorSpaceCheck(),
    CropMarksCheck(),
    InkDensityCheck(),
    ResolutionCheck(),
    ManufacturingStatementCheck(),
    PaperCertificationCheck(),
    BracketedTextCheck(),
    MarginCheck(),
    PDFXCheck(),
]

COVER_CHECKS = [
    FontEmbeddingCheck(),
    CoverPageCountCheck(),
    CoverSizeCheck(),
    ICCProfileCheck(),
    SpotColorCheck(),
    ColorSpaceCheck(),
    InkDensityCheck(),
    ResolutionCheck(),
    BarcodeCheck(),
]


def _filter_checks(
    checks: list,
    enable: tuple[str, ...],
    disable: tuple[str, ...],
) -> list:
    """Filter checks based on --enable/--disable overrides."""
    filtered = []
    for check in checks:
        if check.name in disable:
            continue
        if check.name in enable or check.enabled_by_default:
            filtered.append(check)
    return filtered


def _list_checks(checks: list) -> None:
    """Print available checks and exit."""
    for check in checks:
        default = "on" if check.enabled_by_default else "off"
        console.print(f"  {check.name:30s} {check.description} [dim](default: {default})[/dim]")


def _parse_trim_size(trim_str: str) -> TrimSize:
    """Parse trim size from string like '6x9' or '5.5x8.5'."""
    ts = get_trim_size(trim_str)
    if ts:
        return ts
    # Try parsing as WxH
    try:
        parts = trim_str.lower().split("x")
        if len(parts) == 2:
            return TrimSize(float(parts[0]), float(parts[1]), trim_str)
    except ValueError:
        pass
    raise click.BadParameter(
        f"Unknown trim size: {trim_str}. Use format like '6x9' or '5.5x8.5'"
    )


def _apply_fixes(
    pdf_path: Path,
    spec: BookSpec,
    results: list[CheckResult],
) -> tuple[Path, list[FixResult]]:
    """Apply auto-fixes and return the output path and fix results."""
    output_path = pdf_path.parent / f"{pdf_path.stem}_fixed{pdf_path.suffix}"
    fix_results: list[FixResult] = []
    current_input = pdf_path

    # Determine which fixers to run based on check results
    fixers_to_run = []

    for r in results:
        if not r.fixable or r.status == CheckStatus.PASS:
            continue
        if r.check_name == "page_count":
            fixers_to_run.append(PagePadder())
        elif r.check_name == "icc_profiles":
            fixers_to_run.append(ICCRemover())
        elif r.check_name == "spot_colors":
            fixers_to_run.append(SpotConverter())
        elif r.check_name == "color_space":
            fixers_to_run.append(ColorConverter())
        elif r.check_name == "crop_marks":
            fixers_to_run.append(CropStripper())
        elif r.check_name == "resolution" and "above" in r.message:
            fixers_to_run.append(ImageDownsampler())

    if not fixers_to_run:
        return pdf_path, []

    # Run fixers sequentially, each reading previous output
    for i, fixer in enumerate(fixers_to_run):
        fr = fixer.fix(current_input, output_path, spec)
        fix_results.append(fr)
        if fr.success:
            current_input = output_path

    return output_path, fix_results


@click.group()
def cli() -> None:
    """Ingram Lightning Source PDF compliance checker."""
    pass


@cli.command()
@click.argument("pdf_file", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--trim-size", "-t", default=None,
    help="Trim size (e.g. 6x9, 5.5x8.5)",
)
@click.option(
    "--color-type", "-c", type=click.Choice(["bw", "color"]), default="bw",
    help="Interior color type",
)
@click.option(
    "--bleed/--no-bleed", default=False,
    help="Whether the PDF includes 0.125\" bleed (default: --no-bleed)",
)
@click.option("--fix", "do_fix", is_flag=True, help="Auto-fix what we can")
@click.option(
    "--enable", "-e", multiple=True,
    help="Enable a check that is off by default (repeatable)",
)
@click.option(
    "--disable", "-d", multiple=True,
    help="Disable a check that is on by default (repeatable)",
)
@click.option("--list-checks", is_flag=True, help="List available checks and exit")
@click.option(
    "--format", "output_format", type=click.Choice(["terminal", "json"]),
    default="terminal", help="Output format",
)
def interior(
    pdf_file: Path | None,
    trim_size: str | None,
    color_type: str,
    bleed: bool,
    do_fix: bool,
    enable: tuple[str, ...],
    disable: tuple[str, ...],
    list_checks: bool,
    output_format: str,
) -> None:
    """Check an interior PDF for Ingram Lightning Source compliance."""
    if list_checks:
        console.print("[bold]Available interior checks:[/bold]")
        _list_checks(INTERIOR_CHECKS)
        return

    if pdf_file is None:
        raise click.UsageError("Missing argument 'PDF_FILE'.")
    if trim_size is None:
        raise click.UsageError("Missing option '--trim-size' / '-t'.")

    ts = _parse_trim_size(trim_size)
    spec = BookSpec(
        product_type=ProductType.INTERIOR,
        trim_size=ts,
        color_type=ColorType(color_type),
        bleed=bleed,
    )

    checks = _filter_checks(INTERIOR_CHECKS, enable, disable)

    if output_format == "terminal":
        console.print(f"[bold]Checking interior PDF:[/bold] {pdf_file}")
        bleed_label = "yes" if bleed else "no"
        console.print(f"[bold]Trim size:[/bold] {ts} | [bold]Color:[/bold] {color_type} | [bold]Bleed:[/bold] {bleed_label}")
        console.print()

    results: list[CheckResult] = []
    for check in checks:
        try:
            check_results = check.run(pdf_file, spec)
            results.extend(check_results)
        except Exception as e:
            results.append(CheckResult(
                check_name=check.name,
                status=CheckStatus.SKIP,
                message=f"Check failed: {e}",
                severity=Severity.INFO,
            ))

    fix_results: list[FixResult] | None = None
    if do_fix:
        output_path, fix_results = _apply_fixes(pdf_file, spec, results)
        if fix_results and any(fr.success for fr in fix_results):
            if output_format == "terminal":
                console.print(f"\n[green]Fixed PDF written to:[/green] {output_path}")

    if output_format == "json":
        click.echo(render_json(results, fix_results))
    else:
        render_terminal(results, fix_results, console)

    # Exit code: 1 if errors, 0 otherwise
    has_errors = any(
        r.status == CheckStatus.FAIL and r.severity == Severity.ERROR
        for r in results
    )
    sys.exit(1 if has_errors else 0)


@cli.command()
@click.argument("pdf_file", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--trim-size", "-t", default=None,
    help="Trim size (e.g. 6x9, 5.5x8.5)",
)
@click.option(
    "--binding", "-b", type=click.Choice(["perfectbound", "casewrap", "coil", "saddle"]),
    default="perfectbound", help="Binding type",
)
@click.option("--fix", "do_fix", is_flag=True, help="Auto-fix what we can")
@click.option(
    "--enable", "-e", multiple=True,
    help="Enable a check that is off by default (repeatable)",
)
@click.option(
    "--disable", "-d", multiple=True,
    help="Disable a check that is on by default (repeatable)",
)
@click.option("--list-checks", is_flag=True, help="List available checks and exit")
@click.option(
    "--format", "output_format", type=click.Choice(["terminal", "json"]),
    default="terminal", help="Output format",
)
def cover(
    pdf_file: Path | None,
    trim_size: str | None,
    binding: str,
    do_fix: bool,
    enable: tuple[str, ...],
    disable: tuple[str, ...],
    list_checks: bool,
    output_format: str,
) -> None:
    """Check a cover PDF for Ingram Lightning Source compliance."""
    if list_checks:
        console.print("[bold]Available cover checks:[/bold]")
        _list_checks(COVER_CHECKS)
        return

    if pdf_file is None:
        raise click.UsageError("Missing argument 'PDF_FILE'.")
    if trim_size is None:
        raise click.UsageError("Missing option '--trim-size' / '-t'.")

    ts = _parse_trim_size(trim_size)
    spec = BookSpec(
        product_type=ProductType.COVER,
        trim_size=ts,
        color_type=ColorType.COLOR,
        binding=BindingType(binding),
    )

    checks = _filter_checks(COVER_CHECKS, enable, disable)

    if output_format == "terminal":
        console.print(f"[bold]Checking cover PDF:[/bold] {pdf_file}")
        console.print(
            f"[bold]Trim size:[/bold] {ts} | "
            f"[bold]Binding:[/bold] {binding}"
        )
        console.print()

    results: list[CheckResult] = []
    for check in checks:
        try:
            check_results = check.run(pdf_file, spec)
            results.extend(check_results)
        except Exception as e:
            results.append(CheckResult(
                check_name=check.name,
                status=CheckStatus.SKIP,
                message=f"Check failed: {e}",
                severity=Severity.INFO,
            ))

    fix_results: list[FixResult] | None = None
    if do_fix:
        output_path, fix_results = _apply_fixes(pdf_file, spec, results)
        if fix_results and any(fr.success for fr in fix_results):
            if output_format == "terminal":
                console.print(f"\n[green]Fixed PDF written to:[/green] {output_path}")

    if output_format == "json":
        click.echo(render_json(results, fix_results))
    else:
        render_terminal(results, fix_results, console)

    has_errors = any(
        r.status == CheckStatus.FAIL and r.severity == Severity.ERROR
        for r in results
    )
    sys.exit(1 if has_errors else 0)
