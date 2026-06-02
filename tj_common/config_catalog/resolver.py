"""Resolve 1C context stack lines against exported configuration catalog."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tj_common.models_deadlock import DeadlockCase

# Typical TJ context line: Module.Object : line : call
STACK_LINE_RE = re.compile(
    r"^(.+?)\s*:\s*(\d+)\s*:\s*(.+)$",
    re.MULTILINE,
)


def parse_context_stack(context: str) -> list[dict[str, str]]:
    frames: list[dict[str, str]] = []
    for line in context.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        m = STACK_LINE_RE.match(line)
        if m:
            frames.append(
                {
                    "module": m.group(1).strip(),
                    "line": m.group(2),
                    "call": m.group(3).strip(),
                }
            )
        else:
            frames.append({"module": line, "line": "", "call": ""})
    return frames


def _find_bsl_file(catalog: Path, module_hint: str) -> str | None:
    candidates = list(catalog.rglob("*.bsl")) + list(catalog.rglob("*.os"))
    module_lower = module_hint.lower().replace(".", "/")
    # CommonModule.Foo -> CommonModules/Foo/Ext/Module.bsl
    parts = module_hint.split(".")
    search_names = {module_hint.lower(), parts[-1].lower() if parts else ""}
    if len(parts) >= 2:
        search_names.add(parts[-1].lower())
        search_names.add(f"{parts[-2]}s/{parts[-1]}".lower())

    for path in candidates:
        rel = str(path.relative_to(catalog)).lower().replace("\\", "/")
        if module_lower in rel:
            return str(path.relative_to(catalog))
        for name in search_names:
            if name and name in rel:
                return str(path.relative_to(catalog))
    return None


def resolve_frame(catalog: Path, frame: dict[str, str]) -> dict[str, Any]:
    module = frame.get("module", "")
    rel = _find_bsl_file(catalog, module) if module else None
    snippet = ""
    if rel and frame.get("line"):
        try:
            lines = (catalog / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            ln = int(frame["line"])
            start = max(0, ln - 3)
            end = min(len(lines), ln + 2)
            snippet = "\n".join(lines[start:end])
        except (ValueError, OSError):
            snippet = ""
    return {
        "module": module,
        "line": frame.get("line", ""),
        "call": frame.get("call", ""),
        "source_file": rel,
        "snippet": snippet,
    }


def attach_context_trees(case: DeadlockCase, catalog_path: str) -> None:
    catalog = Path(catalog_path)
    if not catalog.is_dir():
        return

    trees: list[dict[str, Any]] = []
    for ev in case.timeline:
        if not ev.wait or not ev.wait.context:
            continue
        frames = [resolve_frame(catalog, f) for f in parse_context_stack(ev.wait.context)]
        trees.append(
            {
                "event_id": ev.event_id,
                "role": ev.role,
                "is_wait": ev.is_wait,
                "frames": frames,
            }
        )
    case.context_trees = trees
