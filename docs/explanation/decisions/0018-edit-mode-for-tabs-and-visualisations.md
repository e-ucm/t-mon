# ADR 0018: Edit mode for tabs and visualisations

## Context and Problem Statement

T-Mon can already build a dashboard. A user-named page starts as an empty canvas
with one `+` slot ([ADR 0012](0012-empty-visualization-page.md)), named pages can
be added, renamed and deleted ([ADR 0015](0015-dashboard-configuration-import-export.md)),
and the default dashboard is described by a JSON file whose tab, graph and axis
labels are data rather than translations
([ADR 0017](0017-user-defined-default-dashboard-definition.md)). Charts created
in the UI are stored as `{type, x, y, aggregation}` specs; `ChartBuilder.describe()`
derives their title and Plotly derives axis labels from the column names.

What is missing is a coherent way to *edit* what has already been placed:

- mutation controls are scattered through the read-only view — a `New page` /
  `Rename page` / `Delete page` group in the header, a `+` slot on each page and
  per-item `Remove` buttons — so there is no clear boundary between viewing and
  changing a dashboard, and a stray click can alter it;
- the `+` control that creates a new tab is not guaranteed to be present on every
  tab, so a user cannot always add a tab from where they are working;
- once a graph is on a page it cannot be changed: its type, data columns and
  aggregation are fixed, and its title and axis labels are either generated from
  column names (`describe()`) or come from the deployed definition file
  ([ADR 0017](0017-user-defined-default-dashboard-definition.md)). Renaming a
  graph or an axis requires editing Python or JSON, which changes every
  deployment using that file.

The user wants an explicit **edit mode** for already-added tabs and
visualisations. In that mode the new-tab `+` button must always be shown, a tab
or a visualisation must be removable from the layout, and a graph and its labels
must be editable.

## Decision Drivers

1. Provide a single, explicit edit-mode toggle that separates viewing a
   dashboard from changing it.
2. In edit mode, always show the new-tab `+` button, whatever the active tab.
3. In edit mode, expose a remove control for each removable tab and for each
   visualisation, in place in the layout.
4. In edit mode, allow editing a graph — its type, data columns and aggregation —
   and editing its labels: the graph title and the x/y axis labels.
5. Labels typed by the user are data and are stored with the graph; they are not
   i18n lookups and never write to the deployed definition file
   ([ADR 0017](0017-user-defined-default-dashboard-definition.md)).
6. The reserved `xapi_data` tab and the built-in/Create tab cannot be removed;
   the `xapi_data` label stays `xapi data` as required by ADR 0017.
7. Reuse the existing state and helpers — `dashboard-pages`, `created-charts`,
   `page-filters`, `dashboard_tab_children()`, `render_page_items()` and the
   single-writer `update_page_state` callback. Do not introduce a second editing
   state model.
8. Keep [ADR 0015](0015-dashboard-configuration-import-export.md) config files
   and shared links working; any new graph fields are optional and backward
   compatible.
9. Follow the shared-helper first-render pattern
   ([ADR 0009](0009-simlet-detail-view.md),
   [ADR 0012](0012-empty-visualization-page.md)) and take all UI chrome text from
   the translation catalogue ([ADR 0007](0007-shared-translations.md)).

## Decision

### Edit mode toggle and state

Add an **Edit** button to the dashboard header backed by a boolean `edit-mode`
store. The button toggles the store; `edit-mode` is a transient UI flag and is
not itself saved in a configuration file — only the changes it enables are
persisted.

A shared layout helper reads `edit-mode` and decides which controls are visible.
In view mode the dashboard is the clean visualisation layout: no remove buttons,
no new-tab `+` and no graph-edit controls. In edit mode those controls are shown.
Because the same helper builds the initial layout and is reused by callbacks,
the controls exist on first render and stay in sync on later updates, as in ADR
0012.

### New tab `+` always visible in edit mode

When edit mode is active, a `+` tab is rendered as the last entry of the tab bar
(`t-mon-tabs`). It is present regardless of the active tab, including the
built-in and `xapi_data` tabs. Clicking it runs the existing new-page flow
(`page-add`): a named, empty page with the single add slot of ADR 0012. The
header `page-add` button and the tab-bar `+` are two entry points to the same
creation path, not two models.

In view mode the `+` tab is not rendered; the `+` add slot for visualisations
inside a page follows the same rule and appears only in edit mode.

### Removing tabs and visualisations in the layout

Edit mode adds remove affordances tied to the active tab's store key
(`page_key()` / `items_for_key()`):

- each removable (user-defined) tab carries a remove control on the tab itself;
  the built-in/Create tab and the reserved `xapi_data` tab carry none;
- each chart and filter on the active page shows its remove button (reusing the
  existing `item-remove` / `chart-remove` ids) instead of hiding it in the header.

Removing a tab uses the confirmation popup pattern of ADR 0015 so that losing a
page with content is deliberate; removing a single visualisation is immediate
and reports a status message. Removing the active tab selects a remaining tab.
All removals go through the single writer `update_page_state`, which updates
`dashboard-pages`, `created-charts` and `page-filters` together so a store and
the buttons that draw it cannot disagree.

### Editing a graph and its labels

Each chart in edit mode gains an **Edit** control. Clicking it reopens the
creation popup (`item_modal_layout()`) pre-filled with that chart's spec —
`type`, `x`, `y` and `aggregation` — and, on confirmation, the spec is replaced
in the active tab's charts. The popup is the one editor for both creation and
editing; it is not duplicated. The type choices remain the registered graph
types from code
([ADR 0017](0017-user-defined-default-dashboard-definition.md)).

The popup gains three label fields stored on the graph spec:

| Field | Meaning |
|---|---|
| `title` | User-defined graph title. |
| `x_label` | User-defined x axis label. |
| `y_label` | User-defined y axis label. |

These fields are optional. `ChartBuilder.normalise_spec()` accepts and preserves
them, `encode_spec()` / decode carry them in links, and ADR 0015 config
validation permits them. When a label is present, `build_chart()` passes it to
Plotly for the figure title and axis labels; when it is absent, the current
behaviour is unchanged, so `describe()` still derives a title and column names
still label the axes. Existing links, configs and the shipped definition file
therefore render exactly as before.

Labels are user text, read from the spec and passed straight to Dash. No
`I18n.t()` lookup is made for a graph title or axis label, and edit mode never
writes back to `default-dashboard.json`. A graph materialised from the default
definition starts with the JSON labels; editing it stores a user override in the
dashboard state, which is what ADR 0015 export and shared links carry.

Filters use the same popup and are edited in the same way; their selected values
are preserved.

### Protected tabs and compatibility

- The reserved `xapi_data` tab and the built-in/Create tab cannot be removed.
  The `xapi_data` label stays `xapi data`; edit mode may add Markdown but may not
  rename or remove that tab (ADR 0017).
- ADR 0015 file format and version are unchanged apart from the three optional
  chart label fields. Old configurations and links remain valid and render with
  derived labels until a user edits them.
- New chrome strings (the Edit/Remove/Edit-graph buttons and tooltips) are added
  to the shared locale files; graph, x and y labels typed by the user are not.

## Alternatives Considered

- **Always-on remove and edit buttons**: rejected; they clutter the read-only
  dashboard and make accidental changes likely.
- **A separate edit page or route**: rejected; it drops the dashboard context
  and adds a step for every change, as with the rejected creation page in ADR
  0012.
- **Edit the deployed `default-dashboard.json` from the UI**: rejected; one user's
  edit would change every deployment using that file. Edit mode changes user
  state only.
- **Keep deriving labels from column names or i18n keys**: rejected; the user
  must be able to name a graph and its axes without changing Python or a global
  translation file (ADR 0017).
- **A separate editing state model**: rejected; the ADR 0015 stores and the
  single-writer callback already own the dashboard state.

## Consequences

- The dashboard gains an edit toggle, an `edit-mode` store, a tab-bar `+`
  control, per-tab and per-item remove controls and an Edit control per chart,
  plus the three label fields in the item popup.
- Chart specs gain optional `title`, `x_label` and `y_label` fields. Encoding,
  decoding, URL carrying and ADR 0015 config validation must accept them;
  behaviour without them is unchanged.
- The read-only dashboard becomes a clean view, and the single-writer callback
  remains the only place that mutates page, chart and filter state.
- New i18n keys are needed for the edit-mode chrome in all supported locales;
  user-authored graph and axis labels deliberately bypass i18n.
- Tests must cover: edit-mode visibility of controls, the `+` tab being present
  on every tab in edit mode, tab and visualisation removal, protection of the
  built-in and `xapi_data` tabs, graph spec editing, persistence of the three
  labels, and backward compatibility with specs and configs that omit them.

## Status

- **Status**: Accepted
- **Date**: 2026-11-19
- **Tags**: #ui #edit-mode #dashboard #visualization #layout

## See Also

- [ADR 0007](0007-shared-translations.md)
- [ADR 0009](0009-simlet-detail-view.md)
- [ADR 0012](0012-empty-visualization-page.md)
- [ADR 0014](0014-page-level-filters.md)
- [ADR 0015](0015-dashboard-configuration-import-export.md)
- [ADR 0017](0017-user-defined-default-dashboard-definition.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
