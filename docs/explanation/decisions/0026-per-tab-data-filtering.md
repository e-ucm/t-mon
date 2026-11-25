# ADR 0026: Per-Tab Data Filtering and Chart-Type-Specialized Filter Options

## Context and Problem Statement

T-Mon currently supports filtering at two levels:
1. **Definition filters** (ADR 0017): General filters applied to all dashboard tabs/pages
2. **Page-level filters** (ADR 0014): Filters specific to each page's graphs

However, teachers need more granular control:
- Different tabs/pages may need different filter options
- Certain chart types (e.g., heatmaps vs. bar charts) may require specialized filter configurations
- Teachers should be able to select single or multi-filtering per tab before viewing visualizations
- The filter options should be declarative and configurable per-tab

This limitation hinders:
- Teachers who want different filter perspectives for different session views
- Comparative analysis where each tab shows a different filtered perspective
- Chart-type-appropriate filtering (e.g., date filters for time-series, category filters for heatmaps)

## Decision Drivers

1. **Per-tab filter configurations**: Each dashboard tab/page should have its own filter configuration, independent of other tabs
2. **Chart-type-specialized filtering**: Different visualization types should have appropriate filter options pre-configured
3. **Single/multi-filter selection**: Teachers should choose between single-value or multi-value filters per tab
4. **Declarative filter definitions**: Filter configurations should be part of the dashboard definition, not hardcoded

## Decision

### 1. Per-Tab Filter Configurations

- Extend the dashboard definition format (ADR 0015) to include per-tab filter specifications
- Each tab entry in the definition can have an optional `filters` field containing:
  - `filters`: Array of filter definitions specific to this tab
  - `filter_mode`: "single" or "multi" - whether teachers can select one or multiple values
  - `initial_filters`: Pre-selected filter values when the tab is first loaded
  - `filter_options`: Available filter columns/sources for this tab

Example definition extension:
```json
{
  "version": 1,
  "tabs": [
    {
      "id": "overview",
      "title": "Session overview",
      "filters": {
        "filter_mode": "single",
        "filters": [
          {
            "id": "actor",
            "label": "Player",
            "column": "actor.name",
            "mode": "multi",
            "options": ["student1", "student2", "student3"]
          }
        ],
        "initial_filters": ["student1"]
      }
    },
    {
      "id": "progress",
      "title": "Progress",
      "filters": {
        "filter_mode": "multi",
        "filters": [
          {
            "id": "level",
            "label": "Level",
            "column": "object.id",
            "mode": "single"
          }
        ]
      }
    }
  ]
}
```

### 2. Chart-Type-Specialized Filter Options

- Define filter option sets per chart type in a new `FilterOptions` registry (similar to GraphTypes)
- Chart types can specify:
  - Required filter columns
  - Available filter modes (single/multi)
  - Default filter values
  - Filter-dependent chart configuration

Supported chart-type filter specifications:
- **line**: Time-based filters (date ranges), category filters
- **bar**: Category filters, comparison filters
- **pie**: Category or value filters for proportion breakdown
- **heatmap**: Row/column group filters, measure filters
- **count**: Activity filters, result filters

Example filter options registry:
```json
{
  "filter_options": {
    "line": {
      "available_modes": ["single", "multi"],
      "required_columns": ["date", "category"],
      "default_filters": {"date": "last_30_days"}
    },
    "heatmap": {
      "available_modes": ["single", "multi"],
      "required_columns": ["row_category", "column_category", "measure"],
      "default_filters": {"row_category": "all_students"}
    }
  }
}
```

### 3. Single/Multi-Filter Selection UI

- Add a filter mode selector per tab in the dashboard header
- When `filter_mode` is "single": Show single-select dropdowns
- When `filter_mode` is "multi": Show multi-select dropdowns (with checkboxes or tag-based selection)
- UI should be consistent with existing filter components (ADR 0014, 0017)

### 4. Filter Application Order

Filters should be applied in this order per tab:
1. Tab-specific filters (from definition)
2. Page-level filters (existing system)
3. Definition filters (general, ADR 0017)
4. Activity filters (visibility control)

This ensures tab-specific filters take precedence, allowing teachers to narrow down the view appropriately before page-level and general filters further refine the charts.

### 5. Consequences

**Positive**:
- Teachers can create different filtered perspectives for the same session across tabs
- Chart-type-appropriate filtering improves data exploration efficiency
- Single/multi filter choice per tab gives teachers control over selection behavior
- Filter configurations are declarative and part of the dashboard definition

**Negative**:
- Dashboard definition format becomes more complex
- Additional UI components needed for per-tab filter configuration
- Filter application logic needs to handle multiple priority levels
- Existing dashboards may need definition updates to specify tab filters

**Negative**:
- Backward compatibility: Existing dashboards without tab filter definitions will use default behavior (no tab-specific filters, fall back to page-level then definition filters)

## Status

- **Status**: Accepted (proposed)
- **Date**: 2026-11-25
- **Tags**: #dashboard #filtering #per-tab #chart-type #single-multi-filter #configuration

## See Also

- [ADR 0015](0015-dashboard-configuration-import-export.md) — dashboard configuration format
- [ADR 0017](0017-user-defined-default-dashboard-definition.md) — user-defined default dashboard definition
- [ADR 0014](0014-page-level-filters.md) — page-level filters
- [ADR 0018](0018-edit-mode-for-tabs-and-visualisations.md) — edit mode for dashboards
- [T-Mon application reference](../../reference/tmon-app-reference.md)
