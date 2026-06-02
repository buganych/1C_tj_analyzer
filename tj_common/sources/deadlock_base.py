"""Abstract data source for TDEADLOCK analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from tj_common.models import TransactionBounds
from tj_common.models_deadlock import (
    DeadlockQueryFilters,
    ParticipantWait,
    TdeadlockEvent,
)


class DeadlockDataSource(ABC):
    @abstractmethod
    def fetch_tdeadlocks(self, filters: DeadlockQueryFilters) -> list[TdeadlockEvent]:
        ...

    @abstractmethod
    def transaction_bounds_at(
        self,
        connect_id: str,
        reference_ts: datetime,
        log_id: str | None,
        host: str | None,
        process_name: str | None,
    ) -> TransactionBounds:
        ...

    @abstractmethod
    def fetch_participant_tlocks(
        self,
        connect_id: str,
        tx_start: datetime,
        tx_end: datetime,
        tables: list[str],
        host: str | None,
        log_id: str | None,
        process_name: str | None,
        culprit_tx_start: datetime | None,
        culprit_connect_id: str,
    ) -> list[ParticipantWait]:
        ...

    @abstractmethod
    def fetch_context(
        self,
        connect_id: str,
        at_ts: datetime,
        host: str | None,
        log_id: str | None,
        process_name: str | None,
    ) -> str:
        ...
