# ADR 0013: Named visualisation catalogue

## Context and Problem Statement

The Progress and Videos tabs build their figures inline in `update_output`: for
each serious game a progress line, a progress line from a common origin and a
started/completed pie (`vis/xAPISGPlayersProgress.py`), plus one video
seen/skipped bar (`vis/xAPISGVideosSeenSkipped.py`). The creator, in contrast,
can only build generic bar, line, pie and scatter charts from column
descriptions. The figures users actually see in those tabs cannot be placed on
a page of their own.

## Decision Drivers

1. All four existing figures must be creatable directly in the UI.
2. The Progress and Videos tabs keep their figures; they do not become empty
   pages.
3. Figure-building code must have one implementation, shared by the tabs and by
   the creator, so the two cannot drift apart.
4. A progress figure targets one serious game chosen from the loaded data.
5. Created figures must live in the same `created-charts` store and URL carrying
   as generic charts ([ADR 0004](0004-chartbuilder-module.md)).
6. Every new label comes from the translation catalogue
   ([ADR 0007](0007-shared-translations.md)).

## Decision

### Catalogue

A new `TMonWidgets/VisualizationCatalog.py` holds four named entries:

- `progress-line` — progress over raw statement timestamps;
- `progress-origin` — progress from the first timestamp of each actor;
- `progress-pie` — actors who started and completed versus only started;
- `video-seen-skipped` — cutscenes seen and skipped.

Each entry carries an id, an i18n label key, whether it needs a `game`
parameter, and a builder function. The three progress entries need a game; the
video entry does not. The builders delegate to the existing `vis/` functions
rather than reimplementing the figures.

### Shared builders

The Progress and Videos tabs call the same catalogue builders the creator uses,
so an added chart and the figure in its original tab are identical. The
progress builders are made order-independent: the current module-level
`result_progress_column` is set as a side effect of `ProgressPlayerLineChart`,
which would make a named builder depend on call order. The progress column is
resolved inside each builder instead.

### Chart descriptions

A description may carry a `visual` id and a `game` alongside the generic `type`,
`x`, `y` and `aggregation` fields. `normalise_spec` accepts a `visual` only when
it names a catalogue entry and validates the game where one is needed;
`build_chart` dispatches to the named builder or to the generic chart builder;
`describe` uses the catalogue label. `encode_spec` and `decode_specs` append the
two fields to the compact form, so descriptions written before this decision —
which carry four fields — still load and draw as before. `MAX_CREATED_CHARTS` is
unchanged.

### Creation popup

The popup from [ADR 0012](0012-empty-visualization-page.md) gains a Progress and
a Videos group alongside the generic chart types. Choosing a progress visual
shows a dropdown of the serious-game `object.id` values present in the filtered
statements; one selected game produces one chart. The video visual needs no
extra choice.

## Alternatives Considered

- Duplicate the figure code in the creator: rejected; two implementations of
  the same chart would diverge.
- Create the figures for every game at once: rejected; the user chose one game
  per chart through a dropdown.
- Remove the auto-rendered figures from the Progress and Videos tabs: rejected;
  those tabs keep working as before.
- Drop generic charts now that named ones exist: rejected; arbitrary columns
  are still useful for exploring a session.

## Consequences

- Every figure in the dashboard has one builder, used by both tabs and creator.
- Chart descriptions and links gain optional fields while remaining readable by
  older versions of the dashboard.
- The progress visualisation module no longer relies on call order.
- New labels (groups, visual names, game selector) must be added to all three
  locale files.

## Status

- **Status**: Accepted
- **Date**: 2026-11-19
- **Tags**: #ui #visualization #charts #catalogue

## See Also

- [ADR 0004](0004-chartbuilder-module.md)
- [ADR 0007](0007-shared-translations.md)
- [ADR 0012](0012-empty-visualization-page.md)
- [T-Mon application reference](../../reference/tmon-app-reference.md)
