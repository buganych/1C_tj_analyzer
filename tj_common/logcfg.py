"""Build logcfg.xml from TLOCK victims with WaitConnections."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from xml.sax.saxutils import escape

from tj_common.models import TjEvent

LOGCFG_STEM = "logcfg"
_PATH_PLACEHOLDER = "!!!ПУТЬ!!!"
_TLOCK_EVENT_RE = re.compile(
    r"\s*<event>\s*"
    r'<eq property="name" value="TLOCK"/>\s*'
    r'<eq property="regions" value="(?:<regions>|[^"]*)"/>\s*'
    r"</event>",
    re.IGNORECASE,
)
_LOG_TAG_RE = re.compile(
    r'(<log\s+location="[^"]*"\s+history="[^"]*")'
    r'(?:\s+format="json"\s+compress="zip")?'
    r"(\s*>)",
    re.IGNORECASE,
)
_PLATFORM_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class RegionStats:
    region: str
    count: int
    avg_wait_sec: int
    max_wait_sec: int


def _duration_sec_int(duration_us: int) -> int:
    return round(duration_us / 1_000_000)


def collect_region_stats(victims: list[TjEvent]) -> list[RegionStats]:
    """Return region stats sorted by count descending."""
    durations: dict[str, list[int]] = defaultdict(list)
    for victim in victims:
        region = victim.regions.strip()
        if not region:
            continue
        durations[region].append(victim.duration_us)

    stats = [
        RegionStats(
            region=region,
            count=len(values),
            avg_wait_sec=_duration_sec_int(round(sum(values) / len(values))),
            max_wait_sec=max(_duration_sec_int(v) for v in values),
        )
        for region, values in durations.items()
    ]
    return sorted(stats, key=lambda item: (-item.count, item.region))


def parse_platform_version(version: str) -> tuple[int, int, int]:
    match = _PLATFORM_VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(
            f"Invalid platform version {version!r}; expected format like 8.3.24 or 8.3.24.1500"
        )
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def platform_supports_json_zip(version: str) -> bool:
    """True when platform is newer than 8.3.24 (json+zip log format supported)."""
    major, minor, patch = parse_platform_version(version)
    return (major, minor, patch) > (8, 3, 24)


def _render_tlock_events(region_stats: list[RegionStats]) -> str:
    blocks: list[str] = []
    for item in region_stats:
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


def build_logcfg(
    template: str,
    *,
    location_path: str,
    region_stats: list[RegionStats],
    platform_version: str,
) -> str:
    if not region_stats:
        raise ValueError("No TLOCK regions with WaitConnections found")

    xml = template.replace(_PATH_PLACEHOLDER, location_path)

    tlock_block = _render_tlock_events(region_stats)
    xml, replaced = _TLOCK_EVENT_RE.subn(lambda _m: "\n" + tlock_block, xml, count=1)
    if replaced == 0:
        raise ValueError("Template does not contain TLOCK event with regions placeholder")

    if not platform_supports_json_zip(platform_version):
        xml = _LOG_TAG_RE.sub(r"\1\2", xml)

    return xml


def load_template(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def load_default_template() -> str:
    bundled = resources.files("tj_common.data") / "logcfg_шаблон.xml"
    return bundled.read_text(encoding="utf-8")


def write_logcfg_report_from_stats(
    directory: Path,
    region_stats: list[RegionStats],
    *,
    location_path: str = _PATH_PLACEHOLDER,
    platform_version: str = "8.3.25",
    template: str | None = None,
    stem: str = LOGCFG_STEM,
) -> Path | None:
    """Write logcfg.xml into report directory; return path or None if no regions."""
    if not region_stats:
        return None

    template_text = template if template is not None else load_default_template()
    xml_body = build_logcfg(
        template_text,
        location_path=location_path,
        region_stats=region_stats,
        platform_version=platform_version,
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem}.xml"
    path.write_text(xml_body, encoding="utf-8")
    return path


def write_logcfg_report(
    directory: Path,
    victims: list[TjEvent],
    *,
    location_path: str = _PATH_PLACEHOLDER,
    platform_version: str = "8.3.25",
    template: str | None = None,
    stem: str = LOGCFG_STEM,
) -> Path | None:
    """Write logcfg.xml into report directory; return path or None if no regions."""
    return write_logcfg_report_from_stats(
        directory,
        collect_region_stats(victims),
        location_path=location_path,
        platform_version=platform_version,
        template=template,
        stem=stem,
    )
