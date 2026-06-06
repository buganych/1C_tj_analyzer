"""Aggregate victim/blocking contexts and wait regions for summary tables."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from tj_common.analysis.unified_pipeline import UnifiedAnalysisResult
from tj_common.models import AnalysisResult, CulpritAnalysis
from tj_common.report.event_report import (
    _conflict_tlock_rows,
    format_space_label,
    normalize_context,
)

SUMMARY_TOP_N = 10


@dataclass
class RankedItem:
    label: str
    count: int


@dataclass
class SummaryTables:
    victim_contexts: list[RankedItem] = field(default_factory=list)
    blocking_contexts: list[RankedItem] = field(default_factory=list)
    wait_regions: list[RankedItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, int | str]]]:
        def pack(items: list[RankedItem]) -> list[dict[str, int | str]]:
            return [{"label": i.label, "count": i.count} for i in items]

        return {
            "victim_contexts": pack(self.victim_contexts),
            "blocking_contexts": pack(self.blocking_contexts),
            "wait_regions": pack(self.wait_regions),
        }


def context_label(context: str) -> str:
    """Last non-empty context line — typical grouping key in TJ reports."""
    body = normalize_context(context)
    if not body:
        return ""
    lines = body.splitlines()
    return lines[-1].strip().strip("'")


def _regions_list(regions: str) -> list[str]:
    raw = format_space_label(regions)
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _culprit_blocking_rows(culprit: CulpritAnalysis):
    rows = _conflict_tlock_rows(culprit)
    if rows:
        return rows
    return list(culprit.tx_tlocks_all or [])


def _collect_from_analysis(
    analysis: AnalysisResult | None,
    victim_ctx: Counter,
    blocking_ctx: Counter,
    regions: Counter,
) -> None:
    if not analysis:
        return
    for victim in analysis.victims:
        label = context_label(victim.event.context)
        if label:
            victim_ctx[label] += 1
        for region in _regions_list(victim.event.regions):
            regions[region] += 1
        for culprit in victim.culprits:
            for row in _culprit_blocking_rows(culprit):
                block_label = context_label(row.context)
                if block_label:
                    blocking_ctx[block_label] += 1


def _to_ranked(counter: Counter) -> list[RankedItem]:
    return [
        RankedItem(label, count)
        for label, count in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    ]


def collect_summary_tables(result: UnifiedAnalysisResult) -> SummaryTables:
    victim_ctx: Counter = Counter()
    blocking_ctx: Counter = Counter()
    regions: Counter = Counter()

    _collect_from_analysis(result.tlock, victim_ctx, blocking_ctx, regions)
    _collect_from_analysis(result.ttimeout, victim_ctx, blocking_ctx, regions)

    return SummaryTables(
        victim_contexts=_to_ranked(victim_ctx),
        blocking_contexts=_to_ranked(blocking_ctx),
        wait_regions=_to_ranked(regions),
    )
