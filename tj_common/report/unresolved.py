"""Unresolved lock cases and recommended logcfg snippets for reports."""

from __future__ import annotations

import html
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from xml.sax.saxutils import escape

from tj_common.models import AnalysisResult, UnresolvedLock
from tj_common.utils import format_ts

UNRESOLVED_TABLE_HEADERS = ["Время", "Пространство", "Причина неудачи"]
LOGCFG_SECTION_TITLE = "Рекомендуемая настройка logcfg"
LOGCFG_SECTION_HINT = (
    "Фрагмент секций `<event>` для `logcfg.xml` "
    "(полный файл: `python -m tlock_logcfg`)."
)
LOGCFG_SECTION_HINT_HTML = (
    "Фрагмент секций <event> для logcfg.xml "
    "(полный файл: python -m tlock_logcfg)."
)
_ERROR_RE = re.compile(
    r"^(?P<ts>.+?) connect=(?P<connect>\S+)(?: log_id=(?P<log_id>.*?))?: (?P<reason>.+)$"
)


@dataclass(frozen=True)
class RegionLogcfgStat:
    region: str
    count: int
    avg_wait_sec: int
    max_wait_sec: int


def _duration_sec_int(duration_us: int) -> int:
    return round(duration_us / 1_000_000)


def _format_space_label(regions: str) -> str:
    return regions.replace("'", "").strip()


def collect_unresolved_locks(result: AnalysisResult) -> list[UnresolvedLock]:
    """Collect victim/culprit failures and pipeline exceptions."""
    items: list[UnresolvedLock] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(
        timestamp: datetime,
        regions: str,
        reason: str,
        duration_us: int = 0,
    ) -> None:
        key = (format_ts(timestamp), regions, reason)
        if key in seen:
            return
        seen.add(key)
        items.append(
            UnresolvedLock(
                timestamp=timestamp,
                regions=regions,
                reason=reason,
                duration_us=duration_us,
            )
        )

    for victim in result.victims:
        ev = victim.event
        if victim.parse_error:
            _add(ev.ts, ev.regions, victim.parse_error, ev.duration_us)
            continue
        for culprit in victim.culprits:
            if culprit.error:
                _add(
                    ev.ts,
                    ev.regions,
                    f"Виновник {culprit.connect_id}: {culprit.error}",
                    ev.duration_us,
                )

    for item in result.unresolved:
        _add(item.timestamp, item.regions, item.reason, item.duration_us)

    for err in result.errors:
        if any(err == i.reason or err.endswith(i.reason) for i in items):
            continue
        match = _ERROR_RE.match(err)
        if match:
            try:
                ts = datetime.fromisoformat(match.group("ts").strip())
            except ValueError:
                ts = items[0].timestamp if items else datetime.min
            _add(ts, "", match.group("reason").strip())
        else:
            ts = items[0].timestamp if items else datetime.min
            _add(ts, "", err)

    return items


def collect_logcfg_stats_for_unresolved(
    unresolved: list[UnresolvedLock],
) -> list[RegionLogcfgStat]:
    durations: dict[str, list[int]] = defaultdict(list)
    for item in unresolved:
        region = item.regions.strip()
        if not region:
            continue
        durations[region].append(item.duration_us)

    stats = [
        RegionLogcfgStat(
            region=region,
            count=len(values),
            avg_wait_sec=_duration_sec_int(round(sum(values) / len(values))),
            max_wait_sec=max(_duration_sec_int(v) for v in values),
        )
        for region, values in durations.items()
    ]
    return sorted(stats, key=lambda s: (-s.count, s.region))


def unresolved_table_rows(unresolved: list[UnresolvedLock]) -> list[list[str]]:
    return [
        [
            format_ts(item.timestamp),
            _format_space_label(item.regions) or "—",
            item.reason,
        ]
        for item in unresolved
    ]


def render_logcfg_tlock_events(stats: list[RegionLogcfgStat]) -> str:
    blocks: list[str] = []
    for item in stats:
        escaped_region = escape(item.region, {'"': "&quot;"})
        blocks.append(
            f"\t<!-- Количество = {item.count}, "
            f"среднее ожидание = {item.avg_wait_sec}, "
            f"максимальное ожидание = {item.max_wait_sec} -->\n"
            f"\t<event>\n"
            f'      <eq property="name" value="TLOCK"/>\n'
            f'\t  <eq property="regions" value="{escaped_region}"/>\n'
            f"    </event>"
        )
    return "\n".join(blocks)


def _logcfg_stats_for_result(result: AnalysisResult) -> list[RegionLogcfgStat]:
    return collect_logcfg_stats_for_unresolved(collect_unresolved_locks(result))


def append_unresolved_table_markdown(parts: list[str], result: AnalysisResult) -> None:
    unresolved = collect_unresolved_locks(result)
    if not unresolved:
        return

    parts.append("<details>")
    parts.append(f"<summary>Неразобранные блокировки ({len(unresolved)})</summary>")
    parts.append("")
    parts.extend(_md_table(UNRESOLVED_TABLE_HEADERS, unresolved_table_rows(unresolved)))
    parts.append("")
    parts.append("</details>")
    parts.append("")


def append_logcfg_section_markdown(parts: list[str], result: AnalysisResult) -> None:
    stats = _logcfg_stats_for_result(result)
    hidden_attr = " hidden" if not stats else ""
    parts.append(f"<details{hidden_attr}>")
    parts.append(f"<summary>{LOGCFG_SECTION_TITLE}</summary>")
    parts.append("")
    if stats:
        parts.append(LOGCFG_SECTION_HINT)
        parts.append("")
        parts.append("```xml")
        parts.append(render_logcfg_tlock_events(stats))
        parts.append("```")
        parts.append("")
    parts.append("</details>")
    parts.append("")


def append_unresolved_sections_markdown(parts: list[str], result: AnalysisResult) -> None:
    append_unresolved_table_markdown(parts, result)
    append_logcfg_section_markdown(parts, result)


def append_unresolved_table_text(parts: list[str], result: AnalysisResult) -> None:
    unresolved = collect_unresolved_locks(result)
    if not unresolved:
        return

    parts.append("")
    parts.append("--- Неразобранные блокировки ---")
    parts.append("\t".join(UNRESOLVED_TABLE_HEADERS))
    for row in unresolved_table_rows(unresolved):
        parts.append("\t".join(row))


def append_logcfg_section_text(parts: list[str], result: AnalysisResult) -> None:
    stats = _logcfg_stats_for_result(result)
    if not stats:
        return
    parts.append("")
    parts.append(f"--- {LOGCFG_SECTION_TITLE} ---")
    parts.append(render_logcfg_tlock_events(stats))


def append_unresolved_sections_text(parts: list[str], result: AnalysisResult) -> None:
    append_unresolved_table_text(parts, result)
    append_logcfg_section_text(parts, result)


def render_unresolved_table_html(builder, result: AnalysisResult) -> None:
    unresolved = collect_unresolved_locks(result)
    if not unresolved:
        return

    builder.raw(
        '<details class="report-section">'
        f"<summary>Неразобранные блокировки ({len(unresolved)})</summary>"
    )
    builder.table(
        UNRESOLVED_TABLE_HEADERS,
        unresolved_table_rows(unresolved),
        css_class="compact-table",
    )
    builder.raw("</details>")


def render_logcfg_section_html(builder, result: AnalysisResult) -> None:
    stats = _logcfg_stats_for_result(result)
    hidden_attr = " hidden" if not stats else ""
    builder.raw(
        f'<details class="report-section"{hidden_attr}>'
        f"<summary>{LOGCFG_SECTION_TITLE}</summary>"
    )
    if stats:
        builder.paragraph(LOGCFG_SECTION_HINT_HTML, css_class="muted")
        builder.raw(
            f"<pre><code>{html.escape(render_logcfg_tlock_events(stats))}</code></pre>"
        )
    builder.raw("</details>")


def render_unresolved_sections_html(builder, result: AnalysisResult) -> None:
    render_unresolved_table_html(builder, result)
    render_logcfg_section_html(builder, result)


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def unresolved_to_dict(result: AnalysisResult) -> dict:
    unresolved = collect_unresolved_locks(result)
    stats = collect_logcfg_stats_for_unresolved(unresolved)
    return {
        "unresolved": [
            {
                "time": format_ts(item.timestamp),
                "regions": item.regions,
                "reason": item.reason,
                "duration_sec": _duration_sec_int(item.duration_us),
            }
            for item in unresolved
        ],
        "recommended_logcfg_events": [
            {
                "regions": s.region,
                "count": s.count,
                "avg_wait_sec": s.avg_wait_sec,
                "max_wait_sec": s.max_wait_sec,
                "xml": render_logcfg_tlock_events([s]),
            }
            for s in stats
        ],
        "recommended_logcfg_snippet": render_logcfg_tlock_events(stats) or None,
    }
