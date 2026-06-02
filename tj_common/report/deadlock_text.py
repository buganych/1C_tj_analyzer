"""Text report for TDEADLOCK analysis."""

from __future__ import annotations

from tj_common.models_deadlock import DeadlockAnalysisResult


def render_deadlock_text(result: DeadlockAnalysisResult) -> str:
    parts: list[str] = []
    parts.append("=" * 60)
    parts.append("Анализ TDEADLOCK")
    parts.append("=" * 60)

    for idx, case in enumerate(result.cases, 1):
        ev = case.event
        parts.append("")
        parts.append(f"--- Взаимоблокировка #{idx} [{case.status}] ---")
        parts.append(f"id: {case.case_id}")
        parts.append(f"Время: {ev.ts}")
        if ev.log_id:
            parts.append(f"log_id: {ev.log_id}")
        parts.append(f"Соединение (жертва): {ev.connect_id}")
        parts.append(f"Сеанс: {ev.session_id}")
        parts.append(f"Виновники: {case.culprit_connect_ids}")
        parts.append(f"Хост: {ev.host}")
        parts.append(f"База: {ev.process_name}")
        parts.append(f"Пользователь: {ev.user}")

        if case.status_detail:
            parts.append(f"Примечание: {case.status_detail}")

        if case.deadlock_type:
            parts.append("")
            parts.append(case.text_graph)

        if case.cross_matrix:
            parts.append("")
            parts.append("Граф захвата ресурсов:")
            parts.append(case.cross_matrix)

        if case.timeline_text:
            parts.append("")
            parts.append(case.timeline_text[:4000])

    if result.errors:
        parts.append("")
        parts.append("--- Ошибки ---")
        parts.extend(result.errors)

    return "\n".join(parts)
