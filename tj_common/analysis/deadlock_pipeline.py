"""TDEADLOCK analysis pipeline."""

from __future__ import annotations

import uuid

from tj_common.analysis.progress import (
    AnalysisProgress,
    ProgressTracker,
    iter_batches,
    should_report_progress,
)
from tj_common.analysis.deadlock import (
    ROLE_P2,
    ROLE_P3,
    ROLE_VICTIM,
    add_tx_events,
    edge_participants,
    filter_participant_waits,
    finalize_case,
    match_conflicting_waits,
    parse_deadlock_intersections,
)
from tj_common.models_deadlock import (
    DeadlockAnalysisResult,
    DeadlockCase,
    DeadlockQueryFilters,
    Participant,
    TimelineEvent,
    TdeadlockEvent,
)
from tj_common.sources.deadlock_base import DeadlockDataSource


def _apply_tx(
    source: DeadlockDataSource,
    participant: Participant,
    event: TdeadlockEvent,
    use_host: bool,
) -> bool:
    bounds = source.transaction_bounds_at(
        participant.connect_id,
        event.ts,
        event.log_id or None,
        event.host if use_host else None,
        event.process_name or None,
    )
    if bounds.error or not bounds.start or not bounds.end:
        return False
    participant.tx_start = bounds.start
    participant.tx_end = bounds.end
    participant.tx_start_ts = bounds.start.strftime("%Y-%m-%d %H:%M:%S.%f")
    participant.tx_end_ts = bounds.end.strftime("%Y-%m-%d %H:%M:%S.%f")
    return True


def _append_wait_timeline(case: DeadlockCase, waits: list, role: str) -> None:
    for w in waits:
        eid = w.event_id or str(uuid.uuid4())
        w.event_id = eid
        case.timeline.append(
            TimelineEvent(
                time=w.ts_str,
                role=role,
                label=w.locks,
                is_wait=w.is_wait,
                event_id=eid,
                wait=w,
            )
        )


def analyze_case(
    source: DeadlockDataSource,
    event: TdeadlockEvent,
    config_catalog: str | None = None,
) -> DeadlockCase:
    dci = event.deadlock_connection_intersections
    edges, tables, p1, p2, p3, count = parse_deadlock_intersections(
        dci, event.connect_id
    )

    case = DeadlockCase(
        event=event,
        participant_count=count,
        victim=p1,
        participant2=p2,
        participant3=p3,
        edges=edges,
        tables=tables,
    )
    case.victim.role = ROLE_VICTIM
    case.participant2.role = ROLE_P2
    if case.participant3:
        case.participant3.role = ROLE_P3

    if not event.context.strip():
        event.context = source.fetch_context(
            event.connect_id,
            event.ts,
            event.host,
            event.log_id or None,
            event.process_name or None,
        )

    ok1 = _apply_tx(source, case.victim, event, use_host=True)
    ok2 = _apply_tx(source, case.participant2, event, use_host=False)
    ok3 = True
    if case.participant3 and case.participant3.connect_id:
        ok3 = _apply_tx(source, case.participant3, event, use_host=False)

    if not (ok1 and ok2 and ok3):
        case.status = "incomplete_tx"
        case.status_detail = "Не найдены границы транзакции одного или более участников"
        return case

    add_tx_events(case, case.victim, ROLE_VICTIM, "Откат транзакции")
    add_tx_events(case, case.participant2, ROLE_P2, "Фиксация транзакции")
    if case.participant3 and case.participant3.connect_id:
        add_tx_events(case, case.participant3, ROLE_P3, "Фиксация транзакции")

    for edge in case.edges:
        victim_p, culprit_p = edge_participants(case, edge)
        raw_waits = source.fetch_participant_tlocks(
            victim_p.connect_id,
            victim_p.tx_start,
            victim_p.tx_end,
            case.tables,
            victim_p.host or event.host,
            event.log_id or None,
            event.process_name or None,
            culprit_p.tx_start,
            culprit_p.connect_id,
        )
        victim_p.waits = filter_participant_waits(
            raw_waits, case.edges, dci, culprit_p.connect_id
        )

    fast_path = (
        case.participant_count == 2
        and len(case.victim.waits) == 2
        and len(case.participant2.waits) == 2
    )

    if fast_path:
        _append_wait_timeline(case, case.victim.waits, ROLE_VICTIM)
        _append_wait_timeline(case, case.participant2.waits, ROLE_P2)
    else:
        for edge in case.edges:
            victim_p, culprit_p = edge_participants(case, edge)
            if not culprit_p.waits:
                culprit_p.waits = filter_participant_waits(
                    source.fetch_participant_tlocks(
                        culprit_p.connect_id,
                        culprit_p.tx_start,
                        culprit_p.tx_end,
                        case.tables,
                        None,
                        event.log_id or None,
                        event.process_name or None,
                        victim_p.tx_start,
                        victim_p.connect_id,
                    ),
                    case.edges,
                    dci,
                    victim_p.connect_id,
                )
            match_conflicting_waits(
                case, victim_p.waits, culprit_p.waits, victim_p.role, culprit_p.role
            )
        if case.participant3 and case.participant3.connect_id:
            if not case.participant2.waits:
                case.participant2.waits = filter_participant_waits(
                    source.fetch_participant_tlocks(
                        case.participant2.connect_id,
                        case.participant2.tx_start,
                        case.participant2.tx_end,
                        case.tables,
                        None,
                        event.log_id or None,
                        event.process_name or None,
                        case.victim.tx_start,
                        case.victim.connect_id,
                    ),
                    case.edges,
                    dci,
                    case.victim.connect_id,
                )
            if not case.participant3.waits:
                case.participant3.waits = filter_participant_waits(
                    source.fetch_participant_tlocks(
                        case.participant3.connect_id,
                        case.participant3.tx_start,
                        case.participant3.tx_end,
                        case.tables,
                        None,
                        event.log_id or None,
                        event.process_name or None,
                        case.participant2.tx_start,
                        case.participant2.connect_id,
                    ),
                    case.edges,
                    dci,
                    case.participant2.connect_id,
                )
            match_conflicting_waits(
                case,
                case.participant2.waits,
                case.participant3.waits,
                ROLE_P2,
                ROLE_P3,
            )
            match_conflicting_waits(
                case,
                case.participant3.waits,
                case.victim.waits,
                ROLE_P3,
                ROLE_VICTIM,
            )

    finalize_case(case)

    if config_catalog:
        from tj_common.config_catalog.resolver import attach_context_trees

        attach_context_trees(case, config_catalog)

    return case


def run_deadlock_analysis(
    source: DeadlockDataSource,
    filters: DeadlockQueryFilters,
    config_catalog: str | None = None,
    *,
    progress: AnalysisProgress | None = None,
) -> DeadlockAnalysisResult:
    events = source.fetch_tdeadlocks(filters)
    result = DeadlockAnalysisResult()
    if not events:
        return result

    tracker: ProgressTracker | None = None
    batch_size = len(events)
    if should_report_progress(len(events), progress):
        assert progress is not None
        batch_size = progress.batch_size
        tracker = ProgressTracker(
            len(events),
            label=progress.label,
            status_interval_sec=progress.status_interval_sec,
            emit=progress.emit,
        )

    for batch in iter_batches(events, batch_size):
        for event in batch:
            try:
                result.cases.append(
                    analyze_case(source, event, config_catalog=config_catalog)
                )
                if tracker:
                    tracker.tick()
            except Exception as exc:
                result.errors.append(f"{event.ts} connect={event.connect_id}: {exc}")
                if tracker:
                    tracker.tick(error=True)

    if tracker:
        tracker.finish()
    return result
