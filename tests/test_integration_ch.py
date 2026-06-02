"""Optional integration test against live ClickHouse."""

import os

import pytest

from tlock_analyzer.analysis.pipeline import run_analysis
from tlock_analyzer.models import QueryFilters
from tlock_analyzer.sources.clickhouse import ClickHouseSource


@pytest.mark.integration
def test_clickhouse_victims_by_log_id():
    password = os.environ.get("CLICKHOUSE_PASSWORD")
    if not password:
        pytest.skip("CLICKHOUSE_PASSWORD not set")

    ch = ClickHouseSource(
        host=os.environ.get("CLICKHOUSE_HOST", "192.168.40.51"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "18123")),
        password=password,
        database=os.environ.get("CLICKHOUSE_DATABASE", "onec_logs"),
    )

    log_ids = os.environ.get("CLICKHOUSE_TEST_LOG_ID", "teletrade_tj_logs").split(",")
    filters = QueryFilters(log_ids=[x.strip() for x in log_ids if x.strip()])

    result = run_analysis(ch, filters)
    assert isinstance(result.victims, list)
