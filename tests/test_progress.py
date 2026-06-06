"""Progress reporting for batched victim analysis."""

from datetime import datetime, timedelta

from tj_common.analysis.pipeline import run_analysis
from tj_common.analysis.progress import (
    AnalysisProgress,
    ProgressTracker,
    iter_batches,
    should_report_progress,
)
from tj_common.models import QueryFilters, TjEvent
from tj_common.sources.memory import MemoryLogSource

LOG_ID = "progress_test"


def _many_victims(count: int) -> MemoryLogSource:
    base = datetime(2026, 6, 4, 2, 0, 0)
    events = []
    for i in range(count):
        events.append(
            TjEvent(
                ts=base + timedelta(seconds=i),
                event="TLOCK",
                connect_id=f"v{i}",
                wait_connections="999",
                regions="InfoRg10053.DIMS",
                duration_us=20_000_000,
                log_id=LOG_ID,
            )
        )
    return MemoryLogSource(events)


def test_iter_batches_splits_list():
    assert list(iter_batches([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_should_report_progress_threshold():
    progress = AnalysisProgress(min_items=10)
    assert not should_report_progress(9, progress)
    assert should_report_progress(10, progress)
    assert not should_report_progress(100, None)


def test_progress_tracker_emits_on_tick_and_finish():
    messages: list[str] = []
    tracker = ProgressTracker(
        3,
        label="TLOCK",
        status_interval_sec=0.0,
        emit=messages.append,
    )
    tracker.tick()
    tracker.tick(error=True)
    tracker.tick()
    tracker.finish()
    assert messages[0] == "[TLOCK] обработано 0 / 3, осталось 3"
    assert messages[-1] == "[TLOCK] обработано 3 / 3, осталось 0, ошибок 1"


def test_run_analysis_reports_progress_for_large_sets():
    messages: list[str] = []
    progress = AnalysisProgress(
        label="TLOCK",
        batch_size=7,
        status_interval_sec=0.0,
        min_items=5,
        emit=messages.append,
    )
    result = run_analysis(_many_victims(12), QueryFilters(), progress=progress)
    assert len(result.victims) == 12
    assert messages
    assert "обработано" in messages[-1]
    assert "12 / 12" in messages[-1]


def test_run_analysis_skips_progress_for_small_sets():
    messages: list[str] = []
    progress = AnalysisProgress(label="TLOCK", emit=messages.append, min_items=10)
    run_analysis(_many_victims(3), QueryFilters(), progress=progress)
    assert messages == []
