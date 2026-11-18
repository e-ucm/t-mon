# ADR 0008: Query-parameter driven list explorers

## Context and Problem Statement

The SIMVA front-end offers filtering, sorting and pagination on its Simlets and
Sessions lists. T-Mon's original tile grid showed every loaded simlet at once
and its session folders were plain buttons, with no search or paging.

## Decision Drivers

1. Match the parameter names and sort choices used by `simva-front` and the
   SimVA API.
2. Make a filtered list shareable through the browser URL.
3. Avoid extra API calls: the SimVA browser already loads the user's simlets.
4. Keep Dash callback inputs valid when controls are created by callbacks.

## Decision

### Simlet list (`SimletExplorer`)

- Parameters mirror `simva-front`: `status`, `searchString`, `skip`, `limit`,
  `orderBy`, `order`, `searchTags`. Defaults:
  `status=active&skip=0&limit=9&orderBy=id&order=asc`.
- State lives in `dcc.Location(id='url').search`, so a filtered view is a
  shareable link. The pathname (for example `/simlet/1`) is never rewritten by
  the explorer.
- Filtering, sorting and pagination are applied to `TMonWidgets.accepted_studies`
  in memory; no request is made per filter change.
- Unknown or malformed values fall back to defaults, so hand-edited links are
  safe.
- Controls are a **persistent** component in every layout state. Dash's
  `suppress_callback_exceptions` is enabled and the panel is only shown or
  hidden by style; this avoids "nonexistent object in callback" errors.

### Sessions list (`SessionExplorer`)

- Uses the same names and sort options, with `status` values
  `All / active / inactive (Paused) / terminated (Finished)` and four sessions
  per page by default.
- Skip is kept in a `dcc.Store` rather than the URL: the SimVA browser changes
  the pathname when a session is opened, so session filters are not linkable.
- Session cards are pattern-matching `folder-button` components, so opening one
  goes through the existing browser selection callback.

### Guard against spurious navigation

`update_browser` ignores folder/file button events whose `n_clicks` are all 0.
Re-rendering a filtered list recreates its buttons; without this guard the
render was treated as a click and navigated into a session.

## Alternatives Considered

- Call `/simlets?…` and `/simlets/<id>/sessions?…` on every change: rejected;
  the browser already holds the data and this would duplicate requests.
- Infinite scroll as in `simva-front`: rejected; Dash has no equivalent
  without custom JavaScript, so explicit Previous/Next controls were chosen.
- Store filters only in component state: rejected for the simlet list because
  links would not be shareable.

## Consequences

- The same vocabulary and defaults are used across SIMVA, T-Mon and the API.
- Sharing a URL reproduces the exact simlet filter/pagination state.
- Session state is intentionally local to the current browser selection.
- Both explorers need their ids present in the initial layout; new controls
  must follow the persistent-panel pattern.

## Status

- **Status**: Accepted
- **Date**: 2026-11-18
- **Tags**: #i18n #filters #pagination #dash #url-state

## See Also

- [ADR 0006](0006-simlet-tiles-architecture.md) — simlet tiles
- [ADR 0007](0007-shared-translations.md) — shared translations
- [Simlet tiles reference](../../reference/simlet-tiles.md)
