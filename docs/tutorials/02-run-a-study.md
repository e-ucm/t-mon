# Tutorial: Running a Study in T-Mon

## Objective

Run a complete study analysis in T-Mon, from selecting a study to viewing visualizations.

## Prerequisites

- T-Mon installed and running
- SIMVA account with at least one study
- Keycloak/OIDC authentication

## Step-by-Step Guide

### Step 1: Log In

1. Open T-Mon in your web browser
2. Click "Login" or "Sign in"
3. Complete the Keycloak/OIDC authentication flow
4. You should see "Logged in as [your username]" displayed

### Step 2: Select a Study

1. Navigate to the browser section (usually the left panel)
2. You'll see a list of studies (simlets) available in your SIMVA account
3. Click on a study to select it
4. The study name and ID will be displayed in the header

### Step 2 Alternative: Use Home Page

1. Click the "HomePage" tab
2. If studies are available, a grid of tiles will appear
3. Click on a tile to select the study

### Step 3: Run Analysis

1. After selecting a study, you'll see options to run analysis
2. Click the "Run Analysis" button or press the analysis shortcut
3. Wait for the analysis to complete (this may take a few seconds)
4. The system will process the xAPI-SG statements from the study

### Step 4: View Visualizations

1. After analysis completes, navigate to the desired tab
2. Available tabs may include:
   - **Home Page**: Overview of the study
   - **Progress**: Player progress through the study
   - **Videos**: Video viewing data
   - **Completable**: Progress in completables within the study
   - **Alternatives**: Alternative choices in questions
   - **Interactions**: Item interactions within the study
   - **Accessibility**: Accessibility data
   - **Menu**: Menu selections within the study
   - **xAPI Data**: Raw statements from the study
   - **Create**: Custom visualizations

### Step 5: Explore Further

1. Click on different tabs to see various visualizations
2. Use the filter options to narrow down your view
3. Use the "Live updates" checkbox for real-time data
4. Use the "Download" or "Export" features if available

### Step 6: Log Out

1. When finished, click "Logout" to end your session
2. Or simply close the browser window

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Can't select a study | Ensure you're logged in and have studies available |
| Analysis fails | Check the console for error messages |
| Visualizations are empty | Verify the study has data in the LRS |
| Live updates not working | Enable "Live updates" and check the polling interval |
| Can't log in | Verify your Keycloak/OIDC credentials |

### Common Error Messages

| Error Message | Meaning | Solution |
|-------------|---------|----------|
| "No studies available" | No studies in your SIMVA account | Ensure you have studies available |
| "Analysis failed" | Processing error | Check the console for details |
| "No data to display" | No statements for the selected study/test | Verify the study has data |
| "LRS unreachable" | LRS connection issue | Check LRS credentials and network |

## Best Practices

### For Getting Started

1. **Start with a small study**: Begin with a study you're familiar with
2. **Use the Home Page**: Get an overview before diving into the browser
3. **Use Filters**: Narrow down your view using the filter options
4. **Enable Live Updates**: For real-time data during active sessions

### For In-depth Analysis

1. **Start with the Browser**: Navigate through studies → tests → activities
2. **Use Specific Filters**: Filter by specific activities, users, or objects
3. **Create Custom Visualizations**: Use the "Create" tab for tailored views
4. **Use the Raw Data**: Explore the "xAPI Data" tab for detailed statements

### For Troubleshooting

1. **Check the Console**: Look for error messages in the browser console
2. **Verify Credentials**: Ensure Keycloak/OIDC authentication is working
3. **Verify LRS Connection**: Ensure the LRS is reachable and configured
4. **Review the Console**: Error messages often provide clues to the issue

## Frequently Asked Questions

### Q: How long does analysis take?

A: Analysis time depends on the number of statements and the complexity of the study.
Typically, it takes 5-30 seconds for a typical study with 50-100 statements.

### Q: Can I run analysis on multiple studies at once?

A: T-Mon typically processes one study at a time. You can switch between studies using the browser or home page.

### Q: What if analysis fails?

A: Check the console for error messages. Common issues include:
- Missing LRS credentials
- No statements for the selected study
- Network connectivity issues

### Q: Can I save my analysis setup?

A: T-Mon preserves state in the URL, allowing you to save and share your analysis setup via URL.

### Q: Can I export my analysis results?

A: T-Mon allows you to export raw data from the "xAPI Data" tab, and you can share URLs of your analysis setup.

## Frequently Asked Questions (Continued)

### Q: How do I compare two studies?

A: You can:
1. Select one study, run analysis, note the results
2. Select another study, run analysis, compare results
3. Use the "Create" tab to create comparative visualizations

### Q: Can I filter by specific students or activities?

A: Yes, T-Mon provides filter options to narrow down your view by:
- Specific users/players
- Specific activities or activities types
- Specific objects or items
- Date ranges (if available)

### Q: Can I use T-Mon offline?

A: T-Mon requires an internet connection for:
- Authentication via Keycloak/OIDC
- LRS data queries
- Initial study loading

Once data is loaded, some functionality may work offline, but full functionality requires a connection.

## Next Steps

After completing this tutorial:

1. **Explore different visualization tabs**
2. **Create custom visualizations** in the "Create" tab
3. **Use live updates** for real-time monitoring
4. **Share URLs** with colleagues
5. **Experiment with different filter combinations**

## Further Learning

- [How to: Tag simlets and sessions](how-to/tag-simlets-and-sessions.md)
- [How to: Query xAPI statements](how-to/query-xapi-statements.md)
- [T-Mon Architecture explanation](explanation/architecture.md)
- [Agent readiness assessment](AGENTS.md)

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-11-16 | Initial tutorial for running a study |

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-11-16 | Initial tutorial for running a study |

