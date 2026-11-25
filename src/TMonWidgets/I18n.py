"""
Small i18n layer for T-Mon, following the SIMVA front-end's locale files.

Translations live in ``src/locales/<language>.json``. The active language comes
from the ``lng`` query parameter (set by the header selector, which reloads the
page), then from the Flask session, then English. Callbacks run inside a
request context, so ``t()`` there picks up the selected language.
"""

import json
import os

from flask import has_request_context, request, session

DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Español',
    'fr': 'Français',
}

_LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locales')
_TRANSLATIONS = {}
for _language in SUPPORTED_LANGUAGES:
    _path = os.path.join(_LOCALES_DIR, f'{_language}.json')
    if os.path.isfile(_path):
        with open(_path, encoding='utf-8') as _handle:
            _TRANSLATIONS[_language] = json.load(_handle)


def language_from_search(search):
    """Read ``lng`` from a URL query string, ignoring unknown languages."""
    if not search:
        return None
    text = str(search).lstrip('?')
    # Flask's request.args already gives just the value; the URL search gives
    # the whole `lng=xx` pair. Accept either form.
    if text in SUPPORTED_LANGUAGES:
        return text
    for part in text.split('&'):
        if part.startswith('lng=') and part[4:] in SUPPORTED_LANGUAGES:
            return part[4:]
    return None


def current_language():
    """The language for the current request."""
    if has_request_context():
        language = language_from_search(request.args.get('lng'))
        if language:
            return language
        stored = session.get('lang')
        if stored in SUPPORTED_LANGUAGES:
            return stored
    return DEFAULT_LANGUAGE


def set_language(language):
    """Remember the chosen language in the Flask session."""
    if language in SUPPORTED_LANGUAGES and has_request_context():
        session['lang'] = language


def translate(key, language=None, **values):
    """Translate ``key`` into ``language`` (or the current one), English fallback."""
    if language not in SUPPORTED_LANGUAGES:
        language = current_language()
    text = (_TRANSLATIONS.get(language, {}).get(key)
            or _TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, key))
    return text.format(**values) if values else text


def t(key, **values):
    """Translate ``key`` into the current language, falling back to English."""
    return translate(key, None, **values)
