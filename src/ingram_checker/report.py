"""Terminal and JSON report rendering."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import CheckResult, CheckStatus, FixResult, Severity

STATUS_ICONS = {
    CheckStatus.PASS: "[green]PASS[/green]",
    CheckStatus.FAIL: "[red]FAIL[/red]",
    CheckStatus.WARN: "[yellow]WARN[/yellow]",
    CheckStatus.SKIP: "[dim]SKIP[/dim]",
}


def render_terminal(
    results: list[CheckResult],
    fix_results: list[FixResult] | None = None,
    console: Console | None = None,
) -> None:
    """Render check results as a rich terminal table."""
    if console is None:
        console = Console()

    # Summary counts
    errors = sum(
        1 for r in results if r.status == CheckStatus.FAIL and r.severity == Severity.ERROR
    )
    warnings = sum(
        1
        for r in results
        if r.status in (CheckStatus.FAIL, CheckStatus.WARN) and r.severity == Severity.WARNING
    )
    passed = sum(1 for r in results if r.status == CheckStatus.PASS)

    # Results table
    table = Table(title="Ingram Lightning Source Compliance Check", show_lines=True)
    table.add_column("Status", width=6, justify="center")
    table.add_column("Check", min_width=20)
    table.add_column("Result", min_width=30)
    table.add_column("Fix?", width=4, justify="center")

    for r in results:
        fix_col = "[green]Yes[/green]" if r.fixable else ""
        table.add_row(
            STATUS_ICONS.get(r.status, "?"),
            r.check_name,
            r.message,
            fix_col,
        )

    console.print(table)

    # Print details for failures/warnings
    for r in results:
        if r.details and r.status in (CheckStatus.FAIL, CheckStatus.WARN):
            severity_color = "red" if r.severity == Severity.ERROR else "yellow"
            console.print(
                Panel(
                    "\n".join(r.details),
                    title=f"[{severity_color}]{r.check_name}[/{severity_color}]",
                    border_style=severity_color,
                )
            )

    # Fix results
    if fix_results:
        console.print()
        fix_table = Table(title="Auto-Fix Results", show_lines=True)
        fix_table.add_column("Fixer", min_width=20)
        fix_table.add_column("Status", width=8, justify="center")
        fix_table.add_column("Message", min_width=30)

        for fr in fix_results:
            status = "[green]OK[/green]" if fr.success else "[red]FAILED[/red]"
            fix_table.add_row(fr.fixer_name, status, fr.message)

        console.print(fix_table)

    # Summary
    console.print()
    if errors > 0:
        console.print(f"[red bold]{errors} error(s)[/red bold], ", end="")
    if warnings > 0:
        console.print(f"[yellow]{warnings} warning(s)[/yellow], ", end="")
    console.print(f"[green]{passed} passed[/green]")

    if errors > 0:
        console.print(
            "[red bold]PDF is NOT compliant with Ingram Lightning Source requirements.[/red bold]"
        )
    elif warnings > 0:
        console.print("[yellow]PDF has warnings — review before submitting.[/yellow]")
    else:
        console.print("[green bold]PDF appears compliant![/green bold]")


def render_json(
    results: list[CheckResult],
    fix_results: list[FixResult] | None = None,
) -> str:
    """Render check results as JSON."""
    data = {
        "checks": [_check_to_dict(r) for r in results],
        "summary": {
            "errors": sum(
                1 for r in results if r.status == CheckStatus.FAIL and r.severity == Severity.ERROR
            ),
            "warnings": sum(
                1
                for r in results
                if r.status in (CheckStatus.FAIL, CheckStatus.WARN)
                and r.severity == Severity.WARNING
            ),
            "passed": sum(1 for r in results if r.status == CheckStatus.PASS),
            "compliant": all(
                r.status != CheckStatus.FAIL or r.severity != Severity.ERROR for r in results
            ),
        },
    }
    if fix_results:
        data["fixes"] = [
            {
                "fixer": fr.fixer_name,
                "success": fr.success,
                "message": fr.message,
                "changes": fr.changes,
            }
            for fr in fix_results
        ]
    return json.dumps(data, indent=2)


def _check_to_dict(r: CheckResult) -> dict:
    return {
        "check_name": r.check_name,
        "status": r.status.value,
        "message": r.message,
        "severity": r.severity.value,
        "details": r.details,
        "fixable": r.fixable,
    }
