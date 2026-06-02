"""JSON / NDJSON tech journal loader."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tj_common.models import TjEvent
from tj_common.sources.memory import MemoryLogSource


def _get_field(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        source = row.get("_source")
        if isinstance(source, dict) and key in source:
            return source[key]
    return default


def _normalize_row(row: dict[str, Any]) -> TjEvent:
    ts_val = _get_field(row, "ts", "Timestamp", "@timestamp", "timestamp")
    if isinstance(ts_val, datetime):
        ts = ts_val
    else:
        ts = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00")).replace(
            tzinfo=None
        )

    event = str(_get_field(row, "Event", "event", "name", default="TLOCK"))
    duration = int(_get_field(row, "Duration", "duration", default=0) or 0)

    agent = row.get("agent") or {}
    if isinstance(agent, dict):
        host = agent.get("hostname", "")
    else:
        host = ""

    escalating_raw = str(_get_field(row, "Escalating", "escalating", default=""))
    return TjEvent(
        ts=ts,
        event=event,
        log_id=str(_get_field(row, "log_id", "LogId", default="")),
        connect_id=str(
            _get_field(row, "connect_id", "ConnectID", "tconnectID", default="")
        ),
        wait_connections=str(
            _get_field(row, "wait_connections", "WaitConnections", default="")
        ).replace("'", ""),
        regions=str(_get_field(row, "regions", "Regions", default="")).replace("'", ""),
        locks=str(_get_field(row, "locks", "Locks", default="")).replace("'", ""),
        duration_us=duration,
        host=str(_get_field(row, "computer_name", "Host", default=host) or host),
        process_name=str(
            _get_field(row, "process_name", "ProcessName", "pprocessName", default="")
        ),
        user=str(_get_field(row, "usr", "Usr", default="")),
        context=str(_get_field(row, "context", "Context", default="")),
        func=_get_field(row, "func", "Func", default=None) or None,
        escalating=escalating_raw.lower() == "true",
        application_name=str(
            _get_field(row, "application_name", "ApplicationName", "tapplicationName", default="")
        ),
        raw=row,
    )


def load_json_records(records: list[dict[str, Any]]) -> list[TjEvent]:
    return [_normalize_row(r) for r in records]


def parse_json_content(content: str) -> list[TjEvent]:
    content = content.strip()
    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        events = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                events.append(_normalize_row(json.loads(line)))
        return events

    if isinstance(data, dict) and "data" in data:
        return load_json_records(data["data"])
    if isinstance(data, list):
        return load_json_records(data)
    if isinstance(data, dict):
        return [_normalize_row(data)]
    return []


def load_json_file(
    path: str | Path, victim_event: str = "TLOCK"
) -> MemoryLogSource:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return MemoryLogSource(parse_json_content(text), victim_event=victim_event)
