# ADR 0016: Full visualisation catalogue from the `vis/` notebooks

## Context and Problem Statement

[ADR 0013](0013-named-visualisation-catalogue.md) created a catalogue of four
named visualisations: three player-progress figures and one video seen/skipped
figure. Those are the only figures under `src/vis/` that the Dash application
can build today. The `vis/` directory, however, contains 14 notebooks defining
the wider xAPI-SG visualisation set: completable progress, scores and times;
correct/incorrect answers and answer selection; item and accessible-zone
interactions; and menu selections. Their figures are still notebook-only, built
from Jupyter widgets and the `players_info` dictionary that the application no
longer keeps.

The built-in dashboard tabs reflect that gap. Progress and Videos draw real
catalogue figures, but Completable, Alternatives, Interactions, Accessibles and
Menus still render fixed `Tab content 3`–`Tab content 7` placeholder graphs.
Users can create named pages and named charts
([ADR 0012](0012-empty-visualization-page.md),
[ADR 0015](0015-dashboard-configuration-import-export.md)), but the catalogue
does not offer most of the figures the original notebooks defined, and the
default dashboard does not show them.

This decision extends the catalogue to every visualisation defined in `vis/`
and makes those visualisations the contents of the built-in dashboard tabs. The
target is the built-in placeholder tabs, not a new shipped dashboard JSON file.

## Decision Drivers

1. All 14 notebooks in `vis/` must be accounted for in the catalogue or in the
   built-in tab wiring.
2. Every figure must be built from the normalized statements DataFrame that
   Dash already filters, so header selections, hidden activities and page
   filters remain authoritative.
3. The notebooks' widget state (`players_info`, checkbox selections,
   accordions) must not become application state.
4. One implementation of each figure must serve the built-in tabs, the `+`
   creation popup and imported/user-defined pages
   ([ADR 0013](0013-named-visualisation-catalogue.md)).
5. Chart descriptions, shared links and configuration documents must stay
   backward compatible with ADR 0013 and ADR 0015.
6. Every new label, including figure titles and axis labels used by the
   builders, must come from the shared translation catalogue
   ([ADR 0007](0007-shared-translations.md)) in English, Spanish and French.
7. No dashboard section should keep a fabricated placeholder graph when a real
   visualisation can be drawn, or when the data genuinely has nothing to draw.

## Decision

### Scope: all 14 notebooks

The four existing catalogue ids stay unchanged: `progress-line`,
`progress-origin`, `progress-pie` and `video-seen-skipped`. Fifteen new ids are
added, making 19 catalogue entries in total.

| Notebook | Catalogue result | Built-in tab |
|---|---|---|
| `demo.ipynb` | Existing `progress-line`, `progress-origin` and `video-seen-skipped` builders cover its figures | Progress / Videos |
| `globalsSelectors.ipynb` | No new id; it defines the original tab composition, not a unique figure | All built-in tabs |
| `xAPISG-GamesStartedCompleted.ipynb` | Existing `progress-pie` | Progress |
| `xAPISG-CompletableProgressIncreaseDecrease.ipynb` | `completable-progress-change`, with `absolute` and `relative` modes | Completable |
| `xAPISG-CompletablesProgress.ipynb` | `completable-progress` | Completable |
| `xAPISG-CompletablesScores.ipynb` | `completable-scores` | Completable |
| `xAPISG-CompletablesTimes.ipynb` | `completable-times` | Completable |
| `xAPISG-CorrectIncorrectPerPlayer.ipynb` | `correct-incorrect-by-player` | Alternative |
| `xAPISG-CorrectIncorrectPerQuestion.ipynb` | `correct-incorrect-by-question` | Alternative |
| `xAPISG-AlternativesSelectedQuestion.ipynb` | `alternatives-selected` | Alternative |
| `xAPISG-ItemsInteracted.ipynb` | `item-interaction-time`, `item-interaction-heatmap`, `item-interaction-count` | Interactions |
| `xAPISG-ItemsActionTypeInteracted.ipynb` | `item-action-type-count` | Interactions |
| `xAPISG-AccessedAccessible.ipynb` | `accessible-time`, `accessible-heatmap`, `accessible-count` | Accessibles |
| `xAPISG-MenusSelected.ipynb` | `menu-selection-count` | Menus |

`demo.ipynb` and `globalsSelectors.ipynb` are ported through the shared
builders and the default tab wiring rather than being exposed as artificial
catalogue entries. The other 12 notebooks each gain one or more Plotly builder
functions.

### Statement-to-metrics adapter

A new `src/vis/xAPISGVisualizationData.py` replaces the notebook-only
`ProcessxAPISGStatement` globals. It derives, from a normalized statements
DataFrame:

- actors, verbs, activity types, object ids and timestamps;
- result `response`, `success`, `progress`, `score` and `action_type`, whether
  they appear directly under `result` or under `result.extensions`;
- per-player game, video, completable, alternative, item, action-type,
  accessible-zone and menu aggregates;
- the available target ids for each kind of visualisation.

It is pure and order-independent. Missing columns or statement shapes produce
empty metrics, not exceptions. When both a full `object.id` and the legacy
last-path-segment id can name a target, the full id is offered first and the
legacy value is accepted by the builders.

### Plotly builders

Each builder lives in the Python module matching its source notebook under
`src/vis/`, returns a `plotly.graph_objects.Figure`, and has the shape:

```python
builder(df, game="", target="", mode="")
```

Jupyter widgets, matplotlib figures, accordions and module-level selection
globals are not used. Heatmaps use `px.imshow`, time/bubble figures use
`px.scatter` or `px.line`, and count/score figures use `px.bar` or `px.pie`.
A builder with no matching rows returns the existing `noDataToFillVis`
placeholder, so "no matching activity in this session" is never confused with
a broken chart.

The three existing `src/vis/` modules remain the implementation for the four
existing ids. They are reused, not duplicated.

### Catalogue and description changes

`VisualizationCatalog.VisualEntry` gains optional `target_kind` and `modes`
fields. `needs_game` is retained so existing descriptions and callers keep
working. The new groups are:

- `visual.group.completables`
- `visual.group.alternatives`
- `visual.group.interactions`
- `visual.group.accessibles`
- `visual.group.menus`

`GROUPED_VISUALS` lists them after Progress and Videos and before generic
charts and filters. `visual_kind_options()` therefore offers the whole
catalogue without a second hard-coded list.

A chart description keeps `visual` and `game` and adds optional `target` and
`mode`. `completable-progress-change` uses `absolute` and `relative` modes;
other target-based visuals use a single available target and ignore `mode`.
`normalise_spec` validates the target against the loaded statements where data
is available and preserves it when parsing a configuration before data is
loaded.

The compact named form uses the two spare fields already present in the
six-field encoding:

```text
named|VISUAL|GAME|TARGET|MODE|count
```

Old four-field named links decode with empty target and mode; old six-field
links with `-|-` in those positions decode to the same empty values. The
`PageConfig.FORMAT_VERSION` remains `1` because the added fields are optional
and previously saved documents remain valid. URL carrying, export, import,
Replace and Append all use the same description objects.

### Creation popup

The `+` popup gains a target dropdown and a mode dropdown. They are shown
according to the selected visual: games for the progress figures, completables
for the completable figures, alternatives for the answer figures, items or
action types for the interaction figures, accessibles for the accessible-zone
figures, and menus for the menu figure. The mode dropdown is shown only for
`completable-progress-change`. The popup continues to write to the same
`created-charts` or page-chart store as generic charts
([ADR 0012](0012-empty-visualization-page.md),
[ADR 0014](0014-page-level-filters.md)).

### Default dashboard tabs

`TMonWidget.update_output` replaces the five placeholder branches with one
shared built-in-tab renderer driven by a `BUILTIN_TAB_VISUALS` mapping. For each
tab it:

1. uses the already header-filtered `chart_df`;
2. discovers the relevant targets with `target_ids`;
3. renders one titled figure per target, capped to keep a tab readable;
4. gives each figure a stable, unique graph id derived from the visual id and
   target;
5. calls the same catalogue builder used by the popup and user pages.

Progress and Videos are moved onto the same renderer without losing their
current figures. Built-in tabs keep showing all statements left by the header
selectors and activity buttons; page-level filters remain a user-page feature
as decided in ADR 0014. When a statement set has no matching activity type, the
tab shows a short "no data" message next to the builder placeholder instead of
a fabricated chart.

## Alternatives Considered

- **Execute the notebooks directly**: rejected. They need Jupyter widgets,
  matplotlib's notebook backend, missing helper notebooks and mutable global
  state; they cannot be used as Dash builders.
- **Add one catalogue id per notebook**: rejected. Several notebooks define
  three distinct figures (items, accessibles) or three answer figures; users
  must be able to create each one separately.
- **Add only the figures matching the five placeholder tabs**: rejected; the
  user chose all 14 notebooks.
- **Duplicate figure code in `TMonWidget`**: rejected; ADR 0013 requires one
  implementation shared by tabs and creator.
- **Add a shipped default dashboard JSON file**: rejected; the user clarified
  that "default json dashboard" means the built-in placeholder tabs.
- **Bump the configuration format version**: rejected; optional fields and
  existing parser fallbacks keep version 1 documents valid.

## Consequences

- The catalogue grows from 4 to 19 named visualisations across seven groups.
- `src/vis/` gains a shared metrics adapter and 12 notebook-matched builder
  modules; all are imported by the module-import test.
- Chart specs, links and configuration documents gain optional `target` and
  `mode` fields without invalidating existing ones.
- The built-in tabs become real visualisations of the loaded session; tabs
  whose activity types are absent from the sample data show an explicit
  placeholder until matching statements are loaded.
- New group names, visual names, selectors (`visual.target`, `visual.option`),
  mode names (`visual.mode.absolute`, `visual.mode.relative`), figure titles and
  axis labels must be translated into `en`, `es` and `fr`.
- Tests must cover every catalogue id, spec/link/config round-trips, the
  notebook-to-builder mapping, popup options and the replacement of the
  placeholder tab content.

## Status

- **Status**: Accepted
- **Date**: 2026-11-19
- **Tags**: #ui #visualization #charts #catalogue #notebooks

## See Also

- [ADR 0004](0004-chartbuilder-module.md)
- [ADR 0007](0007-shared-translations.md)
- [ADR 0012](0012-empty-visualization-page.md)
- [ADR 0013](0013-named-visualisation-catalogue.md)
- [ADR 0014](0014-page-level-filters.md)
- [ADR 0015](0015-dashboard-configuration-import-export.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
