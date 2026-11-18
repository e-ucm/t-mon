# T-Mon: Agents Documentation

## Overview

T-Mon (Traces Monitor in xAPI-SG) is a set of tools to process data in the **xAPI-SG** data format. T-Mon loads xAPI-SG statements (traces), analyzes them, and displays a default set of visualizations that provide a quick overview of its contents.

This document records architectural decisions, implementation choices, and agent readiness assessment for the API.

## Agent Readiness

### Assessment Status: ⚠️ PARTIAL

The T-Mon API has been assessed for AI agent readiness. Key gaps and decisions:

#### ✅ Agent-Ready Features
- **xAPI-SG Statement Loading**: Statements can be loaded from JSON files and LRS endpoints
- **Statement Deduplication**: Polling-based statement merging with identity-based deduplication
- **Activity Filtering**: Agents can filter statements by activity ID
- **Chart Generation**: Built-in chart types (bar, pie, line) for data visualization
- **Query Parameters**: URL-based filtering by actor, object, and activities

#### ⚠️ Agent-Requirements
- **Authentication**: Requires Keycloak/OIDC login before accessing SIMVA data
- **Study Selection**: Must select a simlet/study before analysis can be performed
- **LRS Credentials**: Direct LRS reading requires username/password in client_secrets.json
- **SimVA API Health**: Must check health endpoint to determine API dialect

#### ❌ Not Yet Agent-Ready
- **Simlet Tiles UI**: New feature - grid of simlet cards on home page (see below)
- **Browser Navigation**: Full browser navigation (studies → tests → activities) requires session state
- **Live Polling**: Requires initial study/activity selection before polling can begin

## Implementation Decisions

### Simlet Tiles (2026-11-16)

#### Decision: Add visual grid of simlets on home page
- **File**: `src/TMonWidgets/TMonWidget.py`
- **Purpose**: Provide visual access to studies without requiring browser navigation
- **Design Tokens**: Uses existing TMON.figcraft design tokens already in codebase
  - `BRAND_PRIMARY = "#078493"` - primary accent color
  - `BRAND_SOFT = "#8ec8c7"` - secondary text color
  - `LIGHT_CARD = "#fcfcfc"` - card background
  - `INTER_FONT = "Inter"` - font family
- **Tile Structure**: Each tile shows study name + ID, clickable to `/simlet{id}/`
- **Layout**: Responsive grid (4 tiles per row) with 16px margins
- **Fallback**: If no studies loaded, shows default "Please select another tab" message

#### Alternative Decision: Browser panel tiles
- **File**: `src/TMonWidgets/SimvaBrowserWidget.py`
- **When**: At root level (`/`) after SIMVA login
- **Purpose**: Replace folder buttons with simlet tiles at the studies list level
- **Condition**: `len(TMonWidgets.accepted_studies) > 0` AND `browser.current_path == browser.base_path`
- **Display**: Shows first study's tile, clicking navigates to that simlet's tests

#### Why not show tiles at all study levels?
- Tiles only at root level to avoid confusion with test/activity navigation
- Prevents mode confusion (browser navigation vs. home dashboard)
- Keeps UI consistent with existing folder button metaphor for deeper navigation

### Git History Decisions

#### `4ee91ed fix tmon structure` (2026-11-15)
- Restructured TMonWidget.py to separate concerns
- Added homepagecontent constant for default tab content
- Established pattern for tab content rendering

#### `8af7126 Add live updates feature and error handling for LRS polling in SimvaBrowser and SimvaBrowserWidget` (2026-11-12)
- Added LRS polling mechanism with error handling
- Established watermark-based incremental reading
- Required for tiles to show live data

#### `8f95b74 Add ChartBuilder module and integrate chart creation into TMonWidget` (2026-11-10)
- Added chart types: bar, line, pie, counting
- Established chart specification pattern
- Enables tiles to show data visualizations

#### `0031d35 refactor SimvaBrowser and SimvaBrowserWidget for improved API integration and error handling` (2026-11-05)
- Refactored browser to handle API dialect detection
- Added health check for SimVA API version detection
- Required before tiles can determine which API is being used

#### `f636627 fix client_secrets.json errors` (2026-11-04)
- Fixed JWT import compatibility
- Established authentication flow required for tiles

### Agent Readiness Threshold

For the API to be considered "agent-ready," the following must be configured:
1. ✅ `client_secrets.json` with valid Keycloak/OIDC configuration
2. ✅ `simva.external_url` set for LRS direct read
3. ✅ Valid studies loaded in the account
4. ⚠️ Tiles feature activated (new in this implementation)

### Known Limitations

1. **Authentication Required**: Must log in via Keycloak before any data access
2. **Study Required**: Must select at least one simlet/study before analysis
3. **LRS Optional**: Direct LRS reading requires additional credentials
4. **Tiles Context**: Only shows at home tab or browser root level, not during navigation

### Next Steps for Agent Readiness

1. **Document authentication flow** for agents
2. **Add query parameter documentation** for URL-based filtering
3. **Document the tiles feature** for discovery by other agents
4. **Add integration tests** for the tile rendering endpoint
