"""Report directory output."""

from datetime import datetime, timedelta

from tj_common.analysis.pipeline import run_analysis
from tj_common.analysis.unified_pipeline import AnalyzerKind, run_unified_analysis
from tj_common.cli_shared import write_unified_analysis_reports, write_victim_analysis_reports
from tj_common.models import QueryFilters, TjEvent
from tj_common.report.json_out import render_json
from tj_common.report.labels import TLOCK_LABELS
from tj_common.report.markdown import render_markdown
from tj_common.report.write import make_report_slug, resolve_report_dir, write_triple_reports
from tj_common.sources.memory import MemoryLogSource

LOG_ID = "report_write_test"
REGIONS = "InfoRg17707.DIMS"
LOCKS = "InfoRg17707.DIMS Exclusive Fld1=1"


def _memory_source() -> MemoryLogSource:
    base = datetime(2026, 5, 27, 10, 54, 35)
    return MemoryLogSource(
        [
            TjEvent(
                ts=base - timedelta(seconds=5),
                event="TLOCK",
                connect_id="500546",
                regions=REGIONS,
                locks=LOCKS,
                context="CULPRIT",
                log_id=LOG_ID,
            ),
            TjEvent(
                ts=base,
                event="TLOCK",
                connect_id="518868",
                wait_connections="500546",
                regions=REGIONS,
                locks=LOCKS,
                duration_us=1_000_000,
                context="VICTIM",
                log_id=LOG_ID,
            ),
        ]
    )


def test_write_triple_reports(tmp_path):
    paths = write_triple_reports(
        tmp_path,
        json_body='{"ok": true}',
        md_body="# Report",
        html_body="<html><body>ok</body></html>",
    )
    assert paths["json"].read_text(encoding="utf-8") == '{"ok": true}'
    assert paths["md"].read_text(encoding="utf-8") == "# Report"
    assert "ok" in paths["html"].read_text(encoding="utf-8")


def test_resolve_report_dir_auto_slug(tmp_path):
    directory = resolve_report_dir(
        str(tmp_path / "reports"),
        log_ids=[LOG_ID],
        database="ex_burm_lock",
        analyzer="tj_analyzer",
    )
    assert directory.parent.name == "reports"
    assert LOG_ID in directory.name
    assert directory.exists()


def test_make_report_slug_sanitizes():
    slug = make_report_slug(["tele/trade logs"], "ex burm", "tj_analyzer")
    assert "/" not in slug
    assert " " not in slug


def test_write_victim_analysis_reports(tmp_path):
    result = run_analysis(_memory_source(), QueryFilters(log_ids=[LOG_ID]))
    paths = write_victim_analysis_reports(
        str(tmp_path),
        result,
        render_json=render_json,
        render_markdown=render_markdown,
        labels=TLOCK_LABELS,
        log_ids=[LOG_ID],
    )
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert paths["html"].exists()
    assert "TLOCK" in paths["md"].read_text(encoding="utf-8")
    assert "<html" in paths["html"].read_text(encoding="utf-8")


def test_write_unified_analysis_reports(tmp_path):
    source = _memory_source()
    unified = run_unified_analysis(
        kinds=[AnalyzerKind.tlock],
        tlock_source=source,
        tlock_filters=QueryFilters(log_ids=[LOG_ID]),
    )
    paths = write_unified_analysis_reports(
        str(tmp_path),
        unified,
        log_ids=[LOG_ID],
    )
    assert '"analyzer": "unified"' in paths["json"].read_text(encoding="utf-8")
    assert "Сводный анализ" in paths["md"].read_text(encoding="utf-8")
    assert "Оглавление" in paths["html"].read_text(encoding="utf-8")
