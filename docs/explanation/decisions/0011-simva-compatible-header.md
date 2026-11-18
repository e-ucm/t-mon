# ADR 0011: SIMVA-compatible application header

## Context and Problem Statement

T-Mon's header used its own visual language, while the rest of the ecosystem
was moving toward the SIMVA front-end look. Users also saw both "Logged in as …"
and "Account", and the header text was hard-coded in English.

## Decision Drivers

1. Visual consistency with `simva-front`.
2. Keep the existing Dash callback ids stable.
3. Work behind proxies that do not serve `/assets/...`.
4. Align language handling with simva-front.

## Decision

### Layout and styling

- Sticky 40px bar, orange `#ff8f22`, bold black sans-serif text, dark drop
  shadow, `justify-content: space-between` (`className='header'`).
- Left: T-Mon logo and "Txmon - The xAPI Trace Monitor", linking to the T-Mon
  home page.
- Right: language selector, Contact us (e-UCM), signed-in username and a black
  Login/Logout pill. The account item shows **only the username** and is hidden
  when logged out; the old connection-status node remains hidden as a callback
  target.
- Top-level SIMVA / Upload file tabs are hidden while a simlet is selected
  (see [ADR 0009](0009-simlet-detail-view.md)).

### Assets

User, power, information and e-UCM icons were copied from `simva-front` into
`src/assets/` and embedded as data URIs by `BrandAssets.py`, like the logo. No
runtime `/assets/...` request is needed.

### Language

`TMonWidgets/I18n.py` loads `src/locales/<lng>.json`. The header selector stores
the choice in the Flask session and reloads with `lng` in the URL, so the
selection and the active translation survive navigation. Keys are canonical
simva keys ([ADR 0007](0007-shared-translations.md)).

## Alternatives Considered

- Reference `simva-front/public/images/...` directly: rejected; sibling
  checkouts are not available in T-Mon's Docker image.
- Keep the original white button chip and larger type: rejected; it did not
  match the SIMVA bar.
- Show both the account label and the connection status: rejected as redundant.

## Consequences

- Both T-Mon apps share one header builder; only the SIMVA app passes
  `with_login=True`.
- Callback ids (`main-login`, `login-logout-button`, `account-button`,
  `account`, `login-logout`, `connection-status`) are unchanged.
- New header text must come from the translation catalogue, not a literal.

## Status

- **Status**: Accepted
- **Date**: 2026-11-18
- **Tags**: #header #ui #i18n #assets

## See Also

- [ADR 0007](0007-shared-translations.md)
- [ADR 0009](0009-simlet-detail-view.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
