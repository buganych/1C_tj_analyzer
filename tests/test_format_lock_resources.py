from tj_common.report.event_report import format_lock_resources


def test_format_lock_resources_multiline_fields():
    regions = "InfoRg40.DIMS"
    locks = 'InfoRg40.DIMS Exclusive Fld41="А" Fld42="Б"'
    text = format_lock_resources(regions, locks)
    assert "InfoRg40.DIMS Exclusive" in text
    assert 'Fld41="А"' in text
    assert 'Fld42="Б"' in text
    assert "    Fld41=" in text
    assert "    Fld42=" in text


def test_format_lock_resources_shared():
    text = format_lock_resources(
        "InfoRg40.DIMS",
        "InfoRg40.DIMS Shared Fld41=1",
    )
    assert "InfoRg40.DIMS Shared" in text
    assert "    Fld41=" in text
