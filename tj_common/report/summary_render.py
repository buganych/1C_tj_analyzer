"""Render summary aggregate tables for text, markdown, and HTML."""

from __future__ import annotations

import html

from tj_common.report.event_report import _md_table
from tj_common.report.summary_stats import SUMMARY_TOP_N, RankedItem, SummaryTables


def _split_items(items: list[RankedItem]) -> tuple[list[RankedItem], list[RankedItem]]:
    return items[:SUMMARY_TOP_N], items[SUMMARY_TOP_N:]


def render_summary_tables_markdown(tables: SummaryTables) -> list[str]:
    parts: list[str] = []
    parts.extend(
        _ranked_markdown(
            "Ожидающие контексты",
            "Контекст жертвы",
            tables.victim_contexts,
        )
    )
    parts.extend(
        _ranked_markdown(
            "Блокирующие контексты",
            "Контекст",
            tables.blocking_contexts,
        )
    )
    parts.extend(
        _ranked_markdown(
            "Таблицы на которых были ожидания",
            "Пространство",
            tables.wait_regions,
        )
    )
    return parts


def _ranked_markdown(title: str, label_header: str, items: list[RankedItem]) -> list[str]:
    lines = [f"### {title}", ""]
    if not items:
        lines.extend(["*(нет данных)*", ""])
        return lines
    visible, hidden = _split_items(items)
    lines.extend(
        _md_table(
            [label_header, "Количество"],
            [[item.label, str(item.count)] for item in visible],
        )
    )
    if hidden:
        lines.append("<details>")
        lines.append(f"<summary>Ещё {len(hidden)}</summary>")
        lines.append("")
        lines.extend(
            _md_table(
                [label_header, "Количество"],
                [[item.label, str(item.count)] for item in hidden],
            )
        )
        lines.append("</details>")
    lines.append("")
    return lines


def render_summary_tables_text(tables: SummaryTables) -> list[str]:
    parts: list[str] = []
    parts.extend(
        _ranked_text(
            "Ожидающие контексты",
            "Контекст жертвы",
            tables.victim_contexts,
        )
    )
    parts.extend(
        _ranked_text(
            "Блокирующие контексты",
            "Контекст",
            tables.blocking_contexts,
        )
    )
    parts.extend(
        _ranked_text(
            "Таблицы на которых были ожидания",
            "Пространство",
            tables.wait_regions,
        )
    )
    return parts


def _ranked_text(title: str, label_header: str, items: list[RankedItem]) -> list[str]:
    from tj_common.report.text import _plain_table

    lines = [title, "-" * len(title)]
    if not items:
        lines.extend(["(нет данных)", ""])
        return lines
    visible, hidden = _split_items(items)
    lines.extend(
        _plain_table(
            [label_header, "Количество"],
            [[item.label, str(item.count)] for item in visible],
        )
    )
    if hidden:
        lines.append(f"  ... ещё {len(hidden)} (см. HTML/Markdown)")
    lines.append("")
    return lines


def render_summary_tables_html(builder, tables: SummaryTables) -> None:
    builder.raw('<div class="summary-grid">')
    _ranked_html(
        builder,
        "Ожидающие контексты",
        "Контекст жертвы",
        tables.victim_contexts,
    )
    _ranked_html(
        builder,
        "Блокирующие контексты",
        "Контекст",
        tables.blocking_contexts,
    )
    _ranked_html(
        builder,
        "Таблицы на которых были ожидания",
        "Пространство",
        tables.wait_regions,
    )
    builder.raw("</div>")


def _ranked_html(builder, title: str, label_header: str, items: list[RankedItem]) -> None:
    builder.raw('<div class="summary-card">')
    builder.raw(f"<h3>{html.escape(title)}</h3>")
    if not items:
        builder.paragraph("(нет данных)", css_class="muted")
        builder.raw("</div>")
        return
    visible, hidden = _split_items(items)
    builder.table(
        [label_header, "Количество"],
        [[item.label, str(item.count)] for item in visible],
        css_class="compact-table count-col-last",
    )
    if hidden:
        builder.raw('<details class="summary-more">')
        builder.raw(f"<summary>Ещё {len(hidden)}</summary>")
        builder.table(
            [label_header, "Количество"],
            [[item.label, str(item.count)] for item in hidden],
            css_class="compact-table count-col-last",
        )
        builder.raw("</details>")
    builder.raw("</div>")
