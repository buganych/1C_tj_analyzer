"""Data models for TDEADLOCK analysis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DeadlockQueryFilters:
    """Filters for loading TDEADLOCK cases."""

    log_ids: list[str] | None = None
    time_from: datetime | None = None
    time_to: datetime | None = None
    hosts: list[str] | None = None
    process_name: str | None = None
    connect_id: str | None = None
    session_id: str | None = None
    single_at: datetime | None = None

    def matches_log_id(self, log_id: str) -> bool:
        if not self.log_ids:
            return True
        return log_id in self.log_ids

    def matches_time(self, ts: datetime) -> bool:
        if self.time_from is not None and ts <= self.time_from:
            return False
        if self.time_to is not None and ts > self.time_to:
            return False
        return True


@dataclass
class TdeadlockEvent:
    ts: datetime
    connect_id: str
    session_id: str = ""
    host: str = ""
    process_name: str = ""
    user: str = ""
    context: str = ""
    last_line_context: str = ""
    deadlock_connection_intersections: str = ""
    log_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LockEdge:
    wait_connect_id: str
    block_connect_id: str
    table: str
    mode: str
    locks: str
    resources: list[Any] = field(default_factory=list)


@dataclass
class Participant:
    connect_id: str = ""
    table: str = ""
    user: str = ""
    host: str = ""
    tx_start: datetime | None = None
    tx_end: datetime | None = None
    tx_start_ts: str = ""
    tx_end_ts: str = ""
    waits: list[ParticipantWait] = field(default_factory=list)
    role: str = ""


@dataclass
class ParticipantWait:
    ts_str: str
    connect_id: str = ""
    context: str = ""
    ts: datetime | None = None
    locks: str = ""
    regions: str = ""
    wait_connections: str = ""
    level: str = ""
    is_wait: bool = False
    wait_previous_tx: bool = False
    properties: list[Any] = field(default_factory=list)
    conflicting_resources: list[Any] = field(default_factory=list)
    event_id: str = ""


@dataclass
class TimelineEvent:
    time: str
    role: str
    label: str
    is_wait: bool = False
    event_id: str = ""
    wait: ParticipantWait | None = None
    order: int = 5


@dataclass
class DeadlockCase:
    event: TdeadlockEvent
    participant_count: int = 2
    victim: Participant = field(default_factory=Participant)
    participant2: Participant = field(default_factory=Participant)
    participant3: Participant | None = None
    edges: list[LockEdge] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
    status: str = "pending"
    status_detail: str = ""
    deadlock_type: str = ""
    cross_matrix: str = ""
    cross_matrix_contexts: str = ""
    text_graph: str = ""
    timeline_text: str = ""
    graph_wait_block: dict[str, Any] = field(default_factory=dict)
    graph_locks: dict[str, Any] = field(default_factory=dict)
    context_trees: list[dict[str, Any]] = field(default_factory=list)
    culprit_connect_ids: str = ""

    @property
    def case_id(self) -> str:
        raw = (
            f"{self.event.ts.isoformat()}"
            f"{self.event.host}"
            f"{self.event.session_id}"
            f"{self.event.connect_id}"
        )
        return hashlib.md5(raw.encode()).hexdigest()

    def participants(self) -> list[Participant]:
        out = [self.victim, self.participant2]
        if self.participant3 and self.participant3.connect_id:
            out.append(self.participant3)
        return out


@dataclass
class DeadlockAnalysisResult:
    cases: list[DeadlockCase] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
