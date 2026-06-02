"""Unified analyzer smoke tests."""

import json
from datetime import datetime, timedelta

from tj_common.analysis.unified_pipeline import AnalyzerKind, run_unified_analysis
from tj_common.models import QueryFilters, TjEvent
from tj_common.models_deadlock import DeadlockQueryFilters, TdeadlockEvent
from tj_common.report.unified import render_unified_json, render_unified_text
from tj_common.sources.deadlock_memory import DeadlockMemorySource
from tj_common.sources.memory import MemoryLogSource

LOG_ID = "u_test"
REGIONS = "InfoRg17707.DIMS"
LOCKS = "InfoRg17707.DIMS Exclusive Fld1=1"
DCI = f"518868 500546 {REGIONS} Exclusive {LOCKS}"


def _memory_sources():
    base = datetime(2026, 5, 27, 10, 54, 35)
    td = TdeadlockEvent(
        ts=base,
        connect_id="518868",
        log_id=LOG_ID,
        deadlock_connection_intersections=DCI,
    )
    events = [
        TjEvent(
            ts=base - timedelta(seconds=20),
            event="SDBL",
            connect_id="518868",
            func="BeginTransaction",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base - timedelta(seconds=10),
            event="TLOCK",
            connect_id="518868",
            wait_connections="500546",
            regions=REGIONS,
            locks=LOCKS,
            log_id=LOG_ID,
        ),
        TjEvent(ts=base, event="TDEADLOCK", connect_id="518868", log_id=LOG_ID),
        TjEvent(
            ts=base + timedelta(seconds=5),
            event="SDBL",
            connect_id="518868",
            func="RollbackTransaction",
            log_id=LOG_ID,
        ),
    ]
    tlock = MemoryLogSource(events, victim_event="TLOCK")
    ttimeout = MemoryLogSource(events, victim_event="TTIMEOUT")
    tdeadlock = DeadlockMemorySource([td], events)
    return tlock, ttimeout, tdeadlock


def test_unified_runs_all_three():
    tlock, ttimeout, tdeadlock = _memory_sources()
    filters = QueryFilters(log_ids=[LOG_ID])
    result = run_unified_analysis(
        kinds=list(AnalyzerKind),
        tlock_source=tlock,
        ttimeout_source=ttimeout,
        tdeadlock_source=tdeadlock,
        tlock_filters=filters,
        ttimeout_filters=filters,
        tdeadlock_filters=DeadlockQueryFilters(log_ids=[LOG_ID]),
    )
    assert result.tlock is not None
    assert result.ttimeout is not None
    assert result.tdeadlock is not None
    payload = json.loads(render_unified_json(result))
    assert payload["analyzer"] == "unified"
    assert "tlock" in payload
    text = render_unified_text(result)
    assert "TLOCK" in text
    assert "TTIMEOUT" in text
    assert "TDEADLOCK" in text


def test_unified_only_tlock():
    tlock, _, _ = _memory_sources()
    result = run_unified_analysis(
        kinds=[AnalyzerKind.tlock],
        tlock_source=tlock,
        tlock_filters=QueryFilters(log_ids=[LOG_ID]),
    )
    assert result.tlock is not None
    assert result.ttimeout is None
    assert "ttimeout" in result.skipped
