from tj_common.report.json_out import analysis_to_dict, render_json as _render_json
from tj_common.report.labels import TTIMEOUT_LABELS


def render_json(result, indent=2, labels=TTIMEOUT_LABELS):
    return _render_json(result, indent=indent, labels=labels)
