# ADR 0012: Empty visualization page with a single add slot

## Context and Problem Statement

A newly created visualisation page in T-Mon is not empty: it opens with the
always-visible `chart-creator-controls` panel and, once charts have been added,
with those charts already laid out. Pages themselves are fixed tabs, so a user
cannot give a page a name of its own. The desired starting point is a blank,
named page that invites the user to create the first visualisation explicitly,
one slot at a time, instead of presenting a toolbar before there is anything to
put on it.

## Decision Drivers

1. A new, user-named visualisation page must contain nothing until the user
   adds an item.
2. The default layout holds exactly one visualisation slot.
3. That slot shows only a `+` affordance; creation happens where the item
   will appear, not in a permanent toolbar.
4. Clicking the `+` opens a popup with the information needed to create the
   visualisation or filter.
5. The popup offers all creatable items: named visualisations
   ([ADR 0013](0013-named-visualisation-catalogue.md)), generic charts and page
   filters ([ADR 0014](0014-page-level-filters.md)).
6. The chart description stays compatible with the shared `created-charts`
   state and URL carrying ([ADR 0004](0004-chartbuilder-module.md)).
7. All new text comes from the translation catalogue
   ([ADR 0007](0007-shared-translations.md)).

## Decision

### Empty starting page

A new visualisation page — in particular a user-named page added beside the
built-in tabs ([ADR 0015](0015-dashboard-configuration-import-export.md)) —
renders with no preloaded charts and no inline creator controls. It is an empty
canvas whose only content is the default layout described below.

### Default layout: one add slot

The default layout consists of a single visualisation slot. Until a chart is
created in it, the slot renders only a `+` — no axes, no placeholder figure, no
surrounding form. The slot is the sole interactive element on the fresh page.

### Creation popup

Clicking the `+` opens a popup (modal) containing the information needed to
create the item. Its groups cover the generic chart fields already defined by
`ChartBuilder` (`CHART_TYPES`, `AGGREGATION_LABELS`, `COUNT_LABEL`), the named
figures from the Progress and Videos tabs
([ADR 0013](0013-named-visualisation-catalogue.md)) and the page filters
([ADR 0014](0014-page-level-filters.md)). The popup reuses those definitions
rather than introducing a second chart or filter model.

On confirmation the popup closes and the slot becomes the created item. Charts
are stored in the same `created-charts` state and encoded in the URL as any
other chart; filters use the page-filter store and URL parameter. An empty page
therefore becomes a one-item page, and any further slot follows the same
`+`-to-popup flow.

### First-render correctness

The popup and the slot are part of the initial Dash layout, not injected by a
callback later, so their ids exist on the first render. As in
[ADR 0009](0009-simlet-detail-view.md), a shared helper computes the layout and
applies it directly when the page is built; callbacks reuse the same helper for
later updates. User-named pages created later use the same helper when their
tab is added.

## Alternatives Considered

- **Preload a default chart**: rejected; the page must start empty and let the
  user choose what the first visualisation shows.
- **Keep the always-visible inline creator controls**: rejected; they put a
  toolbar on an empty page and separate creation from the slot it fills.
- **Navigate to a separate creation page**: rejected; it drops the dashboard
  context and adds a step for each chart.

## Consequences

- A new visualisation page has a predictable, minimal first state: one `+`.
- Item creation is explicit and local to a slot, and the popup reuses the
  existing `ChartBuilder` and filter definitions rather than duplicating them.
- New modal and slot callback ids must be added to the Dash layout; following
  the shared-helper pattern keeps the first render and later callbacks in sync.
- Existing `created-charts` state, chart removal and URL carrying are unchanged.
- New labels (the `+` tooltip and popup fields) must be added to the i18n
  catalogue, not written as literals.

## Status

- **Status**: Accepted
- **Date**: 2026-11-19
- **Tags**: #ui #visualization #dash #layout

## See Also

- [ADR 0004](0004-chartbuilder-module.md)
- [ADR 0007](0007-shared-translations.md)
- [ADR 0009](0009-simlet-detail-view.md)
- [ADR 0013](0013-named-visualisation-catalogue.md)
- [ADR 0014](0014-page-level-filters.md)
- [ADR 0015](0015-dashboard-configuration-import-export.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
