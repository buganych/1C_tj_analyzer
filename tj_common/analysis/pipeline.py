"""Main TLOCK analysis pipeline."""

from __future__ import annotations

from tj_common.analysis.locks import (
    DIFFERENT_DIMENSIONS,
    ESCALATION,
    FULL_MATCH,
    check_full_match_strings,
    locks_conflict,
    parse_lock_properties,
)
from tj_common.models import (
    AnalysisResult,
    CulpritAnalysis,
    QueryFilters,
    TjEvent,
    VictimAnalysis,
)
from tj_common.sources.base import LogSource
from tj_common.utils import event_to_dict, wait_start_ts

BIG_TX_LIMIT = 2001


def _parse_culprit_ids(wait_connections: str) -> list[str]:
    return [
        c.strip().replace("'", "")
        for c in wait_connections.split(",")
        if c.strip()
    ]


def _ensure_context(
    source: LogSource,
    event: TjEvent,
    hosts: list[str] | None,
) -> None:
    if not event.context.strip():
        event.context = source.fetch_context(
            event.connect_id, event.ts, log_id=event.log_id or None, hosts=hosts
        )


def _analyze_culprit_tlocks(
    victim: TjEvent,
    culprit_id: str,
    tlocks: list[TjEvent],
    source: LogSource,
    hosts: list[str] | None,
) -> CulpritAnalysis:
    analysis = CulpritAnalysis(connect_id=culprit_id)
    victim_props = parse_lock_properties(victim.regions, victim.locks)
    event_lines: list[str] = []

    if len(tlocks) >= BIG_TX_LIMIT:
        seen_contexts: set[str] = set()
        for ev in tlocks:
            if ev.context in seen_contexts:
                continue
            seen_contexts.add(ev.context)
            analysis.big_transaction.append(event_to_dict(ev))
        return analysis

    for ev in tlocks:
        _ensure_context(source, ev, hosts)
        line = (
            f"@timestamp={ev.ts},event={ev.event},connect_id={ev.connect_id},"
            f"Regions={ev.regions},Locks={ev.locks},Context={ev.context}"
        )
        event_lines.append(line)

        if check_full_match_strings(victim.locks, ev.locks):
            conflict_type = FULL_MATCH
            has_conflict = True
        else:
            culprit_props = parse_lock_properties(ev.regions, ev.locks)
            result = locks_conflict(
                victim_props, culprit_props, culprit_escalating=ev.escalating
            )
            has_conflict = result.has_conflict
            conflict_type = result.conflict_type

        if not has_conflict or not conflict_type:
            continue

        data = event_to_dict(ev)
        if conflict_type == FULL_MATCH:
            analysis.full_match.append(data)
        elif conflict_type == ESCALATION:
            analysis.escalation.append(data)
        elif conflict_type == DIFFERENT_DIMENSIONS:
            analysis.different_dimensions.append(data)

    if not (
        analysis.full_match
        or analysis.escalation
        or analysis.different_dimensions
    ):
        analysis.transaction_events = "\n".join(event_lines)

    return analysis


def analyze_victim(
    source: LogSource,
    victim: TjEvent,
    hosts: list[str] | None = None,
) -> VictimAnalysis:
    result = VictimAnalysis(event=victim)
    _ensure_context(source, victim, hosts)

    ref_ts = wait_start_ts(victim.ts, victim.duration_us)
    culprit_ids = _parse_culprit_ids(victim.wait_connections)
    if not culprit_ids:
        result.parse_error = "Empty WaitConnections"
        return result

    log_id = victim.log_id or None

    for culprit_id in culprit_ids:
        bounds = source.find_transaction_bounds(
            culprit_id, ref_ts, log_id=log_id, hosts=hosts, neighbor_tx=False
        )
        if bounds.error:
            bounds = source.find_transaction_bounds(
                culprit_id, ref_ts, log_id=log_id, hosts=hosts, neighbor_tx=True
            )

        culprit = CulpritAnalysis(connect_id=culprit_id)
        if bounds.error:
            culprit.error = bounds.error
            result.culprits.append(culprit)
            continue

        culprit.tx_start = bounds.start
        culprit.tx_end = bounds.end
        if bounds.start and bounds.end:
            culprit.tx_duration_us = int(
                (bounds.end - bounds.start).total_seconds() * 1_000_000
            )

        tlocks = source.fetch_culprit_tlocks(
            culprit_id,
            bounds.start,
            bounds.end,
            victim.regions,
            victim.ts,
            log_id=log_id,
            hosts=hosts,
        )
        culprit = _analyze_culprit_tlocks(
            victim, culprit_id, tlocks, source, hosts
        )
        culprit.tx_start = bounds.start
        culprit.tx_end = bounds.end
        result.culprits.append(culprit)

    return result


def run_analysis(source: LogSource, filters: QueryFilters) -> AnalysisResult:
    victims = source.fetch_victims(filters)
    result = AnalysisResult()
    for victim in victims:
        try:
            result.victims.append(
                analyze_victim(source, victim, filters.hosts)
            )
        except Exception as exc:
            result.errors.append(
                f"{victim.ts} connect={victim.connect_id} log_id={victim.log_id}: {exc}"
            )
    return result
