# ADR 0009: Simlet detail view and browser chrome

## Context and Problem Statement

Arriving at `/simlet/<id>` showed the old browser hierarchy headings
("Select an test", "Select an activity", "..") and the sessions as plain folder
buttons. The desired view is a simlet page with only the simlet name at the top,
followed by two tabs, and with activities hidden until a session is opened.

## Decision Drivers

1. The simlet page should read as a detail page, not as a directory listing.
2. Activities belong to a session, so they must not appear at the simlet level.
3. The existing folder-button callback must keep working for real clicks.
4. Styles must be correct on the very first render, not only after a callback.

## Decision

### Layout

- At the simlet level only `current-simlet` (the simlet name) is shown.
  `current-test`, `current-activity`, `parent-directory` and `folders-div` are
  hidden; the old navigation returns once a session or activity is open.
- A persistent panel holds `dcc.Tabs` with two tabs:
  - **general dashboards** — placeholder for whole-simlet dashboards;
  - **sessions dashboard** — the sessions explorer (search, filters, cards).
- Session cards are the folder buttons that open a session, so no separate
  navigation logic was needed.
- The top-level SIMVA / Upload file tabs are hidden while a simlet is selected,
  and shown again at the studies-list root.

### Visibility rule

Selection state is derived from both the path and the browser object
(`actual_test`, `actual_activity`), not from the path alone. A session id that
fails to resolve can leave the path deeper while nothing is selected; that must
not reveal the old placeholders.

### First-render correctness

`init_storage` replaces `browser_div.children` on page load. Style callbacks
writing to the old components would be discarded, so a shared helper
(`simlet_chrome_styles`) computes the styles and `init_storage` applies them
directly to the layout it builds. The callbacks use the same helper for later
navigation.

## Alternatives Considered

- Keep the folder hierarchy and add cards below it: rejected; it repeated the
  sessions and showed placeholders for unselected objects.
- Create the tabs only when a simlet is open: rejected; callback ids would not
  exist in the initial layout and Dash would report missing inputs.
- Rely only on `current-path` to decide visibility: rejected after unresolved
  session ids produced stale headings.

## Consequences

- The simlet page is stable: name, two tabs, then sessions.
- Activities appear only after a session card is clicked.
- Adding new chrome controls must follow the persistent-panel pattern and the
  shared style helper.

## Status

- **Status**: Accepted
- **Date**: 2026-11-18
- **Tags**: #ui #simlet-view #dash #chrome

## See Also

- [ADR 0006](0006-simlet-tiles-architecture.md)
- [ADR 0008](0008-query-parameter-list-explorers.md)
- [Simlet tiles reference](../../reference/simlet-tiles.md)
