# ADR 0010: Simlet card metadata and participant count

## Context and Problem Statement

The first tile implementation showed only a name and an id. The SimVA front-end
cards show creation and update dates, session/group/participant counts and
coloured tags. T-Mon needed the same information without inventing new data
sources.

## Decision Drivers

1. Reuse fields already returned by `GET /simlets`.
2. Match the SimVA front-end's labels and tag colours.
3. Do not fail the whole studies list if a metadata request fails.

## Decision

### Fields

A tile reads the raw simlet object through tolerant accessors supporting both
the current API (`simlet_id`, `simlet_name`, `createdAt`, `updatedAt`) and the
legacy dialect (`_id`, `_name`). It shows:

- name;
- `Created at` and `Updated at`, formatted `YYYY/MM/DD`;
- `Sessions` and `Groups` as list lengths;
- `Participants` from a dedicated count request;
- `Tags` as chips using each tag's `tag_name` and `tag_color`, or `No tags`.

Text is dark on the light card; tag chips choose white or dark text from a
brightness check so light tag colours stay readable.

### Participant count

The count is not on the simlet object. `SimvaBrowser` calls the authenticated
endpoint:

```
GET /simlets/<id>/groups/participants/count
```

The API answers with a map of group id to count, for example
`{"1": 1, "2": 5}`; the values are summed (6). A bare number, a numeric string
or a `count`/`participants` envelope are also accepted. An absent id, network
error, non-200 response or invalid JSON yields 0 and is logged. The value is
annotated onto the simlet as `participants_count` while the studies list loads.

### Normalisation

`render_simlet_section` keeps the whole raw object and adds `id`/`name` keys,
so metadata is not discarded. The dashboard home tab passes raw objects
directly; both paths use the same renderer.

## Alternatives Considered

- Derive participants from the `groups` list: rejected, because group ids carry
  no participant information.
- Fetch the complete session data for each simlet: rejected; far more requests
  than the count endpoint.
- Store the count in a global cache: rejected; loading the studies list is the
  single authoritative moment.

## Consequences

- One extra authenticated request per simlet at login, with a 5s timeout.
- A failing count endpoint degrades to 0 instead of breaking the grid.
- Tag colours come from SimVA data and need no T-Mon-side palette.

## Status

- **Status**: Accepted
- **Date**: 2026-11-18
- **Tags**: #simlets #api #metadata #ui

## See Also

- [ADR 0006](0006-simlet-tiles-architecture.md)
- [Simlet tiles reference](../../reference/simlet-tiles.md)
