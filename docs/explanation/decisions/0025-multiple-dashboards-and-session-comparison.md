# ADR 0025: Multiple dashboards per session, session comparison, user dashboard assignment and sharing

## Context and Problem Statement

T-Mon currently supports a single dashboard view per session analysis. When a user opens a simlet/session, they see one dashboard with its tabs, charts and filters. This ADR addresses several limitations:

1. **Single dashboard per session**: Users cannot have multiple dashboard views for the same session, each with different focus, filters, or visualisations.
2. **No session comparison**: There is no way to open two sessions side-by-side or switch between them to compare data.
3. **No user-specific dashboard assignment**: Dashboards are not tied to specific users; any user with access sees the same view.
4. **No read-only sharing**: Users cannot share a dashboard with other teachers in read-only mode, preventing collaborative analysis without risk of modifying the original.

These limitations hinder:
- Teacher teams who want to compare different student groups across sessions
- Administrators who need to share prepared dashboards with staff
- Collaborative analysis where one user prepares a view others should only observe

## Decision Drivers

1. **Multiple dashboards per session**: A session should be able to have multiple named dashboards, each with its own tabs, charts, filters and layout.
2. **Session comparison**: Users should be able to open and compare data from multiple sessions simultaneously.
3. **User dashboard assignment**: Each authenticated user can have a default/dashboard assignment, but dashboards can also be explicitly shared.
4. **Read-only sharing**: Dashboards can be shared as read-only with other teachers, allowing them to view without modifying the original.

## Decision

### 1. Multiple dashboards per session

- Each session analysis can have **multiple named dashboards** saved independently.
- Dashboards are identified by a **dashboard name** in the URL: `/simlet/{simlet_id}/session/{session_id}/dashboard/{dashboard_name}`.
- The default dashboard remains `default`; users can also create and save custom names.
- When a URL contains a dashboard name segment, `update_tab` loads that specific saved dashboard configuration rather than the default.
- The dashboard definition format (ADR 0015) is extended to support multiple dashboards per session, with an `active_tab` per dashboard.

### 2. Session comparison

- Users can open multiple browser tabs, each pointing to a different session's dashboard.
- URL-based sharing enables direct links to specific session+dashboard combinations: `/simlet/1/session/2/dashboard/default`, `/simlet/1/session/3/dashboard/default`, etc.
- A "Compare sessions" mode can be activated from the dashboard header, which adds a session selector in the top filter bar allowing users to switch the active session while keeping the same dashboard layout and filters.
- When comparison mode is active, the dashboard title shows the currently selected session name alongside the simlet name.

### 3. User dashboard assignment

- Each authenticated user can have a **personal default dashboard** configured in their user profile.
- When a user logs in, T-Mon restores their personal default dashboard if one exists, otherwise falls back to the deployed admin default (ADR 0020).
- The user's default dashboard name is stored in the OIDC profile or in a per-user configuration file.
- Users can override their default dashboard per-session by navigating to a specific dashboard URL.

### 4. Read-only sharing to other teachers

- Dashboards can be shared with a "read" permission level, generating a **shared link** that opens the dashboard in read-only mode.
- Shared links use the URL pattern: `/simlet/{simlet_id}/session/{session_id}/dashboard/{dashboard_name}?read-only=true`.
- When accessed via a shared link:
  - The dashboard renders in read-only mode: no Edit, Remove or `+` controls are visible.
  - Header actor/object selectors and activity filters remain functional.
  - Navigation between tabs is allowed, but creating new charts, pages or filters is disabled.
  - The `?read-only=true` parameter makes the dashboard viewable by anyone with access to the study/session.
- The share button in the dashboard header allows adding `?read-only=true` to the current URL.

## Consequences

- **Positive**: Teachers can create and share multiple dashboard views for the same session, compare different sessions side-by-side, and collaborate through read-only shared links without risking the original dashboard state.
- **Positive**: Users have personal default dashboards that load on login, improving workflow efficiency.
- **Negative**: The URL schema is slightly more complex; existing bookmarks to `/simlet/{id}/session/{id}/dashboard/default` continue to work as before.
- **Negative**: Additional state management is required in the configuration store to track multiple dashboards per session.
- **Negative**: Read-only mode limits some exploratory actions, requiring users to duplicate and edit a shared dashboard if they want to modify it.
- **The `?read-only=true` parameter is transparent** - no token generation or validation is needed, making sharing simple for anyone with study/session access.

## Status

- **Status**: Accepted
- **Date**: 2026-11-25
- **Tags**: #dashboard #multi-dashboard #session-comparison #user-defaults #sharing #read-only

## See Also

- [ADR 0015](0015-dashboard-configuration-import-export.md) — dashboard configuration format and save/load
- [ADR 0017](0017-user-defined-default-dashboard-definition.md) — user-defined default dashboard definition
- [ADR 0018](0018-edit-mode-for-tabs-and-visualisations.md) — edit mode for dashboards
- [ADR 0019](0019-dashboard-polish-url-hover-adaptive-slots.md) — dashboard polish features
- [ADR 0020](0020-dashboard-ownership-admin-default.md) — dashboard ownership and roles
- [ADR 0022](0022-dashboard-routing-by-name.md) — dashboard routing by name in URL
- [ADR 0023](0023-auto-load-dashboard-on-direct-url.md) — auto-load dashboard on direct URL
- [T-Mon application reference](../../reference/tmon-app-reference.md)
