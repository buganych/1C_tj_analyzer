"""Unit tests for TDEADLOCK parsing and classification."""

from datetime import datetime

from tj_common.analysis.deadlock import (
    DEADLOCK_TYPE_ESCALATION,
    DEADLOCK_TYPE_ORDER,
    build_cross_matrix,
    classify_deadlock_type,
    parse_deadlock_intersections,
)
from tj_common.models_deadlock import DeadlockCase, Participant, ParticipantWait, TdeadlockEvent


DCI_TWO = (
    "518868 500546 InfoRg17707.DIMS Exclusive "
    "InfoRg17707.DIMS Exclusive Fld17708=1, "
    "500546 518868 InfoRg17707.DIMS Exclusive "
    "InfoRg17707.DIMS Exclusive Fld17709=2"
)


def test_parse_dci_two_participants():
    edges, tables, p1, p2, p3, count = parse_deadlock_intersections(DCI_TWO, "518868")
    assert len(edges) == 2
    assert "InfoRg17707.DIMS" in tables
    assert p1.connect_id == "518868"
    assert p2.connect_id in ("500546", "518868")
    assert p3 is None
    assert count == 2


def test_classify_escalation():
    victim = Participant(
        waits=[
            ParticipantWait(
                ts_str="",
                ts=datetime.now(),
                connect_id="1",
                level="Shared",
                is_wait=True,
                properties=[],
            )
        ]
    )
    assert classify_deadlock_type(victim) == DEADLOCK_TYPE_ESCALATION


def test_classify_order():
    victim = Participant(
        waits=[
            ParticipantWait(
                ts_str="",
                ts=datetime.now(),
                connect_id="1",
                level="Exclusive",
                is_wait=False,
                properties=[],
            )
        ]
    )
    assert classify_deadlock_type(victim) == DEADLOCK_TYPE_ORDER


def test_cross_matrix_nonempty():
    case = DeadlockCase(
        event=TdeadlockEvent(ts=datetime.now(), connect_id="1"),
        victim=Participant(
            connect_id="1",
            role="Участник 1 (Жертва)",
            waits=[
                ParticipantWait(
                    ts_str="t",
                    ts=datetime.now(),
                    connect_id="1",
                    regions="T.DIMS",
                    level="Exclusive",
                    is_wait=False,
                )
            ],
        ),
        participant2=Participant(
            connect_id="2",
            role="Участник 2",
            waits=[
                ParticipantWait(
                    ts_str="t",
                    ts=datetime.now(),
                    connect_id="2",
                    regions="T.DIMS",
                    level="Shared",
                    is_wait=True,
                )
            ],
        ),
    )
    matrix = build_cross_matrix(case)
    assert "Участник" in matrix or "|" in matrix
