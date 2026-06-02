"""Report titles for victim event type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportLabels:
    title: str
    victim_kind: str
    json_event_type: str


TLOCK_LABELS = ReportLabels(
    title="Анализ TLOCK",
    victim_kind="ожидание TLOCK",
    json_event_type="TLOCK",
)

TTIMEOUT_LABELS = ReportLabels(
    title="Анализ TTIMEOUT",
    victim_kind="таймаут",
    json_event_type="TTIMEOUT",
)
