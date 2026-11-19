# ADR 0014: Page-level filters

## Context and Problem Statement

The dashboard offers two fixed filters in its header, on `actor.name` and
`object.id`, plus the activity on/off buttons. Both are global and hard-coded:
a user cannot add a filter for another column, choose whether it is a
multi-select or a one-select, or place it on a page they have built. The charts
on that page all read one `filtered_df`, so a filter added to the page can
narrow every visualisation without touching the underlying statements.

## Decision Drivers

1. Filters are added through the same creation popup as charts
   ([ADR 0012](0012-empty-visualization-page.md)).
2. A page filter applies to **every** visualisation on that page.
3. A filter may be a multi-select or a one-select over any chartable column.
4. Filters render together in a row above the charts, not interleaved with
   them.
5. Shared links carry both the filter definition and its selected values.
6. New labels come from the translation catalogue
   ([ADR 0007](0007-shared-translations.md)).

## Decision

### Filter entries

The creation popup gains a Filters group with `filter-multi` and
`filter-single` entries. Each asks for a column, offered from the columns
`ChartBuilder.chartable_columns` reports for the current statements. A spec
holds the column, the mode and the values currently selected. Single-select
values are stored in the same list shape as multi-select values.

### Application

A helper in `TMonWidgets/MultiSelector.py` applies every page filter to the
statements with an `isin` test on its column. It runs after the header
actor/object dropdowns and after the activity filter, so the result is the
`filtered_df` every chart, table and named visual on the page reads. Values that
no longer occur in the data are dropped rather than narrowing the view to
nothing.

### Controls and layout

Each filter renders as a `dcc.Dropdown` with `multi=True` or `False`, a remove
button and a pattern-matching id (`{'type': 'page-filter', 'index': n}`), so the
number of filters can grow without changing the layout. Its options are the
distinct values of the chosen column in the filtered data and are refreshed
when `lrs-data-version` changes. Selected values that are still present remain
selected. All filters are rendered in one row above the visualisations.

### State and links

Page filters live in a `page-filters` store with a single writer, mirroring the
`created-charts` arrangement. A `filter=` URL parameter carries each filter's
column, mode and selected values; the values are read back on load in the same
place chart descriptions are read, so a shared link reproduces both the
controls and their selections. Link parameters use a separator that cannot
appear in a column name or value, and values are escaped when encoded.

## Alternatives Considered

- Extend only the two header filters: rejected; they cannot cover other
  columns or one-select mode.
- Let each chart choose its own filters: rejected; the user chose page-wide
  filters.
- Put filters among the charts in creation order: rejected; the user chose a
  single row above the charts.
- Carry only the filter definition in links: rejected; the selected values are
  part of the view being shared.

## Consequences

- Page filters narrow all visualisations and the data table consistently.
- Links become longer as selections are added, and remain capped by the
  existing chart limit only for charts.
- New data can invalidate a selection; the filter is then cleared rather than
  showing an empty page with no explanation.
- New labels (group, modes, placeholders) must be added to all three locale
  files.

## Status

- **Status**: Accepted
- **Date**: 2026-11-19
- **Tags**: #ui #filters #dash #url

## See Also

- [ADR 0007](0007-shared-translations.md)
- [ADR 0012](0012-empty-visualization-page.md)
- [ADR 0013](0013-named-visualisation-catalogue.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
