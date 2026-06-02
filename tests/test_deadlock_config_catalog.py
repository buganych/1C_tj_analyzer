"""Config catalog resolver tests."""

from datetime import datetime
from pathlib import Path

from tj_common.config_catalog.resolver import attach_context_trees, parse_context_stack
from tj_common.models_deadlock import (
    DeadlockCase,
    ParticipantWait,
    TimelineEvent,
    TdeadlockEvent,
)


def test_parse_context_stack():
    ctx = "CommonModule.Test : 10 : Procedure()\nHTTPService.API : 20 : Handler()"
    frames = parse_context_stack(ctx)
    assert len(frames) == 2
    assert frames[0]["module"] == "CommonModule.Test"
    assert frames[0]["line"] == "10"


def test_attach_context_trees(tmp_path: Path):
    mod_dir = tmp_path / "CommonModules" / "TestModule" / "Ext"
    mod_dir.mkdir(parents=True)
    bsl = mod_dir / "Module.bsl"
    bsl.write_text(
        "\n".join(f"// line {i}" for i in range(1, 15)),
        encoding="utf-8",
    )

    case = DeadlockCase(
        event=TdeadlockEvent(ts=datetime.now(), connect_id="1"),
        timeline=[
            TimelineEvent(
                time="t",
                role="Участник 1 (Жертва)",
                label="lock",
                event_id="e1",
                wait=ParticipantWait(
                    ts_str="t",
                    connect_id="1",
                    context="CommonModule.TestModule : 5 : Run()",
                ),
            )
        ],
    )
    attach_context_trees(case, str(tmp_path))
    assert len(case.context_trees) == 1
    assert case.context_trees[0]["frames"][0].get("source_file")
