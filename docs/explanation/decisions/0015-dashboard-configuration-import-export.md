# ADR 0015: Dashboard configuration import and export

## Context and Problem Statement

A dashboard's state currently lives in Dash stores and in the URL: the charts
and filters of the open page, the layout options, the header selections and the
hidden activities. There is no way to keep that state as a file, to share a
whole dashboard rather than one link, or to give the pages users build their
own names. The fixed `DASHBOARD_TABS` list has no notion of a user-defined page,
so a saved configuration cannot describe "pages" at all.

## Decision Drivers

1. A configuration file must describe everything that defines a page or the
   whole dashboard: tab names, charts, filters and layout.
2. Both browser file download/upload and server-side named saves are required.
3. Server-side saves are scoped to the logged-in user, with a shared fallback
   when logged out.
4. Importing asks before replacing the current dashboard; the user chooses
   replace, append or cancel.
5. Imported data is untrusted: validate it before it reaches the stores.
6. Existing links and dashboards must keep working.

## Decision

### Named pages

A `dashboard-pages` store holds user-defined pages, each with an id, an editable
name, and its own charts, filters and layout options. The built-in tabs stay;
custom pages are added beside them and can be renamed and deleted in the UI. A
new custom page is empty except for the single add slot of
[ADR 0012](0012-empty-visualization-page.md). The active page supplies the
`created-charts` and `page-filters` views the existing chart code reads; since
Dash permits one writer per output, the existing store callbacks are extended
to write the active page rather than mirrored by a second writer.

### File format

A new `TMonWidgets/PageConfig.py` owns a versioned JSON document:

- format version and dashboard metadata;
- the built-in tab state and active tab;
- custom pages with their names, chart descriptions, filter descriptions with
  selected values, and layout options;
- header actor/object selections and hidden activities;
- default layout options.

`export_config` builds the document from the stores and layout controls;
`import_config` parses it, checks the version, drops unknown visual ids and
columns, caps lists and ignores unknown keys. Invalid input produces a status
message, never a partial dashboard. The chart and filter encodings are the same
ones used for URL carrying, so a file and a link describe the same state.

### Browser and server flows

The toolbar gains an Export button backed by `dcc.Download`, and an Import
control backed by `dcc.Upload`. Both are available in the two T-Mon apps. The
existing Flask server also gains list, save, load and delete endpoints for
named configurations, stored under a per-user directory keyed by the logged-in
username (a shared directory when logged out). Names are sanitised, writes are
atomic, and every saved file passes through the same validation as an uploaded
one.

### Import confirmation

An import, whether from a file or a saved name, opens a confirmation popup with
Replace, Append and Cancel. Replace substitutes the whole dashboard with the
imported one. Append adds the imported custom pages after the existing ones,
assigning new ids to colliding pages and merging non-duplicate filters. Cancel
leaves the dashboard untouched.

## Alternatives Considered

- Keep sharing by URL only: rejected; a whole dashboard with several named
  pages does not fit in one readable link.
- Browser files only, or server saves only: rejected; the user asked for both.
- Silent replace on import: rejected; the user asked to be asked first.
- One shared directory for every server-side save: rejected; the user chose
  per-user storage.

## Consequences

- Custom pages add a store, tab-rendering callbacks and a page model; the
  built-in tabs are unchanged.
- Server-side saves need a writable configuration root and a documented
  per-user layout; the app must never write secrets into a configuration file.
- Imported files are validated once, in `PageConfig`, so file and server flows
  cannot disagree.
- Old URLs and dashboards without custom pages remain valid; exports from them
  simply contain no custom pages.

## Status

- **Status**: Accepted
- **Date**: 2026-11-19
- **Tags**: #configuration #ui #import-export #storage

## See Also

- [ADR 0012](0012-empty-visualization-page.md)
- [ADR 0013](0013-named-visualisation-catalogue.md)
- [ADR 0014](0014-page-level-filters.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
