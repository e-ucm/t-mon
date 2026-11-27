# ADR 0027: Filter editor and JSON persistence

## Context and Problem Statement

Filters were created through the generic visualisation popup with only a column,
a mode and selected values. There was no name, no hidden flag surfaced as a
field in the editor, no way to choose which dashboard tab a filter applies to,
and filter metadata was not reliably carried into saved configuration files.

## Decision

### Filter editor

Each filter is edited in the creation popup with the following fields:

- **Name**: a human-readable label shown in the filter row.
- **Data column**: the column the filter narrows.
- **one/multi**: whether the filter accepts one or several values.
- **hidden**: whether the filter narrows the view without showing a dropdown.
- **if one, Data Selected**: the selected value when the filter is single-select.
- **Apply to tab**: the dashboard tab where the filter is applied. This is a
  single-select choice, not a global all-tabs toggle. A newly created filter
  defaults to the tab from which it was created.
- **Validate**: confirms the filter.

The filter row renders as `filter name: [selected value] Edit X [+]`. A hidden
filter continues to narrow the selected tab's data without displaying a
selection control.

The target tab is stored by its stable tab ID, so renaming a tab does not change
the filter's target. HomePage and the raw xAPI data tab are not valid targets. If
the target tab is deleted, the filter is not silently reassigned to another tab.

### Persistence

Filter descriptions carry `name`, `hidden`, and the selected target tab ID.
`normalise_filter`, `encode_filter`/`decode_filters` and the configuration
document parser preserve these fields so they survive shared links and saved
JSON files. Existing links and configuration files without the new metadata
remain valid; their filters retain their existing page-local behavior.