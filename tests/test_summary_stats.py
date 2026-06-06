"""Summary aggregate tables for unified reports."""

import json
from datetime import datetime, timedelta

from tj_common.analysis.pipeline import run_analysis
from tj_common.analysis.unified_pipeline import UnifiedAnalysisResult
from tj_common.models import QueryFilters, TjEvent
from tj_common.report.html import render_unified_html
from tj_common.report.summary_render import (
    render_summary_tables_markdown,
    render_summary_tables_text,
)
from tj_common.report.summary_stats import (
    SUMMARY_TOP_N,
    RankedItem,
    collect_summary_tables,
    context_label,
)
from tj_common.report.unified import render_unified_json, render_unified_markdown
from tj_common.sources.memory import MemoryLogSource

LOG_ID = "summary_test"
REGIONS_A = "InfoRg17707.DIMS"
REGIONS_B = "InfoRg99999.DIMS"
LOCKS = "InfoRg17707.DIMS Exclusive Fld1=1"


def _scenario() -> MemoryLogSource:
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
            regions=REGIONS_A,
            locks=LOCKS,
            context="ОбщийМодуль.Блокировка.Модуль\nCULPRIT_CTX",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base,
            event="TLOCK",
            connect_id="518868",
            wait_connections="500546",
            regions=REGIONS_A,
            locks=LOCKS,
            duration_us=1_000_000,
            context="ОбщийМодуль.Жертва.Модуль\nVICTIM_CTX",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base + timedelta(seconds=1),
            event="TLOCK",
            connect_id="518869",
            wait_connections="500546",
            regions=REGIONS_B,
            locks=LOCKS,
            duration_us=500_000,
            context="ОбщийМодуль.Жертва.Модуль\nVICTIM_CTX",
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
    return MemoryLogSource(events)


def test_context_label_strips_quotes():
    assert context_label("'Форма.Вызов : Модуль.Процедура'") == "Форма.Вызов : Модуль.Процедура"
    assert context_label("'первая строка\nВторая : 123 : Метод();'") == "Вторая : 123 : Метод();"


def test_collect_summary_tables_counts():
    result = run_analysis(_scenario(), QueryFilters(log_ids=[LOG_ID]))
    tables = collect_summary_tables(UnifiedAnalysisResult(tlock=result))

    assert [(i.label, i.count) for i in tables.victim_contexts] == [("VICTIM_CTX", 2)]
    assert [(i.label, i.count) for i in tables.blocking_contexts] == [("CULPRIT_CTX", 2)]
    assert [(i.label, i.count) for i in tables.wait_regions] == [
        (REGIONS_A, 1),
        (REGIONS_B, 1),
    ]


def test_summary_tables_in_unified_outputs():
    result = run_analysis(_scenario(), QueryFilters(log_ids=[LOG_ID]))
    unified = UnifiedAnalysisResult(tlock=result)

    md = render_unified_markdown(unified)
    assert "### Ожидающие контексты" in md
    assert "### Блокирующие контексты" in md
    assert "### Таблицы на которых были ожидания" in md
    assert "| VICTIM_CTX | 2 |" in md
    assert "| CULPRIT_CTX | 2 |" in md

    payload = json.loads(render_unified_json(unified))
    assert payload["summary"]["tables"]["victim_contexts"][0] == {
        "label": "VICTIM_CTX",
        "count": 2,
    }

    text = render_summary_tables_text(collect_summary_tables(unified))
    assert "Ожидающие контексты" in "\n".join(text)
    assert "VICTIM_CTX" in "\n".join(text)


def test_summary_tables_collapse_when_more_than_ten():
    from tj_common.report.html import _HtmlBuilder
    from tj_common.report.summary_render import render_summary_tables_html
    from tj_common.report.summary_stats import SummaryTables

    items = [RankedItem(f"CTX_{i}", 100 - i) for i in range(15)]
    tables = SummaryTables(victim_contexts=items)

    md = "\n".join(render_summary_tables_markdown(tables))
    visible_md = md.split("<details>", 1)[0]
    assert visible_md.count("| CTX_") == SUMMARY_TOP_N
    assert "<details>" in md
    assert f"<summary>Ещё {len(items) - SUMMARY_TOP_N}</summary>" in md

    b = _HtmlBuilder()
    render_summary_tables_html(b, tables)
    html_out = b.render_document("test")
    assert html_out.count("CTX_0") == 1
    assert 'class="summary-more"' in html_out
    assert "<summary>Ещё 5</summary>" in html_out

    page = render_unified_html(UnifiedAnalysisResult())
    assert "Ожидающие контексты" in page
    assert "(нет данных)" in page
