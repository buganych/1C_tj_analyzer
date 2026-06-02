from tj_common.report.labels import TTIMEOUT_LABELS
from tj_common.report.text import render_text as _render_text


def render_text(result, labels=TTIMEOUT_LABELS):
    return _render_text(result, labels=labels)
