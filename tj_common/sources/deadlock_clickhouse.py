"""ClickHouse adapter for TDEADLOCK analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import clickhouse_connect

from tj_common.analysis.locks import parse_lock_properties
from tj_common.models import TransactionBounds
from tj_common.models_deadlock import (
    DeadlockQueryFilters,
    ParticipantWait,
    TdeadlockEvent,
)
from tj_common.sources.deadlock_base import DeadlockDataSource
from tj_common.sources.clickhouse import ClickHouseSource
from tj_common.utils import host_variants


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
        tzinfo=None
    )


class DeadlockClickHouseSource(DeadlockDataSource):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        username: str = "default",
        password: str = "",
        database: str = "onec_logs",
        secure: bool = False,
    ):
        self.database = database
        self._tlock = ClickHouseSource(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            secure=secure,
        )
        self.client = self._tlock.client

    def _query(self, sql: str, params: dict | None = None) -> list[dict]:
        return self._tlock._query(sql, params)

    def _query_ts(self, sql_template: str, time_params: dict, params: dict) -> list[dict]:
        return self._tlock._query_ts(sql_template, time_params=time_params, params=params)

    def _log_clause(self, log_ids: list[str] | None) -> tuple[str, dict]:
        return self._tlock._log_id_clause(log_ids)

    def _host_clause(self, hosts: list[str] | None) -> tuple[str, dict]:
        return self._tlock._host_clause(hosts)

    def _time_clause(
        self, time_from: datetime | None, time_to: datetime | None
    ) -> tuple[str, dict[str, datetime], bool]:
        return self._tlock._time_clause(time_from, time_to)

    def fetch_tdeadlocks(self, filters: DeadlockQueryFilters) -> list[TdeadlockEvent]:
        log_sql, log_params = self._log_clause(filters.log_ids)
        host_sql, host_params = self._host_clause(filters.hosts)
        time_sql, time_params, use_time = self._time_clause(
            filters.time_from, filters.time_to
        )

        sql = f"""
            SELECT log_id, ts, connect_id, session_id, computer_name, process_name,
                   usr, context, deadlock_connection_intersections
            FROM {self.database}.tj_tdeadlock
            WHERE {log_sql}
              AND {host_sql}
              AND {time_sql}
        """
        params: dict[str, Any] = {**log_params, **host_params}
        if filters.process_name:
            sql += " AND lower(process_name) = lower({process_name:String})"
            params["process_name"] = filters.process_name
        if filters.connect_id:
            sql += " AND connect_id = {connect_id:String}"
            params["connect_id"] = filters.connect_id
        if filters.session_id:
            sql += " AND session_id = {session_id:String}"
            params["session_id"] = filters.session_id
        if filters.single_at:
            sql += " AND ts = toDateTime64({single_at:String}, 6)"
            params["single_at"] = self._tlock._ts_literal(filters.single_at)
        sql += " ORDER BY ts ASC"

        if use_time:
            rows = self._query_ts(sql, time_params=time_params, params=params)
        else:
            rows = self._query(sql, params)

        result = []
        for r in rows:
            ctx = str(r.get("context") or "")
            result.append(
                TdeadlockEvent(
                    ts=_parse_ts(r["ts"]),
                    connect_id=str(r.get("connect_id") or ""),
                    session_id=str(r.get("session_id") or ""),
                    host=str(r.get("computer_name") or ""),
                    process_name=str(r.get("process_name") or ""),
                    user=str(r.get("usr") or ""),
                    context=ctx,
                    last_line_context=ctx.splitlines()[-1].strip() if ctx else "",
                    deadlock_connection_intersections=str(
                        r.get("deadlock_connection_intersections") or ""
                    ),
                    log_id=str(r.get("log_id") or ""),
                    raw=dict(r),
                )
            )
        return result

    def transaction_bounds_at(
        self,
        connect_id: str,
        reference_ts: datetime,
        log_id: str | None,
        host: str | None,
        process_name: str | None,
    ) -> TransactionBounds:
        hosts = [host] if host else None
        return self._tlock.find_transaction_bounds(
            connect_id, reference_ts, log_id=log_id, hosts=hosts
        )

    def _tables_region_clause(self, tables: list[str]) -> tuple[str, dict]:
        if not tables:
            return "1=1", {}
        if len(tables) == 1:
            return "regions LIKE {region0:String}", {"region0": f"%{tables[0]}%"}
        parts = []
        params: dict[str, Any] = {}
        for i, t in enumerate(tables):
            parts.append(f"regions LIKE {{region{i}:String}}")
            params[f"region{i}"] = f"%{t}%"
        in_list = ", ".join(f"{{tbl{i}:String}}" for i in range(len(tables)))
        for i, t in enumerate(tables):
            params[f"tbl{i}"] = t
        return f"(regions IN ({in_list}) OR {' OR '.join(parts)})", params

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
        host_sql, host_params = self._host_clause([host] if host else None)
        log_sql, log_params = self._log_clause([log_id] if log_id else None)
        region_sql, region_params = self._tables_region_clause(tables)

        guilty_ts = culprit_tx_start or tx_start
        sql = f"""
            SELECT ts, connect_id, wait_connections, context, locks, regions, duration
            FROM {self.database}.tj_tlock
            WHERE connect_id = {{connect_id:String}}
              AND ts >= {{tx_start:DateTime64(6)}}
              AND ts <= {{tx_end:DateTime64(6)}}
              AND {region_sql}
              AND {host_sql}
              AND {log_sql}
            ORDER BY ts ASC
            LIMIT 5000
        """
        params: dict[str, Any] = {
            "connect_id": connect_id,
            **host_params,
            **log_params,
            **region_params,
        }
        rows = self._query_ts(
            sql,
            time_params={"tx_start": tx_start, "tx_end": tx_end},
            params=params,
        )

        waits: list[ParticipantWait] = []
        guilty_literal = self._tlock._ts_literal(guilty_ts)
        for r in rows:
            ts = _parse_ts(r["ts"])
            wc = str(r.get("wait_connections") or "")
            wait_prev = ts < guilty_ts
            if wc:
                ids = [x.strip().replace("'", "") for x in wc.split(",")]
                if culprit_connect_id not in ids and not wait_prev:
                    wc = ""
            regions = str(r.get("regions") or "")
            locks = str(r.get("locks") or "")
            waits.append(
                ParticipantWait(
                    ts=ts,
                    ts_str=self._tlock._ts_literal(ts),
                    connect_id=str(r.get("connect_id") or ""),
                    context=str(r.get("context") or ""),
                    locks=locks,
                    regions=regions,
                    wait_connections=wc,
                    wait_previous_tx=wait_prev,
                    properties=parse_lock_properties(regions, locks),
                )
            )
        return waits

    def fetch_context(
        self,
        connect_id: str,
        at_ts: datetime,
        host: str | None,
        log_id: str | None,
        process_name: str | None,
    ) -> str:
        return self._tlock.fetch_context(
            connect_id, at_ts, log_id=log_id, hosts=[host] if host else None
        )
