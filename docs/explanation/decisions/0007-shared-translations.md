# ADR 0007: Shared translations across SIMVA, T-Mon and Pumva

## Context and Problem Statement

The SIMVA ecosystem contains several front ends that describe the same UI with
the same words. `simva-front` (Node/Express + EJS) keeps its translations in
i18next namespace files under `locales/<lng>/<ns>.json`. T-Mon (Python/Dash)
was given a small custom i18n layer with flat `src/locales/<lng>.json` files.
`pumva` is a separate TypeScript repository.

The two catalogues named identical strings differently — for example simva's
`header.contact.title` versus T-Mon's `header.contact`, and simva's
`info.created_at` versus T-Mon's `simlets.created_at`. Adding i18n to T-Mon
therefore meant translating everything again. Every project also builds its own
Docker image from its own context, so a sibling checkout such as
`../simva-front/locales` is available locally but not in a deployed container.

## Decision Drivers

1. **No duplicate translation work**: a label should be translated once for the
   whole ecosystem.
2. **Consistent wording**: the same concept should read identically in SIMVA,
   T-Mon and Pumva.
3. **Canonical source**: `simva-front`'s existing keys and namespace layout are
   the reference, since they are already in use and cover the shared vocabulary.
4. **Independent deployments**: each project must remain buildable from its own
   repository.
5. **Low-risk migration**: the shared package should not be a prerequisite for
   fixing T-Mon's duplicated keys.

## Decision Description

### 1. Canonical keys

`simva-front`'s key names and namespace layout (`<lng>/<ns>.json`) are
canonical. New shared keys are added to `commons.json` (or the relevant
namespace) in the shared source; consuming projects do not invent local
variants.

### 2. Long-term: a published `@simva/i18n` package

Create a repository containing only locale JSON, starting as a copy of
`simva-front/locales`, and publish it as `@simva/i18n`.

- `simva-front`: point i18next `backend.loadPath` at the package; keep an
  optional local `overrides/` path for front-only strings.
- `pumva` (TypeScript): install the same package and use the same i18next
  backend path.
- `t-mon`: load the shared JSON at build time (copy into the image or read from
  the installed package) and merge local override files for T-Mon-only strings.

This is preferred over a git submodule or a build-time copy because both other
projects are JS/TS and already run `npm ci`, so sharing is a dependency change
rather than a new build mechanism.

### 3. Interim change (applied)

T-Mon's keys were renamed to the canonical simva keys, and the values for those
keys were copied from `simva-front/locales` instead of being re-translated.
T-Mon still owns `src/locales/*.json`, but with canonical keys; moving to the
shared package later is then only a path change. Keys without a simva equivalent
remain explicit T-Mon additions.

#### Key mapping applied

| Previous T-Mon key | Canonical simva key |
|---|---|
| `header.contact` | `header.contact.title` |
| `header.login` | `header.login.title` |
| `header.logout` | `header.logout.title` |
| `simlets.search` | `simlets.search_bar.placeholder` |
| `simlets.created_at` | `info.created_at` |
| `simlets.updated_at` | `info.updated_at` |
| `simlets.sort_by` | `filters.sort_by.title` |
| `sort.default` | `filters.sort_by.id` |
| `sort.name_asc` | `filters.sort_by.name.asc` |
| `sort.name_desc` | `filters.sort_by.name.desc` |
| `sort.created_desc` | `filters.sort_by.created_at.desc` |
| `sort.created_asc` | `filters.sort_by.created_at.asc` |
| `sort.updated_desc` | `filters.sort_by.updated_at.desc` |
| `sort.updated_asc` | `filters.sort_by.updated_at.asc` |
| `simlets.active` | `sessions.status.active.title` |
| `simlets.archived` | `simlets.status.archived` (new canonical key) |
| `simlets.groups` | `groups.title` |
| `simlets.participants` | `participants.title` (new canonical key) |
| `simlets.tags` | `info.tags` |
| `simlets.no_tags` | `info.tags.no_tags` |
| `simlets.sessions` | `sessions.title` |
| `simlets.status` | `filters.status.title` (new canonical key) |
| `sessions.search` | `sessions.search_bar.placeholder` |
| `sessions.no_matches` | `filters.search.no_matches.message` |
| `sessions.activities` | `activities.title` |
| `status.all` | `filters.status.all` |
| `status.paused` | `sessions.status.paused.title` |
| `status.finished` | `sessions.status.finished.title` |

Keys added to the canonical set for T-Mon (no existing simva equivalent):
`header.language`, `app.tab.simva`, `app.tab.upload`, `header.account`,
`upload.login_notice`, `browser.select_simlet`, `browser.select_test`,
`browser.select_activity`, `browser.run_analyse`, `browser.connect`,
`simlets.title`, `simlets.previous`, `simlets.next`, `simlets.no_studies`,
`sessions.general_tab`, `sessions.sessions_tab`, `sessions.placeholder`,
`filters.status.title`, `simlets.status.archived`, `participants.title`.

### 4. Language detection

Detection should converge on `lng` query parameter → cookie `i18next` →
fallback `en`, matching `simva-front`. T-Mon currently stores the choice in the
Flask session; that can be aligned when the shared package is introduced.

## Alternatives Considered

- **Git submodule with a shared `locales/` directory**: rejected because every
  checkout and CI job would need submodule handling, and merge conflicts would
  be shared across three projects.
- **Build-time copy from `simva-front` into T-Mon**: rejected as the permanent
  solution because it couples two independent repositories; kept only as the
  interim rationale for reusing wording.
- **Each project keeps its own keys and translations**: rejected — this is the
  problem being solved.

## Consequences

- A translation is written once in `@simva/i18n`; adding a language happens in
  one place.
- T-Mon's `I18n.py` becomes a thin loader over shared JSON plus overrides.
- Until the package exists, T-Mon still ships its own locale files, but they are
  keyed identically to simva-front, so the eventual switch needs no renaming.
- The interim mapping must be kept in sync if new shared keys are introduced.

## Status

- **Status**: Accepted (interim step implemented; shared package proposed)
- **Date**: 2026-11-18
- **Author**: T-Mon Team
- **Tags**: #i18n #translations #simva-front #tmon #pumva

## See Also

- [T-Mon application reference](../../reference/tmon-app-reference.md)
- [Simlet tiles reference](../../reference/simlet-tiles.md)
- [Agent readiness assessment](../../../AGENTS.md)
