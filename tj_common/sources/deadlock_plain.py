"""Load plain/json TJ into DeadlockMemorySource."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tj_common.models import TjEvent
from tj_common.models_deadlock import TdeadlockEvent
from tj_common.sources.deadlock_memory import DeadlockMemorySource
from tj_common.sources.json_file import parse_json_content
from tj_common.sources.plain import parse_plain_content


def events_to_deadlock_source(events: list[TjEvent]) -> DeadlockMemorySource:
    tdeadlocks: list[TdeadlockEvent] = []
    other: list[TjEvent] = []
    for e in events:
        if e.event == "TDEADLOCK":
            dci = str(
                e.raw.get("DeadlockConnectionIntersections")
                or e.raw.get("deadlock_connection_intersections")
                or ""
            )
            tdeadlocks.append(
                TdeadlockEvent(
                    ts=e.ts,
                    connect_id=e.connect_id,
                    session_id=str(
                        e.raw.get("SessionID") or e.raw.get("session_id") or ""
                    ),
                    host=e.host,
                    process_name=e.process_name,
                    user=e.user,
                    context=e.context,
                    deadlock_connection_intersections=dci,
                    log_id=e.log_id,
                    raw=e.raw,
                )
            )
        else:
            other.append(e)
    return DeadlockMemorySource(tdeadlocks, other)


def load_deadlock_plain_file(
    path: str | Path, base_date: datetime | None = None
) -> DeadlockMemorySource:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return events_to_deadlock_source(parse_plain_content(text, base_date))


def load_deadlock_json_file(path: str | Path) -> DeadlockMemorySource:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return events_to_deadlock_source(parse_json_content(text))
