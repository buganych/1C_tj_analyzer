"""End-to-end TTIMEOUT pipeline tests with in-memory events."""

from datetime import datetime, timedelta

from tj_common.models import QueryFilters, TjEvent
from tj_common.sources.memory import MemoryLogSource
from ttimeout_analyzer.pipeline import run_analysis

REGIONS = "InfoRg17707.DIMS"
LOCKS = (
    "InfoRg17707.DIMS Exclusive "
    "Fld17708=17552:9e5b0050560133fc11f0458ad37f53ef "
    "Fld17709=80:9e5b0050560133fc11f0468638b41009 "
    "Fld17710=393:c62745a3cb8472d9dca8babafb232a78"
)
LOG_ID = "test_log"


def _build_scenario() -> MemoryLogSource:
    base = datetime(2026, 5, 27, 10, 54, 35)
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
            ts=base - timedelta(seconds=5),
            event="TLOCK",
            connect_id="500546",
            regions=REGIONS,
            locks=LOCKS,
            host="vTerm02",
            log_id=LOG_ID,
        ),
        TjEvent(
            ts=base,
            event="TTIMEOUT",
            connect_id="518868",
            wait_connections="500546",
            regions=REGIONS,
            locks=LOCKS,
            duration_us=10_000_000,
            host="vTerm02",
            process_name="UVI_UTD",
            user="Test User",
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
    return MemoryLogSource(events, victim_event="TTIMEOUT")


def test_ttimeout_pipeline_finds_full_match_by_log_id():
    source = _build_scenario()
    filters = QueryFilters(log_ids=[LOG_ID])
    result = run_analysis(source, filters)
    assert len(result.victims) == 1
    victim = result.victims[0]
    assert victim.event.event == "TTIMEOUT"
    assert victim.event.connect_id == "518868"
    assert len(victim.culprits) == 1
    culprit = victim.culprits[0]
    assert culprit.connect_id == "500546"
    assert culprit.tx_start is not None
    assert len(culprit.full_match) >= 1 or len(culprit.different_dimensions) >= 1
