"""End-to-end TDEADLOCK pipeline test (in-memory)."""

from datetime import datetime, timedelta

from tj_common.analysis.deadlock_pipeline import run_deadlock_analysis
from tj_common.models import TjEvent
from tj_common.models_deadlock import DeadlockQueryFilters, TdeadlockEvent
from tj_common.sources.deadlock_memory import DeadlockMemorySource

REGIONS = "InfoRg17707.DIMS"
LOCKS = (
    "InfoRg17707.DIMS Exclusive "
    "Fld17708=17552:9e5b0050560133fc11f0458ad37f53ef"
)
LOCKS2 = (
    "InfoRg17707.DIMS Exclusive "
    "Fld17709=80:9e5b0050560133fc11f0468638b41009"
)
LOG_ID = "test_log"
DCI = (
    f"518868 500546 {REGIONS} Exclusive {LOCKS}, "
    f"500546 518868 {REGIONS} Exclusive {LOCKS2}"
)


def _build_scenario() -> DeadlockMemorySource:
    base = datetime(2026, 5, 27, 10, 54, 35)
    tdeadlock = TdeadlockEvent(
        ts=base,
        connect_id="518868",
        session_id="100",
        host="vTerm02",
        process_name="UVI_UTD",
        user="Victim User",
        log_id=LOG_ID,
        deadlock_connection_intersections=DCI,
    )
    events = [
        TjEvent(
            ts=base - timedelta(seconds=30),
            event="SDBL",
            connect_id="500546",
            func="BeginTransaction",
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base - timedelta(seconds=25),
            event="TLOCK",
            connect_id="500546",
            regions=REGIONS,
            locks=LOCKS2,
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base - timedelta(seconds=20),
            event="SDBL",
            connect_id="518868",
            func="BeginTransaction",
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base - timedelta(seconds=15),
            event="TLOCK",
            connect_id="518868",
            regions=REGIONS,
            locks=LOCKS,
            wait_connections="500546",
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base - timedelta(seconds=10),
            event="TLOCK",
            connect_id="500546",
            regions=REGIONS,
            locks=LOCKS2,
            wait_connections="518868",
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base,
            event="TDEADLOCK",
            connect_id="518868",
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base + timedelta(seconds=5),
            event="SDBL",
            connect_id="518868",
            func="RollbackTransaction",
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base + timedelta(seconds=10),
            event="SDBL",
            connect_id="500546",
            func="CommitTransaction",
            host="vTerm02",
            log_id=LOG_ID,
        ),
    ]
    return DeadlockMemorySource([tdeadlock], events)


def test_deadlock_pipeline_memory():
    source = _build_scenario()
    result = run_deadlock_analysis(
        source, DeadlockQueryFilters(log_ids=[LOG_ID])
    )
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.event.connect_id == "518868"
    assert case.status in ("ok", "too_few_events", "incomplete_tx")
    if case.status == "ok":
        assert case.deadlock_type
        assert case.graph_wait_block
        assert case.graph_locks
