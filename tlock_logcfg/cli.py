"""CLI: build logcfg.xml from TLOCK victims with WaitConnections."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from tj_common.cli_shared import SourceType, build_clickhouse_source, build_file_source, build_filters, parse_csv
from tj_common.logcfg import (
    collect_region_stats,
    load_default_template,
    load_template,
    platform_supports_json_zip,
    write_logcfg_report,
)
from tj_common.logcfg import build_logcfg as _build_logcfg
from tj_common.report.write import resolve_report_dir
from tj_common.utils import apply_mcp_clickhouse_env

app = typer.Typer(
    help="Build 1C tech journal logcfg.xml from TLOCK events with WaitConnections"
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
        3.0,
        "--min-duration",
        help="Min wait duration in seconds (default: 3)",
    ),
    hosts: Optional[str] = typer.Option(
        None, help="Optional comma-separated host names"
    ),
    database: Optional[str] = typer.Option(
        None, "--database", help="Optional ProcessName / IB filter"
    ),
    file_like: Optional[str] = typer.Option(
        None,
        "--file-like",
        help="ClickHouse only: optional file LIKE pattern, e.g. %tlock_1607235%",
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
    platform_version: str = typer.Option(
        "8.3.25",
        "--platform-version",
        help="1C platform version (default 8.3.25+ keeps format=json compress=zip)",
    ),
    location_path: str = typer.Option(
        "!!!ПУТЬ!!!",
        "--location-path",
        help=r"Path for TJ logs in logcfg (replaces !!!ПУТЬ!!!), e.g. D:\TJ\locks",
    ),
    template: Optional[str] = typer.Option(
        None,
        "--template",
        help="Path to logcfg template XML (default: bundled logcfg_шаблон.xml)",
    ),
    report_dir: Optional[str] = typer.Option(
        None,
        "--report-dir",
        help="Write logcfg.xml into report directory (same layout as analyzers)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output logcfg.xml file path (required without --report-dir)",
    ),
):
    """Collect unique TLOCK regions and generate logcfg for lock problem monitoring."""
    if ctx.invoked_subcommand is not None:
        return

    if not output and not report_dir:
        raise typer.BadParameter("Specify --output or --report-dir")

    apply_mcp_clickhouse_env()

    filters = build_filters(
        log_id, time_from, time_to, min_duration, hosts, database, source, file_like
    )

    if source == SourceType.click:
        log_source = build_clickhouse_source(
            clickhouse_host,
            clickhouse_port,
            clickhouse_user,
            clickhouse_password,
            clickhouse_db,
            victim_table="tj_tlock",
            victim_event="TLOCK",
        )
    else:
        log_source = build_file_source(source, file, base_date, victim_event="TLOCK")

    victims = log_source.fetch_victims(filters)
    region_stats = collect_region_stats(victims)

    if not region_stats:
        console.print(
            "[yellow]No TLOCK events with WaitConnections, non-empty regions "
            f"and duration >= {min_duration}s found.[/yellow]"
        )
        raise typer.Exit(code=1)

    if template:
        template_text = load_template(Path(template))
    else:
        template_text = load_default_template()

    if report_dir:
        directory = resolve_report_dir(
            report_dir,
            log_ids=parse_csv(log_id),
            database=database,
            analyzer="tlock_logcfg",
        )
        out_path = write_logcfg_report(
            directory,
            victims,
            location_path=location_path,
            platform_version=platform_version,
            template=template_text,
        )
        assert out_path is not None
    else:
        xml_body = _build_logcfg(
            template_text,
            location_path=location_path,
            region_stats=region_stats,
            platform_version=platform_version,
        )
        assert output is not None
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(xml_body, encoding="utf-8")
        out_path = output.resolve()

    json_zip = platform_supports_json_zip(platform_version)
    console.print(
        f"[green]Victims analyzed: {len(victims)}[/green] "
        f"[dim](min duration >= {min_duration}s)[/dim]"
    )
    console.print(f"[green]Unique regions: {len(region_stats)}[/green]")
    console.print(
        f"[dim]Platform {platform_version}: "
        f"{'format=json compress=zip kept' if json_zip else 'format/compress removed (<= 8.3.24)'}[/dim]"
    )

    table = Table(title="TLOCK regions (WaitConnections)")
    table.add_column("Regions", style="cyan")
    table.add_column("Количество", justify="right")
    table.add_column("Среднее, с", justify="right")
    table.add_column("Макс., с", justify="right")
    for item in region_stats:
        table.add_row(
            item.region,
            str(item.count),
            str(item.avg_wait_sec),
            str(item.max_wait_sec),
        )
    console.print(table)

    console.print(f"[green]logcfg written:[/green] {out_path}")


def app_entry():
    app()


if __name__ == "__main__":
    app()
