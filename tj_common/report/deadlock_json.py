"""JSON report for TDEADLOCK analysis."""

from __future__ import annotations

import json
from typing import Any

from tj_common.models_deadlock import DeadlockAnalysisResult, DeadlockCase


def _case_to_dict(case: DeadlockCase) -> dict[str, Any]:
    ev = case.event
    return {
        "id": case.case_id,
        "status": case.status,
        "status_detail": case.status_detail,
        "timestamp": ev.ts.isoformat(),
        "log_id": ev.log_id,
        "connect_id": ev.connect_id,
        "session_id": ev.session_id,
        "host": ev.host,
        "process_name": ev.process_name,
        "user": ev.user,
        "culprit_connect_ids": case.culprit_connect_ids,
        "deadlock_connection_intersections": ev.deadlock_connection_intersections,
        "participant_count": case.participant_count,
        "deadlock_type": case.deadlock_type,
        "cross_matrix": case.cross_matrix,
        "cross_matrix_contexts": case.cross_matrix_contexts,
        "text_graph": case.text_graph,
        "timeline_text": case.timeline_text,
        "participants": [
            {
                "role": p.role,
                "connect_id": p.connect_id,
                "table": p.table,
                "tx_start": p.tx_start_ts,
                "tx_end": p.tx_end_ts,
                "wait_count": len(p.waits),
            }
            for p in case.participants()
            if p.connect_id
        ],
        "timeline": [
            {
                "time": e.time,
                "role": e.role,
                "label": e.label,
                "is_wait": e.is_wait,
                "event_id": e.event_id,
            }
            for e in case.timeline
        ],
        "graphs": {
            "graph_wait_block": case.graph_wait_block,
            "graph_locks": case.graph_locks,
        },
        "context_trees": case.context_trees,
    }


def render_deadlock_json(result: DeadlockAnalysisResult, indent: int = 2) -> str:
    payload = {
        "analyzer": "TDEADLOCK",
        "cases": [_case_to_dict(c) for c in result.cases],
        "errors": result.errors,
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)
