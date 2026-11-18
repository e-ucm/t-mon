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
    tabs, simva, upload = TMonSimvaApp.switch_mode("upload", "/")
    assert tabs["display"] == "flex"
    assert tabs["flexDirection"] == "row"
    assert simva["display"] == "none"
    assert upload["display"] == "block"

    tabs, simva, upload = TMonSimvaApp.switch_mode("simva", "/")
    assert tabs["display"] == "flex"
    assert tabs["flexDirection"] == "row"
    assert simva["display"] == "block"
    assert upload["display"] == "none"


def test_simlet_selection_hides_the_mode_tabs():
    tabs, simva, upload = TMonSimvaApp.switch_mode("upload", "/simlet/1")
    assert tabs["display"] == "none"
    assert simva["display"] == "block"
    assert upload["display"] == "none"

    # Deeper selections keep the simlet in the path; the tabs stay hidden.
    assert TMonSimvaApp.simlet_selected("/simlet/1/sessions/2/") is True
    assert TMonSimvaApp.simlet_selected("/1/sessions/2/") is True
    assert TMonSimvaApp.simlet_selected("/dashboard/tab=home_tab") is False
    assert TMonSimvaApp.simlet_selected("/") is False
    assert TMonSimvaApp.simlet_selected(None) is False

    # Going back up to the studies list brings them back.
    tabs, _, _ = TMonSimvaApp.switch_mode("simva", "/")
    assert tabs["display"] == "flex"
    assert tabs["flexDirection"] == "row"
