"""CLI entry point for TTIMEOUT analyzer."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from tj_common.analysis.pipeline import run_analysis
from tj_common.cli_shared import (
    OutputType,
    SourceType,
    build_clickhouse_source,
    build_file_source,
    build_filters,
    format_filter_summary,
)
from tj_common.report.json_out import render_json as _render_json
from tj_common.report.labels import TTIMEOUT_LABELS
from tj_common.report.text import render_text as _render_text

app = typer.Typer(
    help="Analyze 1C TTIMEOUT events (wait timeout) and find lock culprits"
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    source: SourceType = typer.Option(SourceType.click, help="Log source type"),
    log_id: Optional[str] = typer.Option(
        None,
        "--log-id",
        help="Log stream id(s) in ClickHouse (comma-separated); required for --source click",
    ),
    time_from: Optional[str] = typer.Option(
        None, "--from", help="Optional start time (ISO)"
    ),
    time_to: Optional[str] = typer.Option(
        None, "--to", help="Optional end time (ISO)"
    ),
    min_duration: float = typer.Option(
        0.0, "--min-duration", help="Min wait duration in seconds"
    ),
    hosts: Optional[str] = typer.Option(
        None, help="Optional comma-separated host names"
    ),
    database: Optional[str] = typer.Option(
        None, "--database", help="Optional ProcessName / IB filter"
    ),
    file: Optional[str] = typer.Option(None, help="Path to TJ file (plain/json)"),
    base_date: Optional[str] = typer.Option(
        None, help="Base date for plain TJ (time-only lines)"
    ),
    clickhouse_host: Optional[str] = typer.Option(None, "--clickhouse-host"),
    clickhouse_port: Optional[int] = typer.Option(None, "--clickhouse-port"),
    clickhouse_user: Optional[str] = typer.Option(None, "--clickhouse-user"),
    clickhouse_password: Optional[str] = typer.Option(None, "--clickhouse-password"),
    clickhouse_db: Optional[str] = typer.Option(None, "--clickhouse-db"),
    output: OutputType = typer.Option(OutputType.both, "--output"),
):
    """Find TTIMEOUT victims and analyze culprit transactions."""
    if ctx.invoked_subcommand is not None:
        return

    filters = build_filters(
        log_id, time_from, time_to, min_duration, hosts, database, source
    )

    if source == SourceType.click:
        log_source = build_clickhouse_source(
            clickhouse_host,
            clickhouse_port,
            clickhouse_user,
            clickhouse_password,
            clickhouse_db,
            victim_table="tj_ttimeout",
            victim_event="TTIMEOUT",
        )
    else:
        log_source = build_file_source(
            source, file, base_date, victim_event="TTIMEOUT"
        )

    console.print(f"[dim]{format_filter_summary(filters, source)}[/dim]")

    result = run_analysis(log_source, filters)

    console.print(f"[green]Victims found: {len(result.victims)}[/green]")
    if result.errors:
        console.print(f"[yellow]Errors: {len(result.errors)}[/yellow]")

    if output in (OutputType.json, OutputType.both):
        console.print(_render_json(result, labels=TTIMEOUT_LABELS))
    if output in (OutputType.text, OutputType.both):
        if output == OutputType.both:
            console.print("\n" + "=" * 40 + " TEXT REPORT " + "=" * 40 + "\n")
        console.print(_render_text(result, labels=TTIMEOUT_LABELS))


def app_entry():
    app()


if __name__ == "__main__":
    app()
