from dash import html

from TMonWidgets import SimvaBrowserWidget as BrowserWidget


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


def test_root_section_shows_all_simlets():
    studies = [
        {'simlet_id': 'a', 'simlet_name': 'simlet A'},
        {'simlet_id': 'b', 'simlet_name': 'simlet B'},
    ]
    section = BrowserWidget.render_simlet_section(studies, _get_id)

    headings = [child for child in _walk(section) if isinstance(child, html.H3)]
    assert any(heading.children == 'Simlets' for heading in headings)

    links = [child for child in _walk(section) if isinstance(child, html.A)]
    assert [link.href for link in links] == [
        '/simlet/a',
        '/simlet/b',
    ]
    assert [link.children.children[0].children for link in links] == ['simlet A', 'simlet B']


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


def test_dashboard_simlet_url_maps_to_browser_path():
    path = BrowserWidget.browser_path_from_dashboard_url(
        '/simlet/1', 'output/')
    assert path == 'output/1/'
    assert BrowserWidget.browser_path_from_dashboard_url('/', 'output/') == 'output/'
    assert BrowserWidget.browser_path_from_dashboard_url('/dashboard/', 'output/') == 'output/'


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
