# ADR 0024: Edit floater for creation, titles, configuration and layout

## Context and Problem Statement

ADR 0018 introduced an explicit edit mode for tabs and visualisations. In the
current dashboard, everything that changes what a user sees is spread across the
page and the header:

- the `New page` / `Rename page` / `Delete page` group sits in the dashboard
  header (`dashboard-page-controls`), revealed by the **Edit** toggle;
- creation and editing of a visualisation or filter happen in a top-centred
  modal (`item-modal`, ADR 0012, ADR 0019, ADR 0021), opened by the `+` slots
  and per-item **Edit** buttons;
- the legacy `Create a visualisation` row (`chart-creator-controls`) is always
  visible in the Create tab;
- the graph layout controls (`graph-layout`, `graph-rows`, `graph-columns`,
  `graph-page`, `graph-split-x`, `graph-split-y`) and the configuration controls
  (save/load/import/export/delete/refresh, ADR 0015) are permanently rendered
  rows in the dashboard.

The result is a read-only view cluttered with editing machinery, several
unrelated ways to reach the same actions, and no single place to configure a
dashboard. The SIMVA front-end (`../simva-front/`) already has the interaction
model to follow: `new_element.floating` forms and the `iframe_floating` panel are
hidden by default and toggled into view by a button
(`Utils.toggleFormInFloating()`), so forms appear in one floating card instead
of being laid out inline.

## Decision Drivers

1. Keep a clear boundary between viewing and changing a dashboard: the **Edit**
   toggle of ADR 0018 remains the single entry point for edit mode and reveals
   the other edit controls (new-tab `+`, add slots, remove buttons).
2. Follow the `simva-front` floater interaction model: one card with window
   chrome, toggled into view by buttons instead of controls being permanently
   visible inline.
3. Keep **one** floater for all editing tasks, with one panel per task rather
   than one window per task.
4. Give each task its own entry button: Edit dashboard, Add/edit page,
   Get/load/export configuration and Edit layout. The Edit button itself only
   toggles edit mode; it never opens the floater.
5. The three section buttons work from view mode too: they switch edit mode on
   and open their panel. The floater's `×` closes only the window; Edit/Done is
   the single way out of edit mode.
6. Provide one editor for both creation and editing of visualisations and
   filters, including their titles and axis labels (ADR 0012, ADR 0018, ADR
   0021), with no second state model.
7. Move **all** configuration into the floater — named pages, configuration
   save/load/import/export (ADR 0015) **and the graph layout controls** — so the
   layout is configured where the rest of the dashboard is configured.
8. Keep the existing Dash ids and stores for the mutation logic (`item-add`,
   `page-add`, `page-rename`, `page-delete`, `config-*`, `graph-layout*`), so
   `update_page_state`, `apply_config_layout`, `handle_config_actions` and
   `update_output` keep working unchanged. Only where the controls are rendered
   changes.
9. Keep the ADR 0015 configuration format, shared links, URL parameters and
   per-user saved names unchanged; the floater is UI chrome, not a new state
   model.
10. Use inline styles for the floater, as for the header and the previous modal
    (ADR 0011): deployed proxies may not serve `/assets/...`, so CSS classes
    alone are not reliable.
11. Take all floater chrome text from the shared translation catalogue
    (ADR 0007); user-authored titles and labels remain data on the chart spec,
    not i18n keys (ADR 0018).

## Decision

### One floater, four panels

Add `edit_floater_layout()` to `TMonWidget.py`, producing a single
`edit-floater` **window** that mirrors `simva-front`'s `partials/iframe.ejs`: a
fixed full-viewport `.iframe_floating` container with a `.backdrop`, a centred
white `.floater` card (`calc(100vw - 32px)`, rounded, scrollable), a gray `×`
`.iframe_floating_close` in the card's top-right corner, and the form content in
an `.iframe_content` body with its 48px top padding. The class names match
simva-front; the styles are inline because of driver 10. The window is a
standalone overlay at the app level: it lives at the top of `TMonBody`, outside
`output-t-mon`, so it sits above the whole page rather than only the dashboard
panel.

Its content is four sibling panels, one shown at a time:

| Panel | Mode | Contents |
|---|---|---|
| `edit-floater-create` | `create` | Add/edit a visualisation or filter, with title and axis labels |
| `edit-floater-pages` | `pages` | `page-name-input`, New / Rename / Delete page |
| `edit-floater-layout` | `layout` | Layout, rows, columns, page and split controls |
| `edit-floater-config` | `config` | Save / load / export / delete / refresh / import |

The floater is driven by three transient stores:

| Store | Values | Purpose |
|---|---|---|
| `edit-floater` (style) | visible (`flex`) / hidden | Whether the window is on screen. |
| `edit-floater-mode` | `create` / `pages` / `layout` / `config` | Which panel the window shows. |
| `edit-floater-target` | page/tab key | Where a created item belongs; replaces `item-modal-target`. |

None of them is persisted; only the mutations they enable are saved (ADR 0018).

The entry points are:

- **Edit dashboard** (`edit-toggle`) → toggles edit mode and reveals the other
  edit controls. It always closes the floater; it never opens it.
- **Add/edit page**, **Edit layout**, **Configuration** buttons in the header →
  switch edit mode on if needed and open the matching panel.
- A `+` slot, a per-item **Edit** button or a default-graph **Edit** button →
  open the `create` panel for that target, pre-filled with the item being edited
  (ADR 0018, ADR 0021).
- **Add** or **Cancel** in the create panel → keeps the create panel open for
  another item.
- The floater's **`×`** (`edit-floater-close`) → closes the window but leaves
  edit mode on; **Edit/Done** is the single exit from edit mode.

### Create panel — visualisation, filter and titles

The old `item-modal` form moves into the floater's create panel, keeping its ids
(`item-kind`, `item-column`, `item-y`, `item-aggregation`, `item-title`,
`item-xlabel`, `item-ylabel`, `item-add`, `item-cancel`). Consequently:

- the kind dropdown still groups generic charts and filters (ADR 0014);
- the heading stays contextual — "Add a visualisation or filter" when creating,
  "Edit filter" / "Edit visualisation" when editing (ADR 0021);
- the three label fields (`title`, `x_label`, `y_label`) remain the only place
  where graph titles are authored: they are pre-filled from the spec on edit and
  written back to it on Add (ADR 0018);
- `prefill_item_modal`, `update_item_modal_fields` and `update_item_modal_title`
  keep their logic and are only retargeted to the floater panel.

The `item-modal` component itself is removed. The legacy
`chart-creator-controls` row is also removed: chart creation now goes through
the floater's create panel, reached with a `+` slot in edit mode.

### The three configuration panels

- **Pages:** `page-name-input` with New page / Rename page / Delete page, moved
  out of the header's `dashboard-page-controls` (ADR 0015); the tab-bar `+` for
  a new tab stays in the sidebar as a second entry point (ADR 0018).
- **Layout:** `graph-layout`, `graph-rows`, `graph-columns`, `graph-page`,
  `graph-split-x` and `graph-split-y`, moved out of the always-visible row in
  the dashboard content. Changing one still flows into `update_output` and
  `arrange_graphs`, is restored by `apply_config_layout` on import, and is saved
  under the `layout` key of an ADR 0015 document. Layout is therefore configured
  in the same floater as the rest of the dashboard.
- **Configuration:** `config-name-input`, save / load / export / delete /
  refresh, `config-saved-dropdown`, `config-import` and `config-status` (ADR
  0015), moved out of the header row.

The import-replace and tab-removal confirmation popups remain separate: they are
confirmations of a destructive action, not configuration forms.

### Callbacks and state

- `toggle_edit_mode` and `toggle_item_modal` are replaced by a single
  `toggle_edit_floater`, the one writer of `edit-mode`, `edit-toggle.children`,
  the new-tab `+` style and the floater's style / mode / target / edit index.
  Its Edit branch only changes edit mode and closes the window; its close
  branch only hides the window; its three section-button branches set edit mode
  on and choose a panel.
- `render_edit_floater_panels` writes the four panels' styles from
  `edit-floater-mode`, showing exactly one.
- `update_page_state`, `update_default_graph_overrides`, `handle_config_actions`
  and `apply_config_layout` are unchanged apart from reading the same ids in
  their new location. The legacy chart-creator inputs and output are dropped.
- `update_output` drops the `chart-creator-controls` style output; the
  `creator_controls_style()` helper is removed.
- Because a Dash style callback **replaces** the whole `style` dict, the show
  and hide values written to `edit-floater.style` carry the overlay properties
  (`position: fixed`, `inset: 0`, `zIndex: 9999`, centring) as well as
  `display`. Writing only `display` would drop the floater out of fixed
  positioning and leave it at the top of the document flow.

### Styling

The floater is a fidelity copy of the `simva-front` floating window: fixed
`inset: 0`, `z-index: 9999`, centred with flex, a `rgba(0,0,0,0.5)` backdrop, a
`calc(100vw - 32px)` white card with `max-height: calc(100vh - 32px)`, rounded
corners and hidden overflow, a scrollable `.iframe_content` body padded
`48px 20px 20px 20px`, and the close button absolutely positioned in the
card's top-right corner. There is no header or drag bar — simva-front has
neither. All of this is expressed as inline styles on the Dash components, for
the proxy reason in driver 10. The window lives at the top level of `TMonBody`,
so it is shared by the upload and SIMVA apps.

## Alternatives Considered

- **Keep controls inline and only restyle them**: rejected; that keeps the
  read-only dashboard cluttered and does not give configuration one home.
- **A separate configuration page or route**: rejected; it drops the dashboard
  context and adds a step for every change, as with the rejected creation page
  in ADR 0012.
- **Keeping the old top-centred `item-modal`**: rejected; the `simva-front`
  floater (backdrop, centred card, close button) is the established model in
  this ecosystem and gives all settings one home.
- **One panel holding all configuration, opened by Edit**: rejected; it mixed
  unrelated tasks into a long window and gave Edit two jobs. One panel per
  button keeps each task focused.
- **Two floaters, one for creation and one for configuration**: rejected; both
  edit the same dashboard state, so a single window with separate panels avoids
  a second state model.
- **Leaving the layout controls inline**: rejected; layout is part of the saved
  configuration (ADR 0015) and must be reachable from the same floater as the
  other configuration controls.
- **Adding a CSS file for the floater**: rejected; deployed proxies may not
  serve `/assets/...` (ADR 0011).

## Consequences

- The dashboard header and the dashboard content lose the page-control, config
  and layout rows; the Create tab loses its legacy chart-creator row. All of
  those controls are reachable only from the floater, in edit mode or through
  their section buttons.
- `item-modal` is replaced by `edit-floater`; `item-modal-target` is replaced by
  `edit-floater-target`, and `edit-floater-mode` is added. All are transient.
- Three header buttons and four panels are added; i18n keys `edit.pages`,
  `edit.layout` and `edit.config` are added to en/es/fr.
- The layout controls keep their ids, so configuration import/export, URL
  state and `arrange_graphs` need no changes; the ADR 0015 document format is
  unchanged.
- Title editing stays in exactly one form, now inside the floater; graph title
  and axis-label fields remain user data on the spec, not translations.
- Tests cover: Edit toggling without opening the floater, the `×` closing
  without leaving edit mode, each section button opening its own panel with the
  overlay style intact, each panel holding its controls, and the mutation paths
  continuing to work through the unchanged ids.

## Status

- **Status**: Accepted
- **Date**: 2026-11-23
- **Tags**: #ui #edit-mode #floater #dashboard #configuration #layout

## See Also

- [ADR 0007](0007-shared-translations.md) — shared translations
- [ADR 0011](0011-simva-compatible-header.md) — inline styles behind proxies
- [ADR 0012](0012-empty-visualization-page.md) — creation slot and popup
- [ADR 0015](0015-dashboard-configuration-import-export.md) — configuration
  document and layout keys
- [ADR 0018](0018-edit-mode-for-tabs-and-visualisations.md) — edit mode and
  graph labels
- [ADR 0019](0019-dashboard-polish-url-hover-adaptive-slots.md) — creation UI
- [ADR 0021](0021-filter-row-and-modal-titles.md) — contextual popup titles
- [T-Mon application reference](../../reference/tmon-app-reference.md)
