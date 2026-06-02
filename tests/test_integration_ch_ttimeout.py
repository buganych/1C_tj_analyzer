"""Optional integration test against live ClickHouse (tj_ttimeout)."""

import os

import pytest

from tj_common.models import QueryFilters
from tj_common.sources.clickhouse import ClickHouseSource
from ttimeout_analyzer.pipeline import run_analysis


@pytest.mark.integration
def test_clickhouse_ttimeout_victims_by_log_id():
    password = os.environ.get("CLICKHOUSE_PASSWORD")
    if not password:
        pytest.skip("CLICKHOUSE_PASSWORD not set")

    ch = ClickHouseSource(
        host=os.environ.get("CLICKHOUSE_HOST", "192.168.40.51"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "18123")),
        password=password,
        database=os.environ.get("CLICKHOUSE_DATABASE", "onec_logs"),
        victim_table="tj_ttimeout",
        victim_event="TTIMEOUT",
    )

    log_ids = os.environ.get("CLICKHOUSE_TEST_LOG_ID", "teletrade_tj_logs").split(",")
    filters = QueryFilters(log_ids=[x.strip() for x in log_ids if x.strip()])

    result = run_analysis(ch, filters)
    assert isinstance(result.victims, list)
