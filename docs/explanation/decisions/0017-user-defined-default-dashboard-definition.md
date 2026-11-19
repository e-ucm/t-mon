# ADR 0017: User-defined default dashboard definition and labels

## Context and Problem Statement

ADR 0012–0016 built a dashboard whose tabs, graph descriptions and display text
live in Python and in the shared locale files. The built-in tabs are chosen by
`DASHBOARD_TABS` and `BUILTIN_TAB_VISUALS` in `TMonWidget`, the notebook
figures are selected from `VisualizationCatalog`, and their titles and axis
labels come from `t("figure.title.*")` and `t("figure.axis.*")` keys in
`src/locales/<lng>.json`.

That is suitable for shared UI chrome, but not for a study-specific dashboard:

- a deployment cannot rename a tab, graph or axis without changing Python or a
  global translation file;
- changing a locale key changes every dashboard that uses it, not just the
  dashboard being edited;
- the renderer code currently supplies a title for each figure, so a user
  cannot choose to have no title or to write a domain-specific one;
- ADR 0016 explicitly kept the default dashboard in code and rejected a shipped
  dashboard JSON file. The user now wants that default dashboard to be defined
  by a JSON file instead;
- there is no declarative way to describe Markdown help text, dashboard-wide
  filters, per-page filters, the tab/page layout and the graphs together.

This ADR supersedes the ADR 0016 decision that the default dashboard must be the
built-in placeholder tabs rather than a shipped definition file. The notebook
figures from ADR 0016 remain available as data recipes, but the default
dashboard itself becomes data-driven.

## Decision Drivers

1. Tab titles, graph titles, Markdown text and x/y axis labels must be written
   by the dashboard author in JSON, not stored as i18n keys.
2. The JSON file must describe the whole default dashboard: tab names, Markdown
   content, layout, graphs, general filters, per-page filters, tab titles, graph
   titles, graph types and axis data.
3. Code may define only the set of supported graph types and how to render
   them. It must not define default graph titles.
4. The x axis definition must carry its label, its data source and whether that
   source is a date; the y axis definition must carry its label and data source.
5. The dashboard must always include a reserved `xapi_data` tab showing a table
   of the loaded statements, whatever the JSON file contains.
6. Invalid dashboard files must be rejected before the dashboard is built, with
   a clear error instead of a partially rendered page.
7. Existing links, named pages and ADR 0015 runtime configuration files must
   keep working; the new file is a deployment-level default, not a replacement
   for user saves.

## Decision

### Default dashboard definition file

Add a versioned JSON document at `src/config/default-dashboard.json`, overridable
by the `TMON_DEFAULT_DASHBOARD` environment variable. A new
`TMonWidgets/DefaultDashboard.py` loads, validates and caches it once per
process.

The document has its own `version` field, starting at `1`. It is deliberately
separate from `PageConfig.FORMAT_VERSION` in ADR 0015: this file defines what a
dashboard *is* for a deployment, while an ADR 0015 document records the state a
user has reached while using it.

`TMonWidget` builds its tabs from this document. `DASHBOARD_TABS` and
`BUILTIN_TAB_VISUALS` stop being the source of the default dashboard and remain
only as compatibility fallbacks if the definition file cannot be read.

### Document structure

A definition has dashboard-wide fields and a list of tabs. Each tab has a
title, optional Markdown, optional general filters and one or more pages. Each
page has its own title, Markdown, layout, filters and graphs.

```json
{
  "version": 1,
  "name": "Default xAPI-SG dashboard",
  "layout": {
    "type": "grid",
    "columns": 2,
    "rows": 3
  },
  "general_filters": [
    {
      "id": "actor",
      "label": "Player",
      "column": "actor.name",
      "mode": "multi"
    }
  ],
  "tabs": [
    {
      "id": "overview",
      "title": "Session overview",
      "markdown": "# Overview\nUse the filters to narrow the session.",
      "pages": [
        {
          "id": "progress",
          "title": "Progress",
          "markdown": "Progress is read from the xAPI `result.progress` field.",
          "layout": {
            "type": "vertical"
          },
          "filters": [
            {
              "id": "level",
              "label": "Level",
              "column": "object.id",
              "mode": "single"
            }
          ],
          "graphs": [
            {
              "id": "progress-over-time",
              "title": "Progress over time",
              "type": "line",
              "x": {
                "label": "Time",
                "data": "timestamp",
                "date": true
              },
              "y": {
                "label": "Progress",
                "data": "result.progress"
              }
            },
            {
              "id": "items-by-player",
              "title": "Items used by each player",
              "type": "heatmap",
              "x": {
                "label": "Item",
                "data": "object.id"
              },
              "y": {
                "label": "Player",
                "data": "actor.name"
              }
            }
          ]
        }
      ]
    }
  ],
  "xapi_data_tab": {
    "id": "xapi_data",
    "title": "xapi data",
    "markdown": "All statements loaded for this session."
  }
}
```

Field meanings:

| Field | Meaning |
|---|---|
| `version` | Version of this dashboard-definition format. |
| `name` | User-defined dashboard name; not displayed unless a tab uses it. |
| `layout` | Default graph arrangement for pages that do not override it. |
| `tabs[].id` | Stable Dash tab value, prefixed internally as today if needed. |
| `tabs[].title` | User-defined tab label. No i18n lookup. |
| `tabs[].markdown` | Markdown shown above the tab's pages. No i18n lookup. |
| `general_filters` | Filters applied before the page filters of every page. |
| `pages[].title` | User-defined page label. No i18n lookup. |
| `pages[].markdown` | Markdown shown above the page's graphs. No i18n lookup. |
| `pages[].layout` | Overrides the dashboard `layout` for this page. |
| `pages[].filters` | Filters applied only to this page. |
| `graphs[].id` | Stable graph id, used to keep Dash ids unique. |
| `graphs[].title` | User-defined graph title. No i18n lookup and no generated fallback. |
| `graphs[].type` | One of the graph types registered in code. |
| `graphs[].x.label` | User-defined x axis label. No i18n lookup. |
| `graphs[].x.data` | Column or code-defined measure plotted on the x axis. |
| `graphs[].x.date` | When true, parse `x.data` as a date and use the date axis path. |
| `graphs[].y.label` | User-defined y axis label. No i18n lookup. |
| `graphs[].y.data` | Column or code-defined measure plotted on the y axis. |

Markdown is rendered with `dcc.Markdown` with raw HTML disabled, so a definition
file cannot inject markup outside the allowed Markdown subset.

### Labels are data, not translations

Tab titles, page titles, graph titles, Markdown blocks and x/y axis labels are
stored only in the default dashboard JSON file. Rendering code reads the string
from the validated definition and passes it directly to Dash; it never calls
`I18n.t()` for one of those values.

Locale files remain the source for application chrome such as buttons, headers,
login controls and generic messages. The `figure.title.*` and `figure.axis.*`
keys introduced for ADR 0016 are deprecated: their values move into
`default-dashboard.json`, and builder code stops looking them up. A graph with
no `title` in the file has **no title**. T-Mon must not synthesize one from the
graph type, column names or a locale key.

### Graph types live in code

A new `TMonWidgets/GraphTypes.py` registry defines the allowed `type` values and
the renderer for each, for example `bar`, `line`, `scatter`, `pie` and
`heatmap`. The registry also declares how many axes a type needs, which data
shapes it accepts and whether it produces a table rather than a Plotly figure.

The registry contains rendering behaviour only. It contains no title strings,
no axis labels and no translation keys. `DefaultDashboard.load()` rejects a
graph whose type is not registered, whose required axes are missing, or whose
`x.date` flag is used with a type that cannot plot dates.

This keeps the security and consistency benefit of fixed renderers while
leaving all display wording in the hands of the dashboard author.

### Filters and data flow

Data reaches a graph in this order:

1. the statements loaded into `TMonWidgets.xapiData`;
2. the header actor/object selectors and the activity visibility filter;
3. the dashboard `general_filters`;
4. the active page's `filters`;
5. the graph renderer, which groups or measures `x.data` and `y.data`.

A general filter is therefore shared by every page that uses the definition,
while a page filter narrows only its own graphs. Both keep the `label`,
`column`, `mode` and optional `values` shape already used by ADR 0014, with the
important difference that `label` comes from JSON rather than i18n.

The renderer receives the filtered DataFrame. It does not read the global
statement list directly, so the same graph definition works for uploaded files,
SIMVA sessions and imported runtime configurations.

### Mandatory xapi data tab

The `xapi_data_tab` section defines the reserved tab with id `xapi_data`. The
loader always appends this tab as the last tab, even when the JSON file omits
the section, using the title `xapi data` and an empty Markdown block in that
case. The label must remain `xapi data`: a definition may add Markdown but may
neither rename nor remove the tab.

This tab always contains a `dash_table.DataTable` built from the full loaded
statement set, flattened for display as today. It ignores dashboard general
filters and page filters: it is the audit view of the statements the dashboard
received. Header actor/object selections and hidden activities still apply
because they define which statements are in the loaded view.

### Compatibility

- ADR 0015 runtime configurations and shared links keep their current format
  and version. They store user state; the default dashboard definition is read
  from the deployed file.
- Named visual ids from ADR 0013 and ADR 0016 remain valid for existing links and
  user-created pages. They are no longer the source of default-tab titles.
- The compatibility fallback keeps the old built-in tabs available if the
  definition file is missing or invalid, but a clear startup warning is logged.
- New tests must validate the example file, reject unknown graph types, confirm
  the mandatory `xapi_data` tab, confirm that no graph renderer calls `I18n.t()`
  for titles or axes, and cover general/page filter ordering and layout
  overrides.

## Alternatives Considered

- **Keep all labels in i18n**: rejected; one locale key cannot express different
  wording for different deployments without affecting every dashboard.
- **Derive graph titles from the type or column names**: rejected; the user
  explicitly asked that no graph title be defined by default.
- **Let JSON supply arbitrary Python renderer code**: rejected; only registered
  graph types are safe to load from a file.
- **Store the definition in the ADR 0015 runtime config only**: rejected; the
  default dashboard must ship with the application and be independently
  versioned.
- **Make the xapi data tab optional**: rejected; the user asked for it to be
  always present as the complete data table.

## Consequences

- A new JSON file and loader become part of every T-Mon deployment.
- Dashboard authors can edit titles, Markdown, filters, layout and graphs
  without touching Python or locale files.
- Graph renderers become purely visual: code defines *how* a `heatmap` or `pie`
  is drawn, and the JSON file defines *what it is called* and *which data it
  uses*.
- Locale files shrink as `figure.title.*` and `figure.axis.*` keys are retired;
  old keys may remain temporarily for non-default legacy charts.
- A bad definition file is a deployment error and must fail validation loudly
  rather than silently omit graphs.
- The `xapi_data` tab is guaranteed, which makes every dashboard auditable
  against its source statements.

## Status

- **Status**: Proposed
- **Date**: 2026-11-19
- **Tags**: #configuration #dashboard #i18n #json #visualization

## See Also

- [ADR 0007](0007-shared-translations.md)
- [ADR 0012](0012-empty-visualization-page.md)
- [ADR 0014](0014-page-level-filters.md)
- [ADR 0015](0015-dashboard-configuration-import-export.md)
- [ADR 0016](0016-vis-notebook-visualisation-catalogue.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
