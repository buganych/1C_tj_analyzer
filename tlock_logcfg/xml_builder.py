"""Re-export logcfg XML builder from tj_common.logcfg."""

from tj_common.logcfg import (
    build_logcfg,
    load_default_template,
    load_template,
    parse_platform_version,
    platform_supports_json_zip,
)

__all__ = [
    "build_logcfg",
    "load_default_template",
    "load_template",
    "parse_platform_version",
    "platform_supports_json_zip",
]
