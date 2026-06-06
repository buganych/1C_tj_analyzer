"""HTML report with table of contents and anchor links."""

from __future__ import annotations

import html
import re
from typing import Any

from tj_common.analysis.deadlock import deadlock_context_matrix_columns
from tj_common.analysis.unified_pipeline import UnifiedAnalysisResult
from tj_common.models import AnalysisResult, CulpritAnalysis, CulpritTlockRow, VictimAnalysis
from tj_common.models_deadlock import DeadlockAnalysisResult, TimelineEvent
from tj_common.report.event_report import (
    VICTIM_TABLE_HEADERS,
    _conflict_tlock_rows,
    _tx_duration_sec,
    _victim_detail_row,
    format_lock_resources,
    format_space_label,
    normalize_context,
)
from tj_common.report.labels import ReportLabels, TLOCK_LABELS, TTIMEOUT_LABELS
from tj_common.report.summary_render import render_summary_tables_html
from tj_common.report.summary_stats import collect_summary_tables
from tj_common.report.unresolved import (
    render_logcfg_section_html,
    render_unresolved_sections_html,
    render_unresolved_table_html,
)
from tj_common.utils import format_ts

_HTML_STYLES = """
:root {
  --bg: #f6f8fa;
  --card: #ffffff;
  --text: #1f2328;
  --muted: #656d76;
  --border: #d0d7de;
  --accent: #0969da;
  --code-bg: #eff1f3;
  --toc-bg: #f0f4f8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  color: var(--text);
  background: var(--bg);
}
.layout {
  max-width: min(1400px, 100%);
  margin: 0 auto;
  padding: 24px 20px 48px;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
body.toc-collapsed .layout {
  max-width: 100%;
  grid-template-columns: auto minmax(0, 1fr);
  padding-left: 16px;
  padding-right: 16px;
}
body.toc-collapsed .toc-aside { display: none; }
.sidebar {
  position: sticky;
  top: 16px;
  align-self: start;
  min-width: 0;
}
.toc-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  min-width: 36px;
  margin: 0 0 12px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--toc-bg);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
}
.toc-toggle-icon {
  display: block;
  width: 16px;
  height: 16px;
}
.toc-toggle:hover { border-color: var(--accent); color: var(--accent); }
.toc-aside { min-width: 0; }
@media (max-width: 900px) {
  body:not(.toc-collapsed) .layout { grid-template-columns: minmax(0, 1fr); }
  body:not(.toc-collapsed) .sidebar { order: -1; }
  nav.toc { position: static; }
}
nav.toc {
  position: sticky;
  top: 16px;
  background: var(--toc-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}
nav.toc h2 {
  margin: 0 0 12px;
  font-size: 15px;
}
nav.toc ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
nav.toc li { margin: 4px 0; }
nav.toc a {
  color: var(--accent);
  text-decoration: none;
}
nav.toc a:hover { text-decoration: underline; }
nav.toc .lvl-1 { font-weight: 600; margin-top: 8px; }
nav.toc .lvl-2 { padding-left: 12px; }
nav.toc .lvl-3 { padding-left: 24px; font-size: 13px; }
main.content {
  min-width: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 24px 28px;
}
h1 { font-size: 22px; margin: 0 0 16px; }
h2 { font-size: 18px; margin: 28px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
h3 { font-size: 16px; margin: 20px 0 10px; }
h4 { font-size: 14px; margin: 16px 0 8px; color: var(--muted); }
.meta-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 20px;
}
.meta-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.3;
}
.meta-label { color: var(--muted); }
.meta-value { font-weight: 600; color: var(--text); }
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 0 0 20px;
}
@media (max-width: 700px) {
  .stat-grid { grid-template-columns: 1fr; }
}
.stat-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
  background: linear-gradient(180deg, #fafbfc 0%, #fff 100%);
}
.stat-card .stat-num {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
  margin-bottom: 4px;
}
.stat-card .stat-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.stat-card .stat-hint {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
}
.stat-tlock .stat-num { color: #0969da; }
.stat-ttimeout .stat-num { color: #bc4c00; }
.stat-tdeadlock .stat-num { color: #8250df; }
.summary-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 8px 0 20px;
  width: 100%;
}
.summary-card {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px 10px;
  background: #fafbfc;
}
.summary-card h3 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.table-fit {
  display: block;
  width: fit-content;
  max-width: 100%;
  overflow-x: auto;
}
.summary-card table {
  margin: 0;
  background: #fff;
  border-radius: 6px;
  overflow: hidden;
}
.summary-card table td:first-child {
  word-break: break-word;
  font-size: 12px;
}
.summary-card .muted { margin: 0; font-size: 12px; }
table {
  border-collapse: collapse;
  margin: 8px 0 16px;
  font-size: 13px;
}
table:not(.compact-table):not(.tlock-table):not(.timeline-table):not(.deadlock-context-matrix) {
  width: 100%;
}
table.compact-table {
  width: fit-content;
  max-width: 100%;
  table-layout: auto;
}
table.compact-table td:first-child,
table.compact-table th:first-child {
  word-break: break-word;
}
table.compact-table.count-col-last td:last-child,
table.compact-table.count-col-last th:last-child {
  width: 1px;
  white-space: nowrap;
  text-align: right;
  padding-left: 16px;
  font-weight: 600;
  color: var(--accent);
}
table.compact-table.field-col-first td:first-child,
table.compact-table.field-col-first th:first-child {
  width: 1px;
  white-space: nowrap;
  vertical-align: top;
  color: var(--muted);
}
th, td {
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}
th { background: #f6f8fa; }
pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.context-label { font-weight: 600; margin: 12px 0 4px; }
.muted { color: var(--muted); font-style: italic; }
hr.section { border: none; border-top: 2px solid var(--border); margin: 32px 0; }
table.tlock-table tr.tlock-data td { border-bottom: none; }
table.tlock-table tr.tlock-extra td,
table.tlock-table tr.tlock-context td {
  padding: 0 8px 8px;
  border-top: none;
  background: #fafbfc;
}
table.tlock-table tr.tlock-extra td { padding-bottom: 0; }
table.tlock-table details { margin: 0; }
table.tlock-table summary {
  cursor: pointer;
  color: var(--accent);
  font-size: 12px;
  padding: 4px 0;
  user-select: none;
}
table.tlock-table summary:hover { text-decoration: underline; }
table.tlock-table details pre {
  margin: 6px 0 0;
  font-size: 12px;
}
table.timeline-table tr.timeline-data td { border-bottom: none; }
table.timeline-table tr.timeline-extra td,
table.timeline-table tr.timeline-context td {
  padding: 0 8px 8px;
  border-top: none;
  background: #fafbfc;
}
table.timeline-table tr.timeline-extra td {
  font-size: 12px;
  color: var(--muted);
  padding-top: 2px;
}
table.timeline-table details { margin: 0; }
table.timeline-table summary {
  cursor: pointer;
  color: var(--accent);
  font-size: 12px;
  padding: 4px 0;
  user-select: none;
}
table.timeline-table summary:hover { text-decoration: underline; }
table.timeline-table details pre {
  margin: 6px 0 0;
  font-size: 12px;
}
details.summary-more { margin: 8px 0 16px; }
details.summary-more summary {
  cursor: pointer;
  color: var(--accent);
  font-size: 13px;
  padding: 4px 0;
  user-select: none;
}
details.summary-more summary:hover { text-decoration: underline; }
details.summary-more { margin-top: 8px; }
details.report-section {
  margin: 16px 0 24px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  background: #fafbfc;
}
details.report-section summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 15px;
  padding: 4px 0;
  user-select: none;
  color: var(--text);
}
details.report-section summary:hover { color: var(--accent); }
details.report-section > table,
details.report-section > .table-fit,
details.report-section > p,
details.report-section > pre {
  margin-top: 12px;
}
table.deadlock-context-matrix {
  margin: 8px 0 16px;
}
table.deadlock-context-matrix th {
  text-align: center;
  font-size: 13px;
  background: #eef2f7;
}
table.deadlock-context-matrix td {
  font-size: 12px;
  word-break: break-word;
  vertical-align: top;
  background: #fafbfc;
}
table.deadlock-context-matrix td.kind {
  width: 96px;
  font-weight: 600;
  color: var(--muted);
  background: #eef2f7;
  white-space: nowrap;
}
"""

_META_LABELS: dict[str, str] = {
    "Source": "Источник",
    "log_id": "Log ID",
    "period": "Период",
    "hosts": "Хосты",
    "database": "База",
    "file_like": "Файл",
    "min_duration": "Мин. ожидание",
}

_SOURCE_LABELS: dict[str, str] = {
    "click": "ClickHouse",
    "plain": "Файл ТЖ",
    "json": "JSON",
}

_META_ORDER = (
    "Source",
    "log_id",
    "database",
    "period",
    "hosts",
    "file_like",
    "min_duration",
)


def _parse_meta_pairs(meta: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for section in meta.split("|"):
        for token in section.split():
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            key = key.strip()
            if key and key not in seen:
                seen.add(key)
                pairs.append((key, value.strip()))
    return pairs


def format_meta_html(meta: str) -> str:
    if not meta or "=" not in meta:
        return ""
    badges: list[str] = []
    pairs = dict(_parse_meta_pairs(meta))
    for key in _META_ORDER:
        if key not in pairs:
            continue
        value = pairs[key]
        if key == "Source":
            value = _SOURCE_LABELS.get(value, value)
        label = _META_LABELS.get(key, key)
        badges.append(
            '<span class="meta-badge">'
            f'<span class="meta-label">{html.escape(label)}</span>'
            f'<span class="meta-value">{html.escape(value)}</span>'
            "</span>"
        )
    for key, value in pairs.items():
        if key in _META_ORDER:
            continue
        label = _META_LABELS.get(key, key)
        badges.append(
            '<span class="meta-badge">'
            f'<span class="meta-label">{html.escape(label)}</span>'
            f'<span class="meta-value">{html.escape(value)}</span>'
            "</span>"
        )
    if not badges:
        return ""
    return f'<div class="meta-bar">{"".join(badges)}</div>'


def _render_summary_stats_html(b: "_HtmlBuilder", summary: dict[str, Any]) -> None:
    b.raw('<div class="stat-grid">')
    for css, num_key, label, hint in (
        ("stat-tlock", "tlock_victims", "TLOCK", "ожидания"),
        ("stat-ttimeout", "ttimeout_victims", "TTIMEOUT", "таймауты"),
        ("stat-tdeadlock", "tdeadlock_cases", "TDEADLOCK", "взаимоблокировки"),
    ):
        b.raw(
            f'<div class="stat-card {css}">'
            f'<div class="stat-num">{summary[num_key]}</div>'
            f'<div class="stat-label">{label}</div>'
            f'<div class="stat-hint">{hint}</div>'
            "</div>"
        )
    b.raw("</div>")


def _normalize_timeline_time(time_str: str) -> str:
    return time_str.replace("T", " ", 1) if "T" in time_str else time_str


def _timeline_event_label(ev: TimelineEvent) -> str:
    if ev.wait:
        return "Ожидание" if ev.is_wait else "Блокировка"
    return ev.label


def _details_block(summary: str, body: str) -> str:
    if body:
        return (
            f"<details><summary>{html.escape(summary)}</summary>"
            f"<pre><code>{html.escape(body)}</code></pre></details>"
        )
    return '<span class="muted">(пусто)</span>'


def _context_details_html(context: str) -> str:
    return _details_block("Контекст", normalize_context(context))


def _resources_details_html(regions: str, locks: str) -> str:
    return _details_block("Ресурсы", format_lock_resources(regions, locks))


def _slug(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[`*]", "", s)
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s, flags=re.UNICODE)
    return s.strip("-") or "section"


class _HtmlBuilder:
    def __init__(self) -> None:
        self._toc: list[tuple[int, str, str]] = []
        self._chunks: list[str] = []
        self._ids: dict[str, int] = {}

    def _unique_id(self, text: str) -> str:
        base = _slug(text)
        count = self._ids.get(base, 0)
        self._ids[base] = count + 1
        return base if count == 0 else f"{base}-{count + 1}"

    def heading(self, level: int, text: str, *, toc: bool = True, toc_level: int | None = None) -> str:
        hid = self._unique_id(text)
        if toc:
            self._toc.append((toc_level or level, hid, text))
        self._chunks.append(f"<h{level} id=\"{hid}\">{html.escape(text)}</h{level}>")
        return hid

    def raw(self, fragment: str) -> None:
        self._chunks.append(fragment)

    def paragraph(self, text: str, *, css_class: str = "") -> None:
        cls = f' class="{css_class}"' if css_class else ""
        self._chunks.append(f"<p{cls}>{html.escape(text)}</p>")

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        *,
        css_class: str = "",
    ) -> None:
        head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        body_rows = []
        for row in rows:
            cells = "".join(f"<td>{html.escape(str(c))}</td>" for c in row)
            body_rows.append(f"<tr>{cells}</tr>")
        cls = f' class="{css_class}"' if css_class else ""
        table_html = (
            f"<table{cls}><thead><tr>"
            + head
            + "</tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table>"
        )
        if "compact-table" in css_class:
            table_html = f'<div class="table-fit">{table_html}</div>'
        self._chunks.append(table_html)

    def tlock_table(
        self,
        headers: list[str],
        rows: list[tuple[list[str], str, str, str]],
    ) -> None:
        """Culprit TLOCK table: data row + expandable resources and context."""
        col_count = len(headers)
        head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        body_rows: list[str] = []
        for cells, regions, locks, context in rows:
            data_cells = "".join(f"<td>{html.escape(str(c))}</td>" for c in cells)
            body_rows.append(f'<tr class="tlock-data">{data_cells}</tr>')
            body_rows.append(
                f'<tr class="tlock-extra"><td colspan="{col_count}">'
                f"{_resources_details_html(regions, locks)}</td></tr>"
            )
            body_rows.append(
                f'<tr class="tlock-context"><td colspan="{col_count}">'
                f"{_context_details_html(context)}</td></tr>"
            )
        self._chunks.append(
            '<table class="tlock-table"><thead><tr>'
            + head
            + "</tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table>"
        )

    def code_block(self, text: str) -> None:
        body = normalize_context(text)
        if not body:
            self.raw('<p class="muted">(пусто)</p>')
            return
        self._chunks.append(f"<pre><code>{html.escape(body)}</code></pre>")

    def context_section(self, title: str, text: str) -> None:
        self.raw(f'<p class="context-label">{html.escape(title)}</p>')
        self.code_block(text)

    def deadlock_context_matrix(self, columns: list[tuple[str, str, str]]) -> None:
        if not columns:
            return
        titles = [title for title, _, _ in columns]
        block_cells = [block or "—" for _, block, _ in columns]
        wait_cells = [wait or "—" for _, _, wait in columns]
        head = "".join(f"<th>{html.escape(title)}</th>" for title in titles)
        block_row = '<td class="kind">Блокировка</td>' + "".join(
            f"<td>{html.escape(cell)}</td>" for cell in block_cells
        )
        wait_row = '<td class="kind">Ожидание</td>' + "".join(
            f"<td>{html.escape(cell)}</td>" for cell in wait_cells
        )
        self.raw(
            '<table class="deadlock-context-matrix"><thead><tr><th></th>'
            + head
            + "</tr></thead><tbody><tr>"
            + block_row
            + "</tr><tr>"
            + wait_row
            + "</tr></tbody></table>"
        )

    def deadlock_timeline_table(self, events: list[TimelineEvent]) -> None:
        headers = ["Время", "Участник", "Событие"]
        col_count = len(headers)
        head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        body_rows: list[str] = []
        for ev in events:
            cells = "".join(
                f"<td>{html.escape(str(c))}</td>"
                for c in (
                    _normalize_timeline_time(ev.time),
                    ev.role,
                    _timeline_event_label(ev),
                )
            )
            body_rows.append(f'<tr class="timeline-data">{cells}</tr>')
            if ev.wait:
                space = f"{ev.wait.regions} {ev.wait.level}".strip()
                body_rows.append(
                    f'<tr class="timeline-extra"><td colspan="{col_count}">'
                    f"Пространство: {html.escape(space)}</td></tr>"
                )
                body_rows.append(
                    f'<tr class="timeline-context"><td colspan="{col_count}">'
                    f"{_context_details_html(ev.wait.context or '')}</td></tr>"
                )
        self._chunks.append(
            '<table class="timeline-table"><thead><tr>'
            + head
            + "</tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table>"
        )

    def tlock_context_sections(self, rows: list[CulpritTlockRow]) -> None:
        seen: set[tuple[str, str]] = set()
        for row in rows:
            body = normalize_context(row.context)
            if not body:
                continue
            key = (format_ts(row.timestamp), body)
            if key in seen:
                continue
            seen.add(key)
            self.context_section(f"Контекст TLOCK {format_ts(row.timestamp)}", body)

    def render_document(self, title: str, meta: str = "") -> str:
        toc_items = []
        for lvl, hid, label in self._toc:
            toc_items.append(
                f'<li class="lvl-{lvl}"><a href="#{hid}">{html.escape(label)}</a></li>'
            )
        meta_html = format_meta_html(meta)
        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{_HTML_STYLES}</style>
</head>
<body>
  <div class="layout">
    <div class="sidebar">
      <button type="button" class="toc-toggle" aria-expanded="true" aria-label="Скрыть оглавление" title="Скрыть оглавление" onclick="toggleToc(this)"><span class="toc-toggle-icon" aria-hidden="true"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3 5 8l5 5"/><path d="M7 3 2 8l5 5"/></svg></span></button>
      <aside class="toc-aside">
        <nav class="toc">
          <h2>Оглавление</h2>
          <ul>
            {''.join(toc_items)}
          </ul>
        </nav>
      </aside>
    </div>
    <main class="content">
      <h1>{html.escape(title)}</h1>
      {meta_html}
      {''.join(self._chunks)}
    </main>
  </div>
  <script>
  const TOC_ICON_COLLAPSE = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3 5 8l5 5"/><path d="M7 3 2 8l5 5"/></svg>';
  const TOC_ICON_EXPAND = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3l5 5-5 5"/><path d="M9 3l5 5-5 5"/></svg>';
  function toggleToc(btn) {{
    document.body.classList.toggle('toc-collapsed');
    const collapsed = document.body.classList.contains('toc-collapsed');
    const icon = btn.querySelector('.toc-toggle-icon');
    if (icon) icon.innerHTML = collapsed ? TOC_ICON_EXPAND : TOC_ICON_COLLAPSE;
    const label = collapsed ? 'Показать оглавление' : 'Скрыть оглавление';
    btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', label);
  }}
  </script>
</body>
</html>"""


def _format_culprit_html(b: _HtmlBuilder, c: CulpritAnalysis) -> None:
    b.heading(3, f"Виновник connect_id={c.connect_id}", toc_level=3)
    if c.error:
        b.paragraph(f"Ошибка: {c.error}")
        return

    start = c.tx_start_boundary
    b.heading(4, "Начало транзакции", toc=False)
    if start and start.timestamp:
        b.table(["Время"], [[format_ts(start.timestamp)]], css_class="compact-table")
    elif c.tx_start:
        b.paragraph(format_ts(c.tx_start))

    conflict_rows = _conflict_tlock_rows(c)
    b.heading(4, "TLOCK с пересечением", toc=False)
    if conflict_rows:
        b.tlock_table(
            ["Время", "Длительность (сек)", "Тип", "Пространство"],
            [
                (
                    [
                        format_ts(r.timestamp),
                        f"{r.duration_sec:.6f}",
                        r.conflict_type or "",
                        format_space_label(r.regions),
                    ],
                    r.regions,
                    r.locks,
                    r.context,
                )
                for r in conflict_rows
            ],
        )
    elif c.big_transaction:
        b.paragraph(
            f"Большая транзакция: >2000 событий, уникальных контекстов: {len(c.big_transaction)}",
            css_class="muted",
        )
    else:
        b.paragraph("Пересечений нет — все TLOCK в периоде транзакции", css_class="muted")
        b.heading(4, "Все TLOCK в транзакции", toc=False)
        if c.tx_tlocks_all:
            b.tlock_table(
                ["Время", "Длительность (сек)", "Пространство"],
                [
                    (
                        [
                            format_ts(r.timestamp),
                            f"{r.duration_sec:.6f}",
                            format_space_label(r.regions),
                        ],
                        r.regions,
                        r.locks,
                        r.context,
                    )
                    for r in c.tx_tlocks_all
                ],
            )
        else:
            b.paragraph("Нет TLOCK в транзакции", css_class="muted")

    end = c.tx_end_boundary
    dur = _tx_duration_sec(c)
    dur_s = f"{dur:.6f}" if dur is not None else "—"
    b.heading(4, "Конец транзакции", toc=False)
    if end and end.timestamp:
        b.table(
            ["Время", "Длительность транзакции (сек)"],
            [[format_ts(end.timestamp), dur_s]],
            css_class="compact-table",
        )
    elif c.tx_end:
        b.table(
            ["Время", "Длительность транзакции (сек)"],
            [[format_ts(c.tx_end), dur_s]],
            css_class="compact-table",
        )


def _render_victim_html(b: _HtmlBuilder, victim: VictimAnalysis, idx: int) -> None:
    b.heading(2, f"Событие #{idx}", toc_level=2)
    b.heading(3, "Жертва", toc=False)
    b.tlock_table([*VICTIM_TABLE_HEADERS], [_victim_detail_row(victim)])
    if victim.parse_error:
        b.paragraph(f"Ошибка: {victim.parse_error}")
        return
    for c in victim.culprits:
        _format_culprit_html(b, c)


def render_event_html(
    result: AnalysisResult,
    labels: ReportLabels = TLOCK_LABELS,
    *,
    doc_title: str | None = None,
    meta: str = "",
    include_logcfg_section: bool = True,
) -> str:
    b = _HtmlBuilder()
    section_title = labels.title
    b.heading(2, section_title, toc_level=1)
    for idx, victim in enumerate(result.victims, 1):
        _render_victim_html(b, victim, idx)
    render_unresolved_table_html(b, result)
    if include_logcfg_section:
        render_logcfg_section_html(b, result)
    title = doc_title or section_title
    return b.render_document(title, meta=meta)


def _render_deadlock_html(b: _HtmlBuilder, result: DeadlockAnalysisResult) -> None:
    b.heading(2, "Анализ TDEADLOCK", toc_level=1)
    for idx, case in enumerate(result.cases, 1):
        ev = case.event
        b.heading(2, f"Взаимоблокировка #{idx}", toc_level=2)
        b.table(
            ["Поле", "Значение"],
            [
                ["Время", format_ts(ev.ts)],
                ["Жертва (connect)", ev.connect_id],
                ["Сеанс", ev.session_id],
                ["Участник 2", case.culprit_connect_ids],
                ["Хост", ev.host],
                ["База", ev.process_name],
                ["Пользователь", ev.user],
                ["Тип", case.deadlock_type or ""],
            ],
            css_class="compact-table field-col-first",
        )
        b.context_section("Контекст", ev.context)
        if case.cross_matrix:
            b.context_section("Граф захвата ресурсов", case.cross_matrix)
        context_columns = deadlock_context_matrix_columns(case)
        if context_columns and any(
            block or wait for _, block, wait in context_columns
        ):
            b.raw('<p class="context-label">Граф захвата ресурсов по контекстам</p>')
            b.deadlock_context_matrix(context_columns)
        if case.timeline:
            b.raw('<p class="context-label">Хронология</p>')
            b.deadlock_timeline_table(case.timeline)
        elif case.timeline_text:
            b.context_section("Хронология", case.timeline_text)


def render_unified_html(
    result: UnifiedAnalysisResult,
    *,
    doc_title: str = "Сводный анализ проблем блокировок 1С",
    meta: str = "",
) -> str:
    s = result.summary
    b = _HtmlBuilder()
    b.heading(2, "Сводка", toc_level=1)
    _render_summary_stats_html(b, s)
    render_summary_tables_html(b, collect_summary_tables(result))
    if result.tlock is not None:
        render_unresolved_table_html(b, result.tlock)
        render_logcfg_section_html(b, result.tlock)
    if result.tlock and result.tlock.victims:
        b.raw('<hr class="section">')
        b.heading(2, TLOCK_LABELS.title, toc_level=1)
        for idx, victim in enumerate(result.tlock.victims, 1):
            _render_victim_html(b, victim, idx)
    if result.ttimeout and result.ttimeout.victims:
        b.raw('<hr class="section">')
        b.heading(2, TTIMEOUT_LABELS.title, toc_level=1)
        for idx, victim in enumerate(result.ttimeout.victims, 1):
            _render_victim_html(b, victim, idx)
    if result.tdeadlock and result.tdeadlock.cases:
        b.raw('<hr class="section">')
        _render_deadlock_html(b, result.tdeadlock)
    return b.render_document(doc_title, meta=meta)
