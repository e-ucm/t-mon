# ADR 0021: Filter row consolidation and contextual modal titles

## Context and Problem Statement

The creation popup always opened with the heading "Add a visualisation or filter", even
when it was editing an existing item, and its filters lived in two places: the general
and tab filters of a default page (`render_definition_filter_controls`) and the page
filters of a user page (`render_filter_controls`). A reader could not tell from the
popup whether they were adding or editing, and the filter row did not offer a way to
add a filter in place.

## Decision

- **Contextual popup title.** The modal heading (`item-modal-title`) is driven by
  `item-edit-index`: with no edit index it reads "Add a visualisation or filter"
  (`visual.open`); when editing a filter it reads "Edit filter" (`edit.filter`);
  when editing a graph it reads "Edit visualisation" (`edit.visualisation`). A new
  locale key `edit.visualisation` is added to en/es/fr.
- **Flat kind list when editing.** When the popup edits an existing item, the
  `item-kind` dropdown drops the "Generic charts" / "Filters" group labels and
  shows a flat list of kinds, since the choice is no longer a fresh one.
- **In-place filter addition.** `render_filter_controls` appends a compact `+`
  button (an `item-add-slot` with the page's target) at the end of the filter row,
  shown only in edit mode, so a filter can be added without leaving the row.
- **One filter row.** General, tab and page filters of a default page are already
  rendered together by `render_definition_filter_controls`; the page-level filters of
  a user page are rendered by `render_filter_controls`. Both keep their single-row
  flex layout with wrapping, so all filters of a tab appear in the header area
  above its charts.

## Consequences

- The popup states whether it is adding or editing, and which kind of item.
- A filter can be added from the filter row itself.
- No change to filter storage or to the configuration format.
EOF
echo done