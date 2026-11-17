# Tutorial: Using Simlet Tiles in T-Mon

## Objectives

By the end of this tutorial, you will be able to:

1. Recognize when simlet tiles are available
2. Interpret the information displayed on tiles
3. Navigate from tiles to study details
4. Troubleshoot common issues with tile display

## What Are Simlet Tiles?

Simlet tiles are a visual grid of studies (simlets) available in your SIMVA account.
They provide a quick overview without requiring you to navigate through the browser
hierarchy.

## When You'll See Tiles

### 1. On the Home Page

- When you select the "HomePage" tab
- If your SIMVA account has studies → you'll see a grid of clickable tiles
- If no studies → default message "Please select another tab"

### 2. In the Browser Panel

- After logging into SIMVA
- When you're at the root level (stay on `/` or don't navigate into a specific study)
- If studies are available → folder buttons are replaced with a tile grid
- Only the first study's tile is shown (browser panel behavior)

## Tile Information

Each tile displays:

- **Study name**: Truncated to 30 characters with ellipsis if longer
- **Study ID**: Shown below the name
- **Clickability**: Tiles are clickable links
- **Navigation**: Clicking a tile takes you to `/dashboard/study/{id}/`

## Step-by-Step: Using Home Page Tiles

### Step 1: Log In

1. Open T-Mon in your browser
2. Click "Login" or "Sign in"
3. Complete the Keycloak/OIDC authentication flow
4. You should see "Logged in as [your username]"

### Step 2: Navigate to Home Page

1. Once logged in, click the "HomePage" tab
2. The home page will load
3. Wait a moment for studies to load from your SIMVA account

### Step 3: Observe Tiles

1. If studies are available in your SIMVA account, a grid of tiles should appear
2. Each tile shows:
   - Study name (truncated to 30 chars with ellipsis if longer)
   - Study ID below the name
3. If no studies are available, you'll see:
   - "No studies available. Please log in and load a study."

### Step 4: Interact with Tiles

1. Click on a tile that interests you
2. You'll be taken to `/dashboard/study/{id}/`
3. From there, you can:
   - View study details
   - Select tests within the study
   - Select activities within a test
   - Run analysis and view visualizations

## Step-by-Step: Using Browser Panel Tiles

### Step 1: Log In (Same as above)

### Step 2: Stay at Root Level

1. After logging in, ensure you're on the main browser view
2. The URL should be `/` or your browser path should be just the base
3. Don't click into any study or test yet

### Step 2: Observe Browser Panel

1. Look at the folder/button area in the browser panel
2. If studies are available, folder buttons should be replaced with a tile
3. The tile will show the first study from your account

### Step 2: Interact with the Tile

1. Click the tile shown in the browser panel
2. You'll be taken to that simlet's tests
3. From there, you can navigate into activities and run analysis

## Common Issues

### Tiles Not Appearing

**Possible causes and solutions**:

| Issue | Solution |
|-------|----------|
| Not logged in | Complete Keycloak authentication |
| No studies in account | Add studies to your SIMVA account |
| On different page | Navigate to HomePage tab or ensure you're at root level |
| Browser error | Refresh the page or check console for errors |

### Tiles Showing "Study" Text

**This is normal behavior**:

- Means a study was found but no name field was available
- The fallback "Study" text is displayed
- The study ID is still shown below
- Tiles function normally despite this display

### Only One Tile Showing (Browser Panel)

**This is by design**:

- Browser panel only shows the first study's tile
- To see other studies, use the Home Page tab
- Or navigate into the study from the browser

## Best Practices

### For End Users

1. **Check both locations**: Tiles can appear on Home Page OR Browser Panel
2. **Note the location**: Tiles on Home Page show all studies; browser panel shows first study
3. **Click to explore**: Tiles are gateways to detailed study views
4. **Refresh if needed**: If tiles don't appear, try refreshing or navigating away/back

### For Administrators

1. Ensure `simva.external_url` is set in `client_secrets.json` for LRS direct read
2. Verify studies are available in the SIMVA account
3. Monitor console logs for tile rendering errors
4. The tiles feature is additive; existing folder navigation remains unchanged

## Frequently Asked Questions

### Q: Why do tiles sometimes not appear?

A: Tiles require studies to be loaded in your SIMVA account and proper authentication.
Check that you're logged in and have studies available.

### Q: Can I customize the tile appearance?

A: The tile appearance uses existing TMON.figcraft design tokens. For customization,
you would need to modify the `render_simlet_tiles()` function in `TMonWidget.py`.

### Q: Why does the browser panel only show one tile?

A: This is intentional behavior to avoid overwhelming the UI. The home page tab
shows all studies as a grid, while the browser panel shows a preview.

### Q: What if a study has no name?

A: The tile will display "Study" as a fallback, followed by the study ID. This is
normal and doesn't affect functionality.

## Further Learning

- [How to: Tag simlets and sessions](how-to/tag-simlets-and-sessions.md)
- [How to: Query xAPI statements](how-to/query-xapi-statements.md)
- [T-Mon Architecture explanation](explanation/architecture.md)
- [Agent readiness assessment](AGENTS.md)

