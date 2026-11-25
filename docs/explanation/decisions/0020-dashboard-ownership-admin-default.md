# ADR 0020: Dashboard ownership — admin-owned default, user-created dashboards

## Context and Problem Statement

T-Mon ships one deployed default dashboard (`src/config/default-dashboard.json`)
whose tabs, graphs and labels describe the standard view. On top of it, a user can
add named pages, charts and filters, and save the result as a named configuration
(ADR 0015). Editing the default dashboard's own graphs changes what every user
sees, so it must not be open to everyone; creating a personal dashboard must
remain open to everyone.

## Decision

- **The default dashboard is admin-owned.** Only an administrator sees the Edit
  control on a default-dashboard graph and only an administrator can write an
  override into the `default-graph-overrides` store. The deployed
  `default-dashboard.json` is never modified by the application; an override lives
  in the user's configuration or in memory.
- **Named dashboards are user-owned.** Any signed-in user can add, rename and
  delete named pages, create charts and filters on the Create tab, and save or
  load a named configuration. Those mutations go through `update_page_state` and
  the `config-*` callbacks exactly as before.
- **Roles.** SimVA issues `administrator`, `researcher`, `teaching-assistant`,
  `teacher`, `student` and `default-role`. `UserRoles.is_admin()` is true only
  for `administrator`. Role claims are read from both the OIDC profile and the
  decoded access token, under `roles`, `groups`, `realm_access.roles` and
  `resource_access.*.roles`.
- **Read-only default for non-administrators.** A non-administrator viewing the
  default dashboard sees its graphs and labels but no Edit, Remove or `+` control
  that would change them. They can still build and save their own dashboard on
  top of it.

## Consequences

- The default view stays consistent for all users unless an administrator changes
  it; administrators' edits travel through configurations like any other change.
- Non-administrators are not blocked from creating personal dashboards.
- No change to the configuration file format beyond `default_graph_overrides`,
  which is empty for documents that never touched the default dashboard.
EOF
echo done