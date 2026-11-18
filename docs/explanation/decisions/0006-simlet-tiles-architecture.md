# ADR 0006: Simlet Tiles - Consolidated Decision

## Context and Problem Statement

T-Mon needed a visual way to display available studies (simlets) to users without requiring
them to navigate through the browser hierarchy.

## Context

### Background
The simlet tiles feature was implemented to provide visual access to studies from both
the home page and the browser panel at root level. This decision consolidates all aspects
of the simlet tiles implementation.

### Problem Statement
Users wanted quick overview of available studies without navigating through the browser
hierarchy (studies → tests → activities). The previous interface only showed folder buttons,
making discovery of studies difficult.

## Decision Drivers

### Positive Drivers
1. **User Experience**: Provide visual grid of studies for quick overview
2. **Design Consistency**: Reuse existing TMON.figcraft design tokens
3. **Two Audience Needs**: Both home page users and browser panel users need visual access
4. **Additive Feature**: No breaking changes to existing folder navigation
5. **Live Updates Support**: Integrate with existing LRS polling infrastructure

### Negative Drivers
1. **UI Complexity**: Tiles could clutter the interface if not carefully designed
2. **State Management**: Tiles must appear/disappear based on user context
3. **Error Handling**: Study names could be missing, requiring fallback behavior

### Drivers Decision
- **ADR Decision**: Adopt simlet tiles with two-appearance strategy and design token usage
- **Alternative Considered**: List format only (rejected - too text-heavy, less visual)
- **Alternative Considered**: Tiles only on home page (rejected - browser users also needed)
- **Alternative Considered**: No tiles (rejected - poor user experience)

## Decision Description

### 1. Tile Layout and Appearance
- **Grid arrangement**: 4 tiles per row with 16px margins
- **Tile dimensions**: 250px width × 180px height
- **Responsive behavior**: Tiles wrap to new rows on smaller screens
- **Fallback**: When no studies are available, display default message
- **Design tokens**: Reuse existing BRAND_PRIMARY (#078493), BRAND_SOFT (#8ec8c7),
  LIGHT_CARD (#fcfcfc), INTER_FONT ("Inter")

### 2. Two-Appearance Strategy

#### Home Page Tiles
- Appear when user selects the "HomePage" tab
- Display ALL available studies as a grid
- Provide quick visual overview without browser navigation
- Each tile shows study name (truncated at 30 chars with ellipsis) and ID
- Clicking navigates to `/simlet{id}`

#### Browser Panel Tiles
- Appear at root level (`/`) after SIMVA login when `len(TMonWidgets.accepted_studies) > 0`
- Replace folder buttons with a single tile showing the first study
- Maintain consistency with folder-based navigation metaphor
- Allow deeper navigation while still showing visual preview

### 3. Name Fallback Strategy
When a study name is not available:

1. First attempt: Use study's `name` field from API
2. Second attempt: Use study's `id` field
3. Third attempt (fallback): Display "Study" as generic label

This ensures tiles always display something meaningful.

### 4. Data Flow and State Management
- **Single source of truth**: `TMonWidgets.accepted_studies` populated from SIMVA API
- **Tile appearance conditions**:
  - Home tab: `TMonWidgets.accepted_studies` is populated
  - Browser panel: `TMonWidgets.accepted_studies` populated AND `browser.current_path == browser.base_path`
- **Error handling**: Missing study name → fallback to "Study" or ID display
- **Live updates integration**: Tiles can show recently arrived statements via existing LRS polling

### 5. Implementation Details

#### Code Organization
- **TMonWidget.py**: Contains `render_simlet_tiles()` function for home page
- **SimvaBrowserWidget.py**: Contains browser panel tile logic
- **Shared state**: Both use `TMonWidgets.accepted_studies` for data sharing

#### Key Code Conditions (from SimvaBrowserWidget.py):
```python
if (TMonWidgets.accepted_studies and
    browser.current_path == browser.base_path and
    len(TMonWidgets.accepted_studies) > 0):
    # Show tiles instead of folder buttons
```

#### Rendering Function (from TMonWidget.py):
```python
def render_simlet_tiles(studies):
    # Returns grid of clickable tiles or default message if studies empty
```

## Consequences

### Positive Consequences
- Users can quickly overview available studies from home page
- Browser users get visual context without navigating away
- Consistent look and feel using existing design tokens
- Additive feature; no breaking changes to existing functionality
- Live updates integration possible via existing infrastructure

### Negative Consequences
- Two appearance locations could confuse users if not well signposted
- Additional code maintenance for two tile rendering paths
- Slight increase in initial page load (negligible)

### Neutral Consequences
- Tiles disappear when navigating into study/test hierarchy (expected behavior)
- Name fallback displays "Study" when no name available (minor UX impact)
- Existing folder navigation remains unchanged

## Consequences Table

| Aspect | Positive Impact | Negative Impact | Neutral Impact |
|--------|----------------|-----------------|----------------|
| User Experience | Quick overview of studies | Potential confusion with two locations | - |
| Visual Design | Consistent with existing tokens | Limited customization options | - |
| Maintenance | Additive feature, no breaking changes | Two code paths to maintain | - |
| Performance | Negligible load impact | Slight increase when tiles appear | - |

## Migration Plan

### For Existing Installations
1. Update to latest T-Mon version containing the tiles feature
2. Ensure `client_secrets.json` has `simva.external_url` set
3. Studies will automatically appear on home page and browser panel (if at root level)
4. No manual migration required for existing users

### For New Installations
1. Ensure `simva.external_url` is set in `client_secrets.json`
2. Studies must be available in the SIMVA account
3. Tiles will appear automatically on home page and browser panel root level

## Related Decisions

| ADR ID | Title | Relationship |
|--------|-------|--------------|
| 0006 | Initial Plotly Demo Foundation | Established visualization foundation |
| 0007 | ChartBuilder Module | Enabled chart creation for tile details |
| 0008 | LRS Polling Mechanism | Enabled live updates for tiles |
| 0009 | client_secrets.json Fix | Enabled authentication for tiles |
| 0010 | Project Structure | Organized the codebase for this feature |

## Status

- **Status**: Accepted
- **Date**: 2026-11-16
- **Author**: T-Mon Team
- **Tags**: #simlet-tiles #ui #ux #design-tokens #decision-consolidation

## Supersedes

- 0001-simlet-tiles-architecture
- 0002-simlet-tiles-design-tokens
- 0003-simlet-tiles-data-flow
- 0004-simlet-tiles-appearance-strategy
- 0005-simlet-tiles-live-updates

## See Also

- [T-Mon Architecture explanation](explanation/architecture.md)
- [LRS Integration explanation](explanation/lrs-integration.md)
- [How-to: Tag simlets and sessions](how-to/tag-simlets-and-sessions.md)
- [Agent readiness assessment](AGENTS.md)
- [ChartBuilder module](explanation/chartbuilder-module.md)
- [LRS Polling Mechanism](explanation/lrs-polling-mechanism.md)

## Status

- **Status**: Accepted
- **Date**: 2026-11-16
- **Author**: T-Mon Team
- **Tags**: #simlet-tiles #ui #ux #design-tokens #decision-consolidation
