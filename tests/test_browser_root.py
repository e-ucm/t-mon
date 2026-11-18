from dash import html
from dash.exceptions import PreventUpdate

import dash

from TMonWidgets import SimvaBrowserWidget as BrowserWidget
from TMonWidgets import SimletExplorer
from TMonWidgets.TMonWidget import render_simlet_tiles


class _FakeOidc:
    def __init__(self, logged_in):
        self.user_loggedin = logged_in


class _FakeFlask:
    def __init__(self, logged_in):
        self.oidc = _FakeOidc(logged_in)


def _get_id(simlet, type, name):
    return simlet.get(f'{type}_{name}')


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and hasattr(children, "children"):
        yield from _walk(children)


def test_root_section_shows_the_explorer():
    studies = [
        {'simlet_id': 'a', 'simlet_name': 'simlet A'},
        {'simlet_id': 'b', 'simlet_name': 'simlet B'},
    ]
    section = BrowserWidget.render_simlet_section(studies, _get_id, '?status=archived&limit=9')
    assert section.children == 'Simlets'

    panel = BrowserWidget.render_simlet_explorer_panel(
        studies, '?status=archived&limit=9')
    assert panel.id == 'simlet-explorer-panel'
    ids = [getattr(child, 'id', None) for child in _walk(panel)]
    assert 'simlet-browser-grid' in ids
    for name in ('status', 'search', 'sort', 'tags', 'limit', 'prev', 'next', 'info'):
        assert f'simlet-explorer-{name}' in ids
    status = next(child for child in _walk(panel)
                  if getattr(child, 'id', None) == 'simlet-explorer-status')
    assert status.value == 'archived'

    filters = SimletExplorer.parse_simlet_query('?status=archived&limit=9')
    page, total = SimletExplorer.apply_simlet_filters(studies, filters)
    assert total == 0  # neither study is archived
    active = SimletExplorer.parse_simlet_query('')
    page, total = SimletExplorer.apply_simlet_filters(studies, active)
    assert total == 2
    links = [child for child in _walk(render_simlet_tiles(page)) if isinstance(child, html.A)]
    assert [link.href for link in links] == ['/simlet/a', '/simlet/b']


def test_navigation_chrome_is_hidden_only_at_root(monkeypatch):
    monkeypatch.setattr(BrowserWidget, 'flask', _FakeFlask(True))
    hidden = ({'display': 'none'},) * 4
    visible = ({'display': 'block'},) * 4
    assert BrowserWidget.toggle_browser_chrome('output/') == hidden
    assert BrowserWidget.toggle_browser_chrome(None) == hidden
    assert BrowserWidget.toggle_browser_chrome('output/simlet-id/') == visible

    # A logged-out visitor never sees the browser navigation, including `..`.
    monkeypatch.setattr(BrowserWidget, 'flask', _FakeFlask(False))
    assert BrowserWidget.toggle_browser_chrome('output/simlet-id/') == hidden


def test_simlet_explorer_panel_is_shown_only_on_the_studies_list(monkeypatch):
    monkeypatch.setattr(BrowserWidget, 'flask', _FakeFlask(True))
    assert BrowserWidget.toggle_simlet_explorer('output/', None) == {'display': 'block'}
    assert BrowserWidget.toggle_simlet_explorer(None, None) == {'display': 'block'}
    assert BrowserWidget.toggle_simlet_explorer('output/1/', None) == {'display': 'none'}
    monkeypatch.setattr(BrowserWidget, 'flask', _FakeFlask(False))
    assert BrowserWidget.toggle_simlet_explorer('output/', None) == {'display': 'none'}


def test_dashboard_simlet_url_maps_to_browser_path():
    path = BrowserWidget.browser_path_from_dashboard_url(
        '/simlet/1', 'output/')
    assert path == 'output/1/'
    assert BrowserWidget.browser_path_from_dashboard_url('/', 'output/') == 'output/'
    assert BrowserWidget.browser_path_from_dashboard_url('/dashboard/', 'output/') == 'output/'


def _tile_texts(component):
    if isinstance(component, str):
        yield component
        return
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _tile_texts(child)
    elif children is not None:
        yield from _tile_texts(children)


def test_root_section_keeps_simlet_metadata():
    # The normaliser used to keep only id/name, which left the tiles unable to
    # show the dates, counts and tags the API returned.
    studies = [{
        'simlet_id': 1,
        'simlet_name': 'test',
        'sessions': [1],
        'groups': [],
        'tags': [{'tag_name': 'test'}],
        'createdAt': '2026-11-18T10:24:54.201Z',
        'updatedAt': '2026-11-18T10:24:54.201Z',
    }]
    page, total = SimletExplorer.apply_simlet_filters(
        studies, SimletExplorer.parse_simlet_query(''))
    assert total == 1
    texts = list(_tile_texts(render_simlet_tiles(page)))
    for expected in ("Created at: 2026/11/18", "Updated at: 2026/11/18",
                     "Sessions: 1", "Groups: 0", "Participants: 0", "Tags:", "test"):
        assert expected in texts


class _Triggered:
    def __init__(self, prop_id):
        self.triggered = [{'prop_id': prop_id}]


class _FakeBrowser:
    def __init__(self):
        self.current_path = 'output/1/'
        self.base_path = 'output/'


def test_redrawing_session_buttons_does_not_navigate(monkeypatch):
    # Changing the Sessions filter re-creates its folder buttons with n_clicks
    # still at zero. That must not be treated as a click into a session.
    fake = _FakeBrowser()
    monkeypatch.setattr(BrowserWidget, 'browser', fake, raising=False)
    monkeypatch.setattr(dash, 'callback_context',
                        _Triggered('{"type":"folder-button","index":"11/"}.n_clicks'))
    try:
        BrowserWidget.update_browser(
            0, [0], [], 0, None, 'output/1/', '/simlet/1', '', None, None, 'simva')
    except PreventUpdate:
        pass
    else:
        raise AssertionError('a button redraw must not navigate')
    assert fake.current_path == 'output/1/'


def test_upload_requires_login(monkeypatch):
    monkeypatch.setattr(BrowserWidget, 'flask', _FakeFlask(False))
    assert BrowserWidget.upload_allowed('upload') is False
    button, style, notice = BrowserWidget.login_logout_button_displayed(None, 'upload')
    assert button == 'Login'
    assert style['display'] == 'none'
    assert 'log in' in notice.lower()

    monkeypatch.setattr(BrowserWidget, 'flask', _FakeFlask(True))
    assert BrowserWidget.upload_allowed('upload') is True
    button, style, notice = BrowserWidget.login_logout_button_displayed(None, 'upload')
    assert button == 'Logout'
    assert style['display'] == 'block'
    assert notice == ''
