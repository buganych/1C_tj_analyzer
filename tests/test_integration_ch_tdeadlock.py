"""Optional integration test against live ClickHouse (tj_tdeadlock)."""

import os

import pytest

from tj_common.analysis.deadlock_pipeline import run_deadlock_analysis
from tj_common.models_deadlock import DeadlockQueryFilters
from tj_common.sources.deadlock_clickhouse import DeadlockClickHouseSource


@pytest.mark.integration
def test_clickhouse_tdeadlock_by_log_id():
    password = os.environ.get("CLICKHOUSE_PASSWORD")
    if not password:
        pytest.skip("CLICKHOUSE_PASSWORD not set")

    ch = DeadlockClickHouseSource(
        host=os.environ.get("CLICKHOUSE_HOST", "192.168.40.51"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "18123")),
        password=password,
        database=os.environ.get("CLICKHOUSE_DATABASE", "onec_logs"),
    )

    log_ids = os.environ.get("CLICKHOUSE_TEST_LOG_ID", "teletrade_tj_logs").split(",")
    filters = DeadlockQueryFilters(
        log_ids=[x.strip() for x in log_ids if x.strip()],
        time_from=None,
        time_to=None,
    )

    result = run_deadlock_analysis(ch, filters)
    assert isinstance(result.cases, list)
