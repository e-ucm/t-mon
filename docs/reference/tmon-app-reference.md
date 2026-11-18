# Reference: T-Mon Application

## Overview

This reference document provides factual information about the T-Mon application components,
API, and configuration. It serves as a technical reference for developers and advanced users.

## Application Structure

### Directory Layout

```
t-mon/
├── docs/                    # Documentation (Diátaxis method)
│   ├── explanation/         # Background and design decisions
│   ├── how-to/              # Task completion guides
│   ├── reference/           # Factual API and component information
│   └── tutorials/           # Step-by-step learning paths
├── src/                     # Source code
│   ├── TMonWidgets/         # Widget components
│   ├── SimvaBrowser/        # SIMVA browser integration
│   ├── TMonApp.py           # Main application entry point
│   └── ...                  # Other modules
├── docs/                    # Root documentation
├── AGENTS.md                # Agent readiness assessment
├── client_secrets.json      # Authentication configuration
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container configuration
└── ...                      # Other project files
```

### Key Modules

#### `src/TMonWidgets/`

- **TMonWidget.py**: Main widget component with chart creation, filtering, and display logic
- **SimvaBrowserWidget.py**: Browser panel for navigating studies, tests, and activities
- **ChartBuilder.py**: Chart creation and management module
- **other modules**: ActivityFilter, data processing, etc.

#### `src/SimvaBrowser/`

- **SimvaBrowser.py**: Core browser integration with SIMVA API
- **SimvaAPIBrowser.py**: API integration layer
- **KeycloakClient.py**: Authentication via Keycloak/OIDC
- **other modules**: Data processing, authentication, etc.

#### `src/TMonApp.py`

- Main application setup and routing
- Dashboard layout configuration
- Callback definitions for interactivity

### Shared Header

`src/TMonWidgets/TMonWidget.py` exposes `build_header(with_login=False)`, which builds the
sticky top bar used by both apps. It follows the SIMVA front-end header: a compact
orange bar with the T-Mon logo and "Txmon - The xAPI Trace Monitor" on the left, and a
right-hand nav with a language selector, Contact us, the signed-in username and a black
Login/Logout pill. The icons and logo live in `src/assets/` but are embedded as data
URIs, so they still appear behind a path prefix where `/assets/...` would not resolve.

The SIMVA app uses `TMonSimvaHeader = build_header(with_login=True)`; the account item
shows only the username and is hidden while logged out. The local file-upload app uses
`TMonHeader` without the account controls. The login callbacks in
`SimvaBrowserWidget.py` keep targeting the same component ids (`main-login`,
`login-logout-button`, `account-button`, `connection-status`), so moving the controls
into the header did not change their behaviour.

Text comes from `src/locales/<lang>.json` through `TMonWidgets/I18n.py` (`en`, `es`,
`fr`). The header selector writes `lng` into the URL and reloads, like SIMVA's i18n.

`TMonFooter` is pinned to the bottom: both app layouts are flex columns with
`minHeight: 100vh`, and the footer uses `marginTop: auto` plus `position: sticky; bottom: 0`.
That keeps it at the bottom of a short page and in view while a long page scrolls.

### Application Modes

Below the header, `TMonSimvaApp` has two top tabs: **SIMVA** (the default) shows the
simlet browser, and **Upload file** shows the local `dcc.Upload` drop zone used for
xAPI-SG JSON files. The `switch_mode` callback shows only the selected panel; the
dashboard, the shared result log (`content`) and the footer stay in place. Files dropped
in the Upload tab are always treated as local files, even when a SIMVA session is open
in the other tab. Uploading requires a SIMVA login: when logged out the drop zone is
hidden and the tab shows a "Please log in to upload files" notice.

At the browser root the SIMVA tab shows a **Simlets** grid with one tile per study;
`toggle_browser_chrome` hides the study/test/activity headings and the `..` button there
because nothing is selected yet, and hides all of them for logged-out visitors too.
For logged-in users they reappear when a study is opened, and the Simlets grid comes
back when you navigate up to the root again. Tile links point at
`/simlet{id}`.

### Core Concepts

#### Studies (Simlets)

- **Definition**: A study (simlet) represents a collection of related activities in the SIMVA system
- **Structure**: Studies contain tests, which contain activities
- **Navigation**: Studies → Tests → Activities → Analysis

#### Studies Browser

- **Breadth-first navigation**: Browse studies → select test → select activity
- **Directory structure**: Uses directory-style navigation with folder buttons
- **Tile view**: Visual grid of studies on home page and root level

#### LRS (Learning Record Store)

- **Direct read**: Connect to LRS with username/password for full statement queries
- **Polling**: Periodic queries for new statements (live updates)
- **Watermark-based**: Incremental queries based on statement timestamps

#### Charts and Visualizations

- **Chart types**: Bar, line, pie, counting
- **Specifications**: Reusable chart specifications stored in references
- **Custom creation**: User-defined charts in the "Create" tab
- **Aggregation**: Count, sum, average, min, max

## Configuration

### client_secrets.json

Required configuration fields:

```json
{
  "simva": {
    "api_url": "https://your-simva-instance.com",
    "external_url": "https://your-simva-instance.com",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "use_lrs": true/false
  },
  "lrs": {
    "endpoint": "https://your-lrs-instance.com/xAPI/",
    "username": "your-lrs-username",
    "password": "your-lrs-password",
    "lrs_lag_seconds": 60
  }
}
```

### Environment Variables

No environment variables are required beyond the client_secrets.json configuration.

### Diátaxis Documentation Structure

The documentation follows the Diátaxis method with four categories:

1. **Explanation** (`docs/explanation/`): Background, concepts, and decisions
   - `architecture.md` - System architecture
   - `decisions/` - Architecture Decision Records
   - `lrs-integration.md` - LRS integration details

2. **How-to** (`docs/how-to/`): Task completion guides
   - `tmon-app-guide.md` - This guide
   - `tag-simlets-and-sessions.md` - Managing studies and sessions
   - `query-xapi-statements.md` - Querying xAPI data

3. **Reference** (`docs/reference/`): Factual information
   - `tmon-app-reference.md` - This reference
   - `activity-types.md` - Activity type definitions
   - `data-model.md` - Data model specifications

4. **Tutorials** (`docs/tutorials/`): Step-by-step learning paths
   - `01-first-study.md` - Getting started
   - `02-run-a-study.md` - Running analysis
   - `03-read-the-data.md` - Reading data
   - `04-simlet-tiles.md` - Using simlet tiles

### API Endpoints

The T-Mon application provides the following API endpoints (via the SimVA backend):

- **Studies endpoint**: `/simlets` - List available studies
- **Tests endpoint**: `/simlets/{id}/tests` - List tests within a study
- **Activities endpoint**: `/simlets/{id}/tests/{test_id}/activities` - List activities
- **Analysis endpoint**: Queries LRS for statements
- **Authentication**: Keycloak/OIDC token-based authentication

### Data Model

#### Study Object

```json
{
  "id": "simlet-123",
  "name": "Study Name",
  "description": "Study description",
  "tests": ["test-1", "test-2", ...],
  "activities": ["activity-1", "activity-2", ...]
}
```

#### Statement Object

```json
{
  "id": "stmt-12345",
  "agent": {
    "objectName": "Player 1",
    "mbox": "mailto:player1@example.com"
  },
  "verb": {
    "id": "http://adlnet.gov/expapi/verbs/initialized",
    "display": {
      "en-US": "initialized"
    }
  },
  "object": {
    "objectType": "Activity",
    "id": "activity-123",
    "definition": {
      "type": "http://adlnet.gov/expapi/activities/activity",
      "name": {
        "en-US": "Activity Name"
      }
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "liked": false
}
```

### Chart Specifications

#### Available Chart Types

| Chart Type | Description | Data Requirements |
|------------|-------------|-------------------|
| **Bar** | Comparative bar chart | Categorical x, numerical y |
| **Line** | Time series or trend line | Temporal x, numerical y |
| **Pie** | Proportional distribution | Categorical data, numerical values |
| **Counting** | Simple count display | No specific requirements |

#### Chart Specification Fields

```json
{
  "type": "bar",
  "x": "activity.name",
  "y": "count",
  "aggregation": "count"
}
```

- **type**: Chart type (bar, line, pie, counting)
- **x**: Column name for the x-axis
- **y**: Column name for the y-axis
- **aggregation**: Aggregation method (count, sum, average, min, max)

## Error Handling

### Common Error Codes

| Error | Meaning | Resolution |
|-------|---------|------------|
| 401 | Authentication failed | Check client_secrets.json credentials |
| 404 | Resource not found | Verify study/test/activity exists |
| 500 | Server error | Check console for details, restart application |
| 429 | Rate limited | Wait before retrying or reduce polling frequency |

### Error Messages

| Message | Meaning | Resolution |
|---------|---------|------------|
| "No xAPI statements available" | No data for the selected study/test/activity | Verify data exists in LRS |
| "LRS unreachable" | Cannot connect to LRS | Check LRS credentials and network |
| "Authentication failed" | Invalid Keycloak/OIDC credentials | Verify client_secrets.json |
| "Study not found" | Study not in your account | Verify study access permissions |

## Glossary

| Term | Definition |
|------|------------|
| **Study (Simlet)** | A collection of related activities in the SIMVA system |
| **LRS** | Learning Record Store - stores xAPI statements |
| **xAPI** | Experience API - standard for learning data |
| **Keycloak** | OpenID Connect authentication provider |
| **LRS Polling** | Periodic queries for new statements |
| **Watermark** | Timestamp-based incremental query mechanism |
| **Aggregation** | Statistical method for summarizing data |
| **Chart Specification** | Reusable chart configuration |

## Versioning

### T-Mon Versioning

The T-Mon application follows semantic versioning principles:

- **Major version**: Breaking changes to the application
- **Minor version**: New features and improvements
- **Patch version**: Bug fixes and minor changes

### Documentation Versioning

Documentation versions align with the T-Mon application version:

- **Latest version**: Always reflect the current application state
- **Historical versions**: Available in the Git history

### Changelog

Changes are tracked in the Git commit history and documented in the
`CHANGES.md` file (if present) or the `AGENTS.md` file.

## Related Resources

### Internal Links

- [T-Mon GitHub Repository](...): Source code and issues
- [AGENTS.md](AGENTS.md): Agent readiness assessment
- [client_secrets.json](client_secrets.json): Configuration file
- [SimVA API Documentation](...): Backend API details

### External Resources

- [xAPI-SG Specification](...): The data standard
- [Keycloak Documentation](...): Authentication details
- [LRS Documentation](...): Learning Record Store configuration
- [W3C xAPI](...): The xAPI specification

## Version History

### Recent Changes

| Version | Date | Changes |
|---------|------|---------|
| latest | 2026-11-16 | Simlet tiles feature added |
| 1.0.0 | 2024-07-12 | Initial Plotly demo foundation |
| 0.9.0 | 2026-09-30 | ChartBuilder module added |
| 0.8.0 | 2026-09-28 | LRS polling mechanism added |

### Upcoming Changes

- Planned features and their expected release versions
- Deprecation warnings for soon-to-be-removed features

## Contact and Support

- **Source Code**: [T-Mon GitHub Repository](...)
- **Issues**: [GitHub Issues](...)
- **Documentation**: This reference guide
- **Support**: [T-Mon Support Team](...)

## Licensing

T-Mon is open source software under the license specified in the `LICENSE` file.

*Last updated: November 2026*
*T-Mon version: latest*
