"""Human-readable report (ЗаполнитьСводнаяИнформацияClick style)."""

from __future__ import annotations

from tj_common.models import AnalysisResult, CulpritAnalysis
from tj_common.report.labels import ReportLabels, TLOCK_LABELS
from tj_common.utils import format_ts

SECTION_FULL = "ПОЛНОЕ СООТВЕТСТВИЕ"
SECTION_ESC = "ЭСКАЛАЦИЯ"
SECTION_DIFF = "РАЗНЫЙ НАБОР ИЗМЕРЕНИЙ"
SECTION_BIG = "БОЛЬШАЯ ТРАНЗАКЦИЯ"


def _tx_interval(c: CulpritAnalysis) -> str:
    if not c.tx_start or not c.tx_end:
        return "—"
    dur = ""
    if c.tx_duration_us:
        dur = f" ({c.tx_duration_us / 1_000_000:.2f} сек.)"
    return (
        f"{format_ts(c.tx_start)} — {format_ts(c.tx_end)}{dur}"
    )


def _format_conflict_block(title: str, items: list[dict]) -> list[str]:
    lines = [f"--- {title} ---"]
    template = (
        "Пространство = {Regions}\n"
        "Блокировка = {Locks}\n"
        "Длительность(сек) = {dur}\n"
        "timestamp = {ts}\n"
        "Пользователь = {Usr}\n"
        "Номер соединения = {ConnectID}\n"
        "Контекст = {Context}"
    )
    for d in items:
        dur = float(d.get("Duration", 0) or 0) / 1_000_000
        lines.append(
            template.format(
                Regions=d.get("Regions", ""),
                Locks=str(d.get("Locks", "")).replace(",", ",\n             "),
                dur=dur,
                ts=d.get("Timestamp", ""),
                Usr=d.get("Usr", ""),
                ConnectID=d.get("ConnectID", ""),
                Context=d.get("Context", ""),
            )
        )
        lines.append("")
    return lines


def render_text(
    result: AnalysisResult, labels: ReportLabels = TLOCK_LABELS
) -> str:
    parts: list[str] = []
    parts.append("=" * 60)
    parts.append(labels.title)
    parts.append("=" * 60)

    for idx, victim in enumerate(result.victims, 1):
        ev = victim.event
        parts.append("")
        parts.append(f"--- Жертва #{idx} ---")
        parts.append(f"Время: {format_ts(ev.ts)}")
        if ev.log_id:
            parts.append(f"log_id: {ev.log_id}")
        parts.append(f"Соединение: {ev.connect_id}")
        parts.append(f"Ждали: {ev.wait_connections}")
        parts.append(f"Пользователь: {ev.user}")
        parts.append(f"Хост: {ev.host}")
        parts.append(f"База: {ev.process_name}")
        parts.append(f"Длительность(сек): {ev.duration_sec:.6f}")
        parts.append(f"Пространство: {ev.regions}")
        parts.append(f"Блокировка: {ev.locks}")
        parts.append(f"Контекст: {ev.context[:500]}{'...' if len(ev.context) > 500 else ''}")

        if victim.parse_error:
            parts.append(f"Ошибка: {victim.parse_error}")
            continue

        for c in victim.culprits:
            parts.append("")
            parts.append(f"  Виновник connect_id={c.connect_id}")
            parts.append(f"  Транзакция: {_tx_interval(c)}")
            if c.error:
                parts.append(f"  Ошибка: {c.error}")
                continue
            if c.full_match:
                parts.extend(_format_conflict_block(SECTION_FULL, c.full_match))
            if c.escalation:
                parts.extend(_format_conflict_block(SECTION_ESC, c.escalation))
            if c.different_dimensions:
                parts.extend(_format_conflict_block(SECTION_DIFF, c.different_dimensions))
            if c.big_transaction:
                parts.extend(_format_conflict_block(SECTION_BIG, c.big_transaction))
            if c.transaction_events and not (
                c.full_match or c.escalation or c.different_dimensions or c.big_transaction
            ):
                parts.append("  События транзакции (конфликт не классифицирован):")
                parts.append(c.transaction_events[:2000])

    if result.errors:
        parts.append("")
        parts.append("--- Ошибки обработки ---")
        parts.extend(result.errors)

    return "\n".join(parts)
