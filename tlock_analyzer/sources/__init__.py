"""Log source adapters."""

from tlock_analyzer.sources.base import LogSource
from tlock_analyzer.sources.clickhouse import ClickHouseSource

__all__ = ["LogSource", "ClickHouseSource"]
