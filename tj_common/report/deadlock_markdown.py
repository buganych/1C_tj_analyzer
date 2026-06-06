"""Markdown report for TDEADLOCK analysis."""

from __future__ import annotations

from tj_common.analysis.deadlock import deadlock_context_matrix_columns
from tj_common.models_deadlock import DeadlockAnalysisResult
from tj_common.report.event_report import _md_code_block, _md_table
from tj_common.utils import format_ts


def render_deadlock_markdown(result: DeadlockAnalysisResult) -> str:
    parts: list[str] = ["# Анализ TDEADLOCK", ""]

    for idx, case in enumerate(result.cases, 1):
        ev = case.event
        parts.append(f"## Взаимоблокировка #{idx}")
        parts.append("")
        parts.extend(
            _md_table(
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
                    ["Статус", case.status],
                ],
            )
        )
        parts.append("")
        if ev.context:
            parts.append("**Контекст**")
            parts.extend(_md_code_block(ev.context))
        if case.cross_matrix:
            parts.append("**Граф захвата ресурсов**")
            parts.extend(_md_code_block(case.cross_matrix))
        context_columns = deadlock_context_matrix_columns(case)
        if context_columns and any(
            block or wait for _, block, wait in context_columns
        ):
            titles = [title for title, _, _ in context_columns]
            block_cells = [block or "—" for _, block, _ in context_columns]
            wait_cells = [wait or "—" for _, _, wait in context_columns]
            parts.append("**Граф захвата ресурсов по контекстам**")
            parts.extend(
                _md_table(
                    [""] + titles,
                    [
                        ["Блокировка", *block_cells],
                        ["Ожидание", *wait_cells],
                    ],
                )
            )
            parts.append("")
        if case.timeline_text:
            parts.append("**Хронология**")
            parts.extend(_md_code_block(case.timeline_text[:4000]))

    if result.errors:
        parts.append("## Ошибки")
        parts.append("")
        for err in result.errors:
            parts.append(f"- {err}")

    parts.append("")
    return "\n".join(parts)
