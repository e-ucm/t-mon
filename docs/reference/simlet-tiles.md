# Reference: Simlet Tiles

## API Reference

### `render_simlet_tiles(studies)` Function

**File**: `src/TMonWidgets/TMonWidget.py`

**Signature**:
```python
def render_simlet_tiles(studies) -> dash.html.Div
```

**Parameters**:
- `studies` (list): List of study objects from the SimVA API

**Returns**:
- `dash.html.Div`: A Div containing the tile grid, or a default message if studies is empty

**Behavior**:
- If `studies` is empty or None: Returns `Div("No studies available. Please log in and load a study.")`
- If `studies` has content: Returns a Div containing the tile grid HTML

**Tile HTML Structure**:
```html
<div style="...">  <!-- Tile container -->
  <a href="/simlet/{id}">  <!-- Clickable link -->
    <div style="...">  <!-- Study name -->
      {name[:30] + ("..." if len(name) > 30 else "")}
    </div>
    <div style="...">  <!-- Study ID -->
      ID: {id}
    </div>
  </a>
</div>
```

### Browser Panel Tile Condition

**File**: `src/TMonWidgets/SimvaBrowserWidget.py`

**Condition**:
```python
if (TMonWidgets.accepted_studies and
    browser.current_path == browser.base_path and
    len(TMonWidgets.accepted_studies) > 0):
```

**Behavior**:
- Only executes when all three conditions are met:
  1. `TMonWidgets.accepted_studies` is populated (studies loaded from SIMVA)
  2. Browser is at base path (`browser.current_path == browser.base_path`)
  3. At least one study is available (`len(TMonWidgets.accepted_studies) > 0`)

**Tile Display**:
- Uses first study from `TMonWidgets.accepted_studies[0]`
- Shows study name (truncated at 30 chars with ellipsis)
- Shows study ID below the name
- Tile links to `/simlet/{id}`

### Design Tokens Used

| Token | Value | Usage |
|-------|-------|-------|
| `BRAND_PRIMARY` | `#078493` | Primary text color, link color |
| `BRAND_SOFT` | `#8ec8c7` | Secondary text color (IDs) |
| `LIGHT_CARD` | `#fcfcfc` | Tile background color |
| `INTER_FONT` | `Inter` | Font family for all text |

### Study Object Fields

| Field | Source | Description |
|-------|--------|-------------|
| `id` | API response | Study/simlet identifier |
| `name` | API response | Study display name |
| `accepted_studies` | `TMonWidgets` | List of all available studies |

## Configuration

### Required for Tiles to Appear

1. **client_secrets.json**:
   - Valid Keycloak/OIDC configuration
   - `simva.external_url` set for LRS direct read

2. **SIMVA Account**:
   - At least one study (simlet) available
   - Studies must have `id` and `name` fields (name optional, fallback available)

3. **T-Mon Setup**:
   - User must be authenticated via Keycloak/OIDC
   - Studies must be loaded via the SIMVA browser

### Environment Variables

No new environment variables required. Uses existing configuration.

### Default Values

| Setting | Default | Description |
|---------|---------|-------------|
| Tile margin | `16px` | Fixed margin between tiles |
| Tile width | `250px` | Fixed tile width |
| Tile height | `180px` | Fixed tile height |
| Name truncation | `30 chars` | Maximum study name length before ellipsis |

### Error Handling

#### Possible Error States

| Scenario | Error Shown | Action |
|----------|-------------|--------|
| No studies available | "No studies available. Please log in and load a study." | User logs in and loads studies |
| Study has no name | "Study" + ID displayed | Normal fallback behavior |
| API error during load | Tiles not shown | Error logged to console |
| Browser not at root level | Folder buttons shown (not tiles) | Navigate to `/` or home tab |

### Logging

- Tiles rendering status logged to console at INFO level
- Errors during tile rendering logged at ERROR level
- Study count and path status logged for debugging

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 2026-11-16 | Initial implementation with two appearance locations |
| 2026-11-15 | Added name fallback strategy |
| 2026-11-12 | Fixed TypeError for None study names |
| 2026-11-10 | Added browser panel tile support |

### See Also

- [TMonWidget.py source](src/TMonWidgets/TMonWidget.py)
- [SimvaBrowserWidget.py source](src/TMonWidgets/SimvaBrowserWidget.py)
- [AGENTS.md agent readiness assessment](AGENTS.md)
- [How-to: Tag simlets and sessions](how-to/tag-simlets-and-sessions.md)
- [LRS Integration explanation](explanation/lrs-integration.md)

