"""Unresolved locks and recommended logcfg sections in reports."""

from datetime import datetime, timedelta

from tj_common.analysis.pipeline import run_analysis
from tj_common.models import AnalysisResult, QueryFilters, TjEvent, UnresolvedLock, VictimAnalysis
from tj_common.report.html import render_event_html
from tj_common.report.json_out import analysis_to_dict
from tj_common.report.markdown import render_markdown
from tj_common.report.text import render_text
from tj_common.report.unresolved import collect_unresolved_locks
from tj_common.sources.memory import MemoryLogSource

LOG_ID = "unresolved_test"
REGIONS = "InfoRg10053.DIMS"


def _tx_error_scenario() -> MemoryLogSource:
    base = datetime(2026, 6, 4, 12, 0, 0)
    events = [
        TjEvent(
            ts=base,
            event="TLOCK",
            connect_id="675289",
            wait_connections="674241",
            regions=REGIONS,
            locks=f"{REGIONS} Exclusive",
            duration_us=20_000_000,
            log_id=LOG_ID,
        ),
    ]
    return MemoryLogSource(events)


def test_collect_unresolved_from_culprit_tx_error():
    result = run_analysis(_tx_error_scenario(), QueryFilters(log_ids=[LOG_ID]))
    unresolved = collect_unresolved_locks(result)
    assert len(unresolved) == 1
    assert unresolved[0].regions == REGIONS
    assert "674241" in unresolved[0].reason
    assert "транзакции" in unresolved[0].reason.lower()


def test_reports_include_collapsible_unresolved_sections():
    result = run_analysis(_tx_error_scenario(), QueryFilters(log_ids=[LOG_ID]))
    md = render_markdown(result)
    text = render_text(result)
    html = render_event_html(result)
    data = analysis_to_dict(result)

    assert "<details>" in md
    assert "Неразобранные блокировки" in md
    assert "Рекомендуемая настройка logcfg" in md
    assert REGIONS in md
    assert "Причина неудачи" in md or "Виновник" in md

    assert "Неразобранные блокировки" in text
    assert "Рекомендуемая настройка logcfg" in text
    assert REGIONS in text

    assert 'class="report-section"' in html
    assert "Неразобранные блокировки" in html
    assert "Рекомендуемая настройка logcfg" in html
    assert REGIONS in html

    assert data["unresolved"]
    assert data["recommended_logcfg_snippet"]
    assert REGIONS in data["recommended_logcfg_snippet"]


def test_successful_analysis_has_no_unresolved_sections():
    base = datetime(2026, 5, 27, 10, 54, 35)
    events = [
        TjEvent(
            ts=base - timedelta(seconds=30),
            event="SDBL",
            connect_id="500546",
            func="BeginTransaction",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base - timedelta(seconds=5),
            event="TLOCK",
            connect_id="500546",
            regions=REGIONS,
            locks=f"{REGIONS} Exclusive",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base,
            event="TLOCK",
            connect_id="518868",
            wait_connections="500546",
            regions=REGIONS,
            locks=f"{REGIONS} Exclusive",
            duration_us=1_000_000,
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base + timedelta(seconds=10),
            event="SDBL",
            connect_id="500546",
            func="CommitTransaction",
            log_id=LOG_ID,
        ),
    ]
    result = run_analysis(MemoryLogSource(events), QueryFilters(log_ids=[LOG_ID]))
    assert not collect_unresolved_locks(result)
    md = render_markdown(result)
    html = render_event_html(result)
    assert "Неразобранные блокировки" not in md
    assert "Рекомендуемая настройка logcfg" in md
    assert "<details hidden>" in md
    assert "Рекомендуемая настройка logcfg" in html
    assert 'class="report-section" hidden' in html


def test_parse_error_appears_in_unresolved_table():
    ev = TjEvent(
        ts=datetime(2026, 6, 4, 12, 0, 0),
        event="TLOCK",
        connect_id="1",
        wait_connections="",
        regions=REGIONS,
        duration_us=5_000_000,
    )
    result = AnalysisResult(
        victims=[VictimAnalysis(event=ev, parse_error="Empty WaitConnections")]
    )
    unresolved = collect_unresolved_locks(result)
    assert len(unresolved) == 1
    assert unresolved[0].reason == "Empty WaitConnections"
    md = render_markdown(result)
    assert "Empty WaitConnections" in md


def test_pipeline_exception_populates_unresolved():
    ev = TjEvent(
        ts=datetime(2026, 6, 4, 12, 0, 0),
        event="TLOCK",
        connect_id="1",
        wait_connections="2",
        regions=REGIONS,
        duration_us=4_000_000,
    )

    class BrokenSource(MemoryLogSource):
        def find_transaction_bounds(self, *args, **kwargs):
            raise RuntimeError("boom")

    result = run_analysis(BrokenSource([ev]), QueryFilters())
    assert result.errors
    assert result.unresolved
    assert "boom" in result.unresolved[0].reason
