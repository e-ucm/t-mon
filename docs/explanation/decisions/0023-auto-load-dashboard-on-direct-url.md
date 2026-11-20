# ADR 0023: Auto-load the dashboard on a direct URL

## Context and Problem Statement

A dashboard URL such as `/simlet/1/session/1/dashboard/default` is produced after an
analysis, but opening it directly did not load any statements: `init_storage` restored
the browser's directory but never ran the analysis, so `output-t-mon` stayed hidden
and the browser mode remained on screen.

## Decision

- `init_storage` now returns `output-t-mon`'s style and the `url` pathname as well as
  the browser div, with `prevent_initial_call='initial_duplicate'` so the initial
  load still runs.
- When the restored selection is analysable (`browser.analysis_ready`), it calls
  `get_analysis_outputs` during the initial load and returns the block style and the
  dashboard URL, so the dashboard opens without a button click.
- A non-analysable or logged-out load returns a hidden style and `no_update` for the
  URL, leaving the browser mode visible.

## Consequences

- Visiting a dashboard URL directly loads its statements and shows the dashboard
  instead of the browser.
- The browser callback keeps its existing outputs; the new ones use `allow_duplicate`.
EOF
echo done