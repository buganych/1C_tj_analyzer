"""Shared utilities."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from dateutil import parser as date_parser


def parse_datetime(value: str) -> datetime:
    return date_parser.parse(value)


def host_variants(hosts: list[str] | None) -> list[str]:
    """1C uses lower/upper host names in queries."""
    if not hosts:
        return []
    result: list[str] = []
    for h in hosts:
        result.append(h)
        result.append(h.lower())
        result.append(h.upper())
    return list(dict.fromkeys(result))


def wait_start_ts(victim_ts: datetime, duration_us: int) -> datetime:
    """Moment when wait began: victim_ts - duration (BSL logic)."""
    total_us = int(victim_ts.timestamp() * 1_000_000) - duration_us
    if total_us < 0:
        return victim_ts - timedelta(seconds=duration_us / 1_000_000)
    sec, us = divmod(total_us, 1_000_000)
    return datetime.fromtimestamp(sec).replace(microsecond=us)


def format_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


from tj_common.models import TjEvent


def event_to_dict(event: Any) -> dict[str, Any]:

    if not isinstance(event, TjEvent):
        return dict(event)
    return {
        "Timestamp": format_ts(event.ts),
        "log_id": event.log_id,
        "Event": event.event,
        "ConnectID": event.connect_id,
        "WaitConnections": event.wait_connections,
        "Regions": event.regions,
        "Locks": event.locks,
        "Duration": event.duration_us,
        "Host": event.host,
        "ProcessName": event.process_name,
        "Usr": event.user,
        "Context": event.context,
        "Func": event.func or "",
        "Escalating": "true" if event.escalating else "false",
        "ApplicationName": event.application_name,
    }


def clickhouse_config_from_env() -> dict[str, Any]:
    return {
        "host": os.environ.get("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        "username": os.environ.get("CLICKHOUSE_USER", "default"),
        "password": os.environ.get("CLICKHOUSE_PASSWORD", ""),
        "database": os.environ.get("CLICKHOUSE_DATABASE", "onec_logs"),
        "secure": os.environ.get("CLICKHOUSE_SECURE", "false").lower() == "true",
    }
