"""Write analysis reports (JSON, Markdown, HTML) to a directory."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

REPORT_STEM = "analysis"


def _safe_token(value: str, *, max_len: int = 40) -> str:
    token = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return token.strip("_")[:max_len] or "run"


def make_report_slug(
    log_ids: list[str] | None = None,
    database: str | None = None,
    analyzer: str = "analysis",
) -> str:
    """Build a filesystem-safe subdirectory name for one analysis run."""
    lid = "_".join(_safe_token(x, max_len=24) for x in (log_ids or ["nofile"])[:2])
    db = f"_{_safe_token(database, max_len=20)}" if database else ""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_safe_token(analyzer, max_len=16)}_{lid}{db}_{ts}"


def resolve_report_dir(
    report_dir: str,
    *,
    log_ids: list[str] | None = None,
    database: str | None = None,
    analyzer: str = "analysis",
) -> Path:
    """Resolve output directory; auto-append slug when base is exactly `reports`."""
    path = Path(report_dir)
    if path.name == "reports":
        path = path / make_report_slug(log_ids, database, analyzer)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_triple_reports(
    directory: Path,
    *,
    json_body: str,
    md_body: str,
    html_body: str,
    stem: str = REPORT_STEM,
) -> dict[str, Path]:
    """Write analysis.json, analysis.md, analysis.html into directory."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": directory / f"{stem}.json",
        "md": directory / f"{stem}.md",
        "html": directory / f"{stem}.html",
    }
    paths["json"].write_text(json_body, encoding="utf-8")
    paths["md"].write_text(md_body, encoding="utf-8")
    paths["html"].write_text(html_body, encoding="utf-8")
    return paths
