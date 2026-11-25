# ADR 0022: Dashboard routing by name in the URL

## Context and Problem Statement

A dashboard URL ends in `/dashboard/<segment>`. Until now `/dashboard/default` was treated
as "no tab selected" for a session (so the simlet/session names showed first), and any
other segment was ignored, so `/dashboard/xxx` could not open a saved dashboard. Users
expect `/dashboard/default` to open the default dashboard and `/dashboard/xxx` to open
the dashboard saved under the name `xxx`.

## Decision

- `update_tab` now interprets the segment after `/dashboard/`:
  - `default` opens the default dashboard with its `home_tab` selected, even inside a
    session, instead of the no-tab view.
  - a segment containing `tab=` keeps the existing tab/user/object parsing.
  - any other segment is treated as the name of a saved dashboard: `load_named` is
    called and, on success, its `active_tab`, header selections and
    `default_graph_overrides` are applied through `config-command`. A missing name
    falls back to `home_tab`.
- The no-tab view is now reserved for a URL with an empty dashboard segment
  (`/dashboard/`), which is what a fresh session analysis without an explicit dashboard
  produces.
- `update_tab` gains a fourth output, `config-command`, so a named dashboard in the URL
  can be loaded through the same path as the configuration importer.

## Consequences

- `/simlet/1/session/1/dashboard/default` opens the default dashboard instead of the
  session's no-tab view.
- `/simlet/1/session/1/dashboard/xxx` opens the saved dashboard `xxx`.
- The configuration file format is unchanged.
EOF
echo done