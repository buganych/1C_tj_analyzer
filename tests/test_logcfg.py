"""Tests for tlock_logcfg generator."""

from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tj_common.models import QueryFilters, TjEvent
from tj_common.sources.memory import MemoryLogSource
from tj_common.logcfg import (
    RegionStats,
    build_logcfg,
    collect_region_stats,
    load_template,
    platform_supports_json_zip,
)

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns="http://v8.1c.ru/v8/tech-log">
  <dump create="true" location="!!!ПУТЬ!!!\\Dump" type="3"/>
  <log location="!!!ПУТЬ!!!\\locks_problems" history="8" format="json" compress="zip">
    <event>
      <eq property="name" value="SCALL"/>
      <eq property="MName" value="onBeginTransaction"/>
    </event>
    <event>
      <eq property="name" value="TLOCK"/>
      <eq property="regions" value="<regions>"/>
    </event>
    <property name="all"/>
  </log>
</config>
"""


def _victim(regions: str, wait: str = "500546", duration_us: int = 1_000_000) -> TjEvent:
    return TjEvent(
        ts=datetime(2026, 5, 27, 10, 0, 0),
        event="TLOCK",
        connect_id="518868",
        wait_connections=wait,
        regions=regions,
        duration_us=duration_us,
    )


def test_collect_region_stats_sorted_and_skips_empty():
    victims = [
        _victim("InfoRg17707.DIMS", duration_us=1_000_000),
        _victim("InfoRg17707.DIMS", duration_us=3_000_000),
        _victim("AccumRg10479.DIMS", duration_us=500_000),
        _victim(""),
    ]
    assert collect_region_stats(victims) == [
        RegionStats("InfoRg17707.DIMS", 2, 2, 3),
        RegionStats("AccumRg10479.DIMS", 1, 0, 0),
    ]


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("8.3.24", False),
        ("8.3.24.1500", False),
        ("8.3.23.1000", False),
        ("8.3.25", True),
        ("8.3.25.1000", True),
    ],
)
def test_platform_supports_json_zip(version, expected):
    assert platform_supports_json_zip(version) is expected


def test_build_logcfg_replaces_path_and_regions():
    region_stats = [
        RegionStats("InfoRg17707.DIMS", 5, 2, 10),
        RegionStats("AccumRg10479.DIMS", 2, 1, 3),
    ]
    xml = build_logcfg(
        TEMPLATE,
        location_path=r"D:\TJ\locks",
        region_stats=region_stats,
        platform_version="8.3.25",
    )
    assert r'location="D:\TJ\locks\locks_problems"' in xml
    assert r'location="D:\TJ\locks\Dump"' in xml
    assert 'value="InfoRg17707.DIMS"' in xml
    assert (
        "<!-- Количество = 5, среднее ожидание = 2, максимальное ожидание = 10 -->"
        in xml
    )
    assert (
        "<!-- Количество = 2, среднее ожидание = 1, максимальное ожидание = 3 -->"
        in xml
    )
    assert 'format="json" compress="zip"' in xml
    assert 'value="<regions>"' not in xml


def test_build_logcfg_removes_json_zip_for_old_platform():
    xml = build_logcfg(
        TEMPLATE,
        location_path=r"C:\TJ",
        region_stats=[RegionStats("InfoRg17707.DIMS", 1, 1, 1)],
        platform_version="8.3.24",
    )
    assert 'format="json"' not in xml
    assert 'compress="zip"' not in xml
    assert 'history="8"' in xml


def test_fetch_victims_min_duration_filter():
    events = [
        _victim("InfoRg17707.DIMS", duration_us=2_000_000),
        _victim("InfoRg17707.DIMS", duration_us=4_000_000),
        _victim("AccumRg10479.DIMS", duration_us=3_500_000),
    ]
    source = MemoryLogSource(events)
    victims = source.fetch_victims(QueryFilters(min_duration_us=3_000_000))
    region_stats = collect_region_stats(victims)
    assert len(victims) == 2
    assert region_stats == [
        RegionStats("AccumRg10479.DIMS", 1, 4, 4),
        RegionStats("InfoRg17707.DIMS", 1, 4, 4),
    ]


def test_memory_source_integration():
    events = [
        _victim("InfoRg17707.DIMS", duration_us=3_000_000),
        TjEvent(
            ts=datetime(2026, 5, 27, 10, 1, 0),
            event="TLOCK",
            connect_id="500546",
            regions="InfoRg17707.DIMS",
        ),
    ]
    source = MemoryLogSource(events)
    victims = source.fetch_victims(QueryFilters())
    region_stats = collect_region_stats(victims)
    xml = build_logcfg(
        TEMPLATE,
        location_path=r"E:\logs",
        region_stats=region_stats,
        platform_version="8.3.24",
    )
    assert "InfoRg17707.DIMS" in xml
    assert "среднее ожидание = 3" in xml
    assert 'format="json"' not in xml


def test_cli_min_duration_default_is_3_seconds(tmp_path):
    from tlock_logcfg.cli import app

    tj = tmp_path / "tj.log"
    tj.write_text(
        "10:00:00.000000-2000000,TLOCK,2,\n"
        "WaitConnections=500546\n"
        "regions=InfoRg17707.DIMS\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.xml"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--source",
            "plain",
            "--file",
            str(tj),
            "--base-date",
            "2026-05-27",
            "--location-path",
            r"D:\TJ",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert "duration >= 3" in result.output


def test_cli_output_or_report_dir_required():
    from tlock_logcfg.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--source",
            "plain",
            "--file",
            "missing.log",
        ],
    )
    assert result.exit_code != 0
    assert "--output" in result.output or "--report-dir" in result.output


def test_bundled_template_loads():
    root = Path(__file__).resolve().parents[1]
    template = load_template(root / "logcfg_шаблон.xml")
    xml = build_logcfg(
        template,
        location_path=r"X:\TJ",
        region_stats=[RegionStats("AccumRg10479.DIMS", 3, 5, 12)],
        platform_version="8.3.27",
    )
    assert "AccumRg10479.DIMS" in xml
    assert "максимальное ожидание = 12" in xml
    assert 'format="json" compress="zip"' in xml
