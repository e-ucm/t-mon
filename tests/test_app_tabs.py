import TMonSimvaApp


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and hasattr(children, "children"):
        yield from _walk(children)


def test_top_tabs_select_upload_or_simva():
    ids = [getattr(component, "id", None)
           for component in _walk(TMonSimvaApp.app.layout)]
    assert "app-tabs" in ids
    assert "simva-panel" in ids
    assert "upload-panel" in ids
    # The upload control and the log are shared by both modes.
    assert "upload-data" in ids
    assert "content" in ids

    tabs = next(component for component in _walk(TMonSimvaApp.app.layout)
                if getattr(component, "id", None) == "app-tabs")
    assert tabs.value == "simva"
    assert [tab.label for tab in tabs.children] == ["SIMVA", "Upload file"]


def test_switch_mode_shows_one_panel_at_a_time():
    simva, upload = TMonSimvaApp.switch_mode("upload")
    assert simva["display"] == "none"
    assert upload["display"] == "block"

    simva, upload = TMonSimvaApp.switch_mode("simva")
    assert simva["display"] == "block"
    assert upload["display"] == "none"
