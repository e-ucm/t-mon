# ADR 0019: Dashboard polish — URL hover, adaptive slots and creation UI

## Context and Problem Statement

After ADR 0018 the dashboard can be edited, but three rough edges remain and a
backlog of earlier decisions is still only partially implemented:

1. **Axes show shortened URLs but the full IRI is lost.** ADR 0015/0017 shorten
   `https://yyyuyugjh.com/xxx` to `xxx` so a bar chart stays readable, but a
   reader can no longer tell which statement the mark came from. The full URL
   should be available on hover.
2. **The creation popup does not always present its fields.** Opening a `+` slot
   resets `item-kind` to nothing, so the column / value / label inputs stay hidden
   until a kind is picked; picking a filter kind hides the label inputs but the
   value row is not always shown. The popup should open ready to use.
3. **The `+` slot does not follow the grid.** `arrange_graphs` always appends a
   single `+` button below the charts, so a 2 × 2 grid with one chart leaves three
   empty cells instead of three `+` slots.
4. **Carry-over from earlier ADRs.** Default-dashboard graphs are editable only by
   an administrator (ADR 0018); non-administrators still see the definition as
   written. Several smaller items listed in ADR 0016 (notebook catalogue removal)
   and ADR 0018 (labels, config round-trip) are now in place and are recorded
   here so the decision log stays complete.

## Decision

### 1. Hover shows the full URL

- `ValueLabels` gains `full_url_map(series)` and `hover_values(values, mapping)`.
  `full_url_map` records, for every value that shortening actually changed, the
  original URL (or the joined list of originals when two URLs share a last
  segment). Values that are not URLs are absent from the map.
- `ChartBuilder.build_chart` computes the map before shortening `x`, and, when it
  is non-empty, sets `customdata` on every trace so the hover template shows the
  full URL above the shortened value. The axis itself keeps showing the short
  form.
- `GraphTypes` does the same for default-dashboard graphs: `_summary` stores
  `full_x` on the summary's `attrs`, `_with_url_hover` applies it to bar / line /
  scatter / pie, and `_heatmap` stores both `full_x` and `full_y` and shows them
  in its hover template. Date axes never shorten, so they never get a hover map.
- Shortening stays display-only: statements, filters, links and specs keep the
  full identifier, as required by ADR 0015.

### 2. The creation popup opens ready to use

- `item-kind` defaults to `bar`, so `update_item_modal_fields` immediately shows
  the column, value and label inputs for a generic chart. Switching the kind to a
  filter kind shows the column and mode inputs and hides the label and value rows;
  switching to a chart kind shows them again.
- The value row (`item-value-div`) is shown for every chart kind and hidden for
  every filter kind, matching the aggregation selector that only charts use.
- The label inputs keep their values while the kind changes, so a user who typed
  a title does not lose it by switching chart type.

### 3. The `+` slot follows the grid

- `arrange_graphs` no longer appends a single `+` button. It computes how many
  cells the current page holds (`page_size`) and how many are occupied by graphs
  (`shown`), then appends `max(1, page_size - len(shown))` copies of the `+`
  slot, each carrying the same target index. A 1 × 1 layout therefore shows one
  `+`; a 2 × 2 layout with one chart shows three `+` buttons filling the row.
- At least one `+` is always shown, even on a full page, so a chart can always
  be added on the next page or below the grid.
- The copies are deep copies of the original button, so their id, title and style
  stay identical and the existing `item-add-slot` callback handles every one.

### 4. Carry-over recorded here

- Default-dashboard graphs are editable only by an administrator; the deployed
  JSON is never modified, an override store holds the edited spec, and a
  configuration file round-trips `default_graph_overrides` (ADR 0018).
- User-authored labels (`title`, `x_label`, `y_label`) are data on the spec, are
  not written to `default-dashboard.json`, and survive a config export/import.
- The `+` button that creates a new tab is always shown in edit mode.
- The `ValueError: invalid literal for int() with base 10: '/dashboard/upload'`
  crash is fixed by keeping Dash Inputs before States in `update_page_state`.

## Consequences

- Hovering a mark whose axis value came from a URL now shows the full IRI; marks
  whose value is plain text are unaffected because they are absent from the map.
- The creation popup is usable the moment it opens, without an extra click to
  choose a kind.
- Empty cells in a grid layout are themselves `+` slots, so the grid stays
  balanced and every cell is actionable.
- No statement, filter, link or spec changes shape: shortening and hover remain
  purely presentational.
EOF
echo done