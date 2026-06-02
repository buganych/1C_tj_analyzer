"""Tests for lock comparison engine."""

from datetime import date

from tlock_analyzer.analysis.locks import (
    DIFFERENT_DIMENSIONS,
    ESCALATION,
    FULL_MATCH,
    check_full_match_strings,
    locks_conflict,
    parse_lock_properties,
    values_intersect,
)
from tlock_analyzer.analysis.locks import DateRange


# Real sample from ClickHouse onec_logs (2026-05-27)
VICTIM_REGIONS = "InfoRg17707.DIMS"
VICTIM_LOCKS = (
    "InfoRg17707.DIMS Exclusive "
    "Fld17708=17552:9e5b0050560133fc11f0458ad37f53ef "
    "Fld17709=80:9e5b0050560133fc11f0468638b41009 "
    "Fld17710=393:c62745a3cb8472d9dca8babafb232a78"
)


def test_parse_lock_properties_real_sample():
    props = parse_lock_properties(VICTIM_REGIONS, VICTIM_LOCKS)
    assert len(props) >= 1
    assert props[0].mode == "Exclusive"
    assert props[0].space == "InfoRg17707.DIMS"
    assert "Fld17708" in props[0].fields


def test_same_locks_full_match():
    v = parse_lock_properties(VICTIM_REGIONS, VICTIM_LOCKS)
    c = parse_lock_properties(VICTIM_REGIONS, VICTIM_LOCKS)
    result = locks_conflict(v, c)
    assert result.has_conflict
    assert result.conflict_type == FULL_MATCH


def test_shared_shared_no_conflict():
    regions = "Test.Table"
    locks = "Test.Table Shared Fld1=1"
    props = parse_lock_properties(regions, locks)
    result = locks_conflict(props, props)
    assert not result.has_conflict


def test_different_field_values_no_intersection():
    """BSL: non-intersecting field values => no conflict."""
    regions = "InfoRg17707.DIMS"
    victim = "InfoRg17707.DIMS Exclusive Fld17708=aaa Fld17709=bbb"
    culprit = "InfoRg17707.DIMS Exclusive Fld17708=ccc Fld17709=ddd"
    v = parse_lock_properties(regions, victim)
    c = parse_lock_properties(regions, culprit)
    result = locks_conflict(v, c)
    assert not result.has_conflict


def test_different_dimensions_partial_field_set():
    """BSL: common fields intersect, but different field sets => РазныйНаборИзмерений."""
    regions = "T.Table"
    victim = "T.Table Exclusive Fld1=aaa Fld2=bbb"
    culprit = "T.Table Exclusive Fld1=aaa"
    v = parse_lock_properties(regions, victim)
    c = parse_lock_properties(regions, culprit)
    result = locks_conflict(v, c)
    assert result.has_conflict
    assert result.conflict_type == DIFFERENT_DIMENSIONS


def test_escalation_empty_fields():
    regions = "T.Table"
    victim = "T.Table Exclusive Fld1=1"
    culprit = "T.Table Exclusive"
    v = parse_lock_properties(regions, victim)
    c = parse_lock_properties(regions, culprit)
    result = locks_conflict(v, c)
    assert result.has_conflict
    assert result.conflict_type == ESCALATION


def test_values_intersect_period():
    r1 = DateRange(date(2021, 5, 1), date(2021, 6, 1))
    r2 = DateRange(date(2021, 5, 15), date(2021, 7, 1))
    assert values_intersect(r1, r2)
    r3 = DateRange(date(2022, 1, 1), date(2022, 2, 1))
    assert not values_intersect(r1, r3)


def test_check_full_match_strings():
    assert check_full_match_strings(VICTIM_LOCKS, VICTIM_LOCKS)
    other = "InfoRg17707.DIMS Exclusive Fld99999=other"
    assert not check_full_match_strings(VICTIM_LOCKS, other)
