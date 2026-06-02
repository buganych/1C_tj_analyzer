"""Combined report for unified lock analysis."""

from __future__ import annotations

import json
from typing import Any

from tj_common.analysis.unified_pipeline import UnifiedAnalysisResult
from tj_common.report.deadlock_json import render_deadlock_json
from tj_common.report.deadlock_text import render_deadlock_text
from tj_common.report.json_out import analysis_to_dict, render_json
from tj_common.report.labels import TLOCK_LABELS, TTIMEOUT_LABELS
from tj_common.report.text import render_text


def unified_to_dict(result: UnifiedAnalysisResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "analyzer": "unified",
        "summary": result.summary,
        "skipped": result.skipped,
    }
    if result.tlock is not None:
        payload["tlock"] = analysis_to_dict(result.tlock, labels=TLOCK_LABELS)
    if result.ttimeout is not None:
        payload["ttimeout"] = analysis_to_dict(
            result.ttimeout, labels=TTIMEOUT_LABELS
        )
    if result.tdeadlock is not None:
        payload["tdeadlock"] = json.loads(render_deadlock_json(result.tdeadlock))
    return payload


def render_unified_json(result: UnifiedAnalysisResult, indent: int = 2) -> str:
    return json.dumps(unified_to_dict(result), ensure_ascii=False, indent=indent)


def render_unified_text(result: UnifiedAnalysisResult) -> str:
    parts: list[str] = []
    s = result.summary
    parts.append("=" * 60)
    parts.append("Сводный анализ проблем блокировок 1С")
    parts.append("=" * 60)
    parts.append(
        f"TLOCK: {s['tlock_victims']}  |  "
        f"TTIMEOUT: {s['ttimeout_victims']}  |  "
        f"TDEADLOCK: {s['tdeadlock_cases']}"
    )
    if s["total_errors"]:
        parts.append(f"Ошибки обработки: {s['total_errors']}")
    if result.skipped:
        parts.append(f"Пропущено: {', '.join(result.skipped)}")

    if result.tlock is not None:
        parts.append("")
        parts.append("#" * 60)
        parts.append("# TLOCK")
        parts.append("#" * 60)
        parts.append(render_text(result.tlock, labels=TLOCK_LABELS))

    if result.ttimeout is not None:
        parts.append("")
        parts.append("#" * 60)
        parts.append("# TTIMEOUT")
        parts.append("#" * 60)
        parts.append(render_text(result.ttimeout, labels=TTIMEOUT_LABELS))

    if result.tdeadlock is not None:
        parts.append("")
        parts.append("#" * 60)
        parts.append("# TDEADLOCK")
        parts.append("#" * 60)
        parts.append(render_deadlock_text(result.tdeadlock))

    return "\n".join(parts)
