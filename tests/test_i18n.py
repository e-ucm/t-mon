"""Tests for the lightweight translation layer and the compact header."""

from dash import dcc, html, no_update

import TMonSimvaApp
from TMonWidgets import I18n, TMonWidget


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None and hasattr(children, "to_plotly_json"):
        yield from _walk(children)


def test_language_from_search_accepts_query_string_and_bare_value():
    assert I18n.language_from_search('?lng=es') == 'es'
    assert I18n.language_from_search('lng=fr') == 'fr'
    assert I18n.language_from_search('es') == 'es'
    assert I18n.language_from_search('?status=active&lng=fr') == 'fr'
    assert I18n.language_from_search('?lng=xx') is None
    assert I18n.language_from_search(None) is None


def test_translations_follow_the_request_language():
    server = TMonSimvaApp.app.server
    with server.test_request_context('/?lng=es'):
        assert I18n.current_language() == 'es'
        assert I18n.t('header.contact.title') == 'Contáctanos'
        assert I18n.t('simlets.next') == 'Siguiente'
    with server.test_request_context('/?lng=fr'):
        assert I18n.t('header.contact.title') == 'Contactez-nous'
    with server.test_request_context('/'):
        assert I18n.current_language() == 'en'
        assert I18n.t('header.contact.title') == 'Contact us'
        # Missing keys fall back to English rather than showing the key.
        assert I18n.t('not.a.key') == 'not.a.key'


def test_header_is_compact_and_has_a_language_selector():
    header = TMonWidget.TMonSimvaHeader
    assert header.style['height'] == '40px'
    links = [child for child in _walk(header) if isinstance(child, html.A)]
    contact = next(child for child in links
                   if child.href == 'https://www.e-ucm.es/es/people/')
    assert contact.children[0].style['height'] == '1.2rem'

    language = next(child for child in _walk(header)
                    if getattr(child, 'id', None) == 'header-language')
    assert isinstance(language, dcc.Dropdown)
    assert [option['value'] for option in language.options] == ['en', 'es', 'fr']

    account_item = next(child for child in _walk(header)
                        if getattr(child, 'id', None) == 'header-account-item')
    assert 'Account' not in [text for text in _walk(account_item)
                             if isinstance(text, str)]
    # The username label is hidden; only the account item shows it.
    status = next(child for child in _walk(header)
                  if getattr(child, 'id', None) == 'connection-status')
    assert status.style['display'] == 'none'
    # The static selector starts unset; the callback fills it from the session.
    assert language.value is None


def test_language_choice_is_remembered_across_loads():
    from flask import session

    server = TMonSimvaApp.app.server
    with server.test_request_context('/'):
        session['lang'] = 'es'
        # An unset dropdown on a fresh page keeps the remembered language;
        # it must not reload with the English default.
        href, value, contact, simva, upload = TMonSimvaApp.change_language(None, None)
        assert href is no_update
        assert value == 'es'
        assert contact == 'Contáctanos'
        assert simva == 'SIMVA'
        # A genuine user change reloads with the new language in the URL.
        href, value, contact, _, _ = TMonSimvaApp.change_language('fr', None)
        assert href == '?lng=fr'
        assert value == 'fr'
        assert contact == 'Contactez-nous'
