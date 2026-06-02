"""Port of 1C АнализTLOCK lock comparison logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from tj_common.models import LockConflictResult

# BSL conflict type names (kept for report compatibility)
FULL_MATCH = "ПолноеСоответствие"
ESCALATION = "Эскалация"
DIFFERENT_DIMENSIONS = "РазныйНаборИзмерений"


@dataclass
class DateRange:
    start: date
    end: date


@dataclass
class LockProperties:
    mode: str  # Shared | Exclusive
    space: str
    fields: dict[str, Any] = field(default_factory=dict)


def _strip_quotes(s: str) -> str:
    return s.replace("'", "")


def _parse_period_value(raw: str) -> DateRange | str:
    """Parse Period=[T\"...\":+] style values."""
    if not (raw.startswith("[") and raw.endswith("]")):
        return raw
    inner = raw[1:-1]
    parts = inner.split(":")
    if len(parts) < 2:
        return raw

    def parse_bound(part: str) -> date:
        if "-" in part and 'T"' not in part and "T\"" not in part:
            return date(1, 1, 1)
        if "+" in part:
            return date(3999, 12, 31)
        # [T"20210501000000" -> take 14 chars from position 3 (after T")
        if len(part) >= 17 and part[0] in "Tt":
            chunk = part[3:17]
        elif len(part) >= 14:
            chunk = part[-14:] if part.startswith('T"') else part[3:17]
        else:
            chunk = part.replace('T"', "").replace('"', "")[:14]
        try:
            return datetime.strptime(chunk, "%Y%m%d%H%M%S").date()
        except ValueError:
            return date(1, 1, 1)

    start = parse_bound(parts[0])
    end = parse_bound(parts[1])
    return DateRange(start=start, end=end)


def parse_lock_properties(regions: str, locks: str) -> list[LockProperties]:
    """Port of ПолучитьМассивСвойствБлокировок."""
    regions = _strip_quotes(regions)
    locks = _strip_quotes(locks)
    region_list = [r.strip() for r in regions.split(",") if r.strip()]
    lock_parts = [lp.strip() for lp in locks.split(",") if lp.strip()]

    result: list[LockProperties] = []
    current_space = False
    current_mode = ""

    for space in region_list:
        for lock_item in lock_parts:
            pos_shared = lock_item.find("Shared")
            pos_exclusive = lock_item.find("Exclusive")
            if pos_shared <= 0 and pos_exclusive <= 0:
                continue

            if pos_exclusive > 0:
                current_mode = "Exclusive"
            else:
                current_mode = "Shared"

            if space in lock_item:
                current_space = True
            else:
                current_space = False
                continue

            if not current_space:
                continue

            block = lock_item
            mode_pos = block.find(current_mode)
            if mode_pos > 0:
                block = block[mode_pos + len(current_mode) + 1 :]

            fields: dict[str, Any] = {}
            for token in block.split():
                if "=" not in token:
                    continue
                key, _, val = token.partition("=")
                if key == "Period":
                    parsed = _parse_period_value(val)
                    fields[key] = parsed
                else:
                    fields[key] = val

            result.append(
                LockProperties(mode=current_mode, space=space, fields=fields)
            )

    return result


def values_intersect(value1: Any, value2: Any) -> bool:
    """Port of ЗначенияПересекаются."""
    if isinstance(value1, DateRange) and isinstance(value2, DateRange):
        return value1.start <= value2.end and value2.start <= value1.end
    if isinstance(value1, DateRange):
        if isinstance(value2, date):
            return value1.start <= value2 <= value1.end
        return False
    if isinstance(value2, DateRange):
        if isinstance(value1, date):
            return value2.start <= value1 <= value2.end
        return False
    return value1 == value2


def _distinct_spaces(props: list[LockProperties]) -> int:
    return len({p.space for p in props})


def _filter_large_lock_set(
    victim_props: list[LockProperties],
    culprit_props: list[LockProperties],
) -> list[LockProperties]:
    """Simplified port of large-lock optimization (in-memory filter)."""
    if not victim_props:
        return culprit_props
    v0 = victim_props[0]
    filtered: list[LockProperties] = []
    for c in culprit_props:
        if c.space != v0.space:
            continue
        match = True
        for key, val in v0.fields.items():
            if key == "Period":
                continue
            cval = c.fields.get(key)
            if cval is None:
                continue
            if str(cval) != str(val) and str(cval) != "":
                match = False
                break
        if match:
            filtered.append(c)
    return filtered


def locks_conflict(
    victim_props: list[LockProperties],
    culprit_props: list[LockProperties],
    culprit_escalating: bool = False,
) -> LockConflictResult:
    """Port of БлокировкиКонфликтуют — returns last matching conflict type."""
    result = LockConflictResult()

    optimize = len(culprit_props) > 100 and _distinct_spaces(culprit_props) == 1

    for v_prop in victim_props:
        c_list = culprit_props
        if optimize:
            c_list = _filter_large_lock_set([v_prop], culprit_props)

        for c_prop in c_list:
            if v_prop.space != c_prop.space:
                continue
            if v_prop.mode == "Shared" and c_prop.mode == "Shared":
                continue

            if (
                len(v_prop.fields) == 0
                or len(c_prop.fields) == 0
                or culprit_escalating
            ):
                return LockConflictResult(has_conflict=True, conflict_type=ESCALATION)

            all_keys = set(v_prop.fields) | set(c_prop.fields)
            full_match = True
            has_conflict = True

            for key in all_keys:
                v_val = v_prop.fields.get(key)
                c_val = c_prop.fields.get(key)
                if v_val is None or c_val is None:
                    full_match = False
                    continue
                if not values_intersect(v_val, c_val):
                    has_conflict = False

            if not has_conflict:
                continue

            if full_match:
                result = LockConflictResult(
                    has_conflict=True, conflict_type=FULL_MATCH
                )
            else:
                result = LockConflictResult(
                    has_conflict=True, conflict_type=DIFFERENT_DIMENSIONS
                )

    return result


def check_full_match_strings(victim_locks: str, culprit_locks: str) -> bool:
    """ClickHouse hasAny-style full match on lock field tokens."""
    pattern = re.compile(r"\w*\.\w* (?:Exclusive|Shared)", re.IGNORECASE)

    def extract_fields(locks: str) -> set[str]:
        cleaned = _strip_quotes(locks).strip()
        stripped = pattern.sub("", cleaned)
        return {p.strip() for p in stripped.split(",") if p.strip()}

    v_fields = extract_fields(victim_locks)
    c_fields = extract_fields(culprit_locks)
    if not v_fields or not c_fields:
        return False
    return bool(v_fields & c_fields)
