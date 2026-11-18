# How to: Use T-Mon App

## Overview

T-Mon is a web application for monitoring and visualizing xAPI-SG (Experience API for 
Surveys) data. This guide explains how to use the main features of the T-Mon application.

## Getting Started

### 1. Installation

1. Ensure you have Python 3.12+ installed
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your SIMVA credentials in `client_secrets.json`:
   ```json
   {
     "simva": {
       "api_url": "https://your-simva-instance.com",
       "external_url": "https://your-simva-instance.com",
       "client_id": "your-client-id",
       "client_secret": "your-client-secret"
     },
     "lrs": {
       "endpoint": "https://your-lrs-instance.com/xAPI/",
       "username": "your-lrs-username",
       "password": "your-lrs-password"
     }
   }
   ```

### 2. Running the Application

```bash
# Using the Python server
python3 -m src/TMonApp

# Or using Docker (if available)
docker run -p 5001:5001 -v $(pwd)/client_secrets.json:/app/client_secrets.json your-tmon-image
```

### 3. Accessing the Application

1. Open your web browser
2. Navigate to `http://localhost:5001`
3. Click "Login" to authenticate via Keycloak/OIDC
4. Once logged in, you'll see the T-Mon dashboard

## Navigating the Dashboard

### Home Page

1. Click the "HomePage" tab to see the overview
2. If studies are available, you'll see a grid of simlet tiles
3. Each tile shows the study name and ID
4. Click a tile to navigate to that study's tests

### Browser Panel

1. After logging in, you'll see the browser panel on the left
2. Navigate through studies → tests → activities
3. Use the folder buttons to move through the directory structure
4. Select "Analysis" to run LRS queries on the selected study/test/activity

### Tabs

T-Mon provides the following visualization tabs:

- **HomePage**: Overview of studies and simlets
- **Progress**: Player progress through serious games
- **Videos**: Videos seen and skipped
- **Completable**: Progress in completables
- **Alternatives**: Alternative choices in questions
- **Interactions**: Item interactions
- **Accessible**: Accessibility data
- **Menu**: Menu selections
- **xAPI Data**: Raw xAPI data table
- **Create**: Create custom visualizations

### Browser Navigation

The browser panel allows you to explore the directory structure:

1. **Studies**: List of available simlets (studies)
2. **Tests**: Tests within a selected study
3. **Activities**: Activities within a selected test
4. **Analysis**: Run LRS queries on the selected activity or entire study

## Using Specific Features

### 1. Loading Studies

1. Log into T-Mon
2. Navigate to the HomePage tab
3. Wait for studies to load from your SIMVA account
4. Tiles will appear showing available studies

### 2. Running Analysis

1. Navigate to a study in the browser panel
2. Select a test within the study
3. Select an activity within the test
4. Click "Run Analysis" or the "Analysis" button
5. Wait for the LRS query to complete
6. Visualizations will appear based on the study data

### 2. Creating Custom Visualizations

1. Navigate to the "Create" tab
2. Select a chart type (bar, line, pie, counting)
3. Select variables for the x and y axes
4. Select an aggregation method
5. Click "Add chart"
6. The chart will appear in the "Your visualisations" section

### 2. Using Live Updates

1. In the home page or browser panel, check the "Live updates" box
2. Select a polling interval (5, 10, 30, 60, or 300 seconds)
3. The application will periodically poll the LRS for new statements
4. New statements will appear in the visualizations without needing to refresh

### 2. Filtering Data

1. Use the "Activities" filter to show/hide specific activities
2. Use the "Users" filter to show/hide specific users
3. Use the "Objects" filter to show/hide specific objects
3. Filter settings are preserved in the URL for sharing

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Can't log in | Check your Keycloak/OIDC credentials and client_secrets.json |
| No studies available | Ensure you have studies in your SIMVA account and `simva.external_url` is set |
| No data shown | Verify the LRS connection and that statements exist for the selected study |
| Visualizations not updating | Check if "Live updates" is enabled and the polling interval |
| Browser panel not loading | Ensure you're authenticated and have navigated to a study |

### Error Messages

| Error Message | Meaning | Solution |
|--------------|---------|----------|
| "No xAPI statements available" | No statements for the selected study | Verify the study has data in the LRS |
| "LRS unreachable" | LRS connection issue | Check LRS credentials and network connectivity |
| "Authentication failed" | Invalid credentials | Check your Keycloak/OIDC settings |
| "Study not found" | Study not in your account | Verify you have access to the study in SIMVA |

## Sharing Results

### Sharing via URL

T-Mon preserves state in the URL, allowing you to share results:

1. After loading data and making selections, check the URL
2. The URL contains parameters for:
   - Study selection
   - User filters
   - Object filters
   - Activity filters
   - Created charts
3. Share the complete URL with colleagues

### Exporting Data

1. Navigate to the "xAPI Data" tab
2. Use the table to explore raw statements
3. Use your browser's export features or the dashboard's download options

## Best Practices

### For End Users

1. **Start with the Home Page**: Get an overview of available studies
2. **Use Filters**: Narrow down your view using the filter options
3. **Enable Live Updates**: For real-time data during active sessions
4. **Share URLs**: Share study views with colleagues using the URL

### For Administrators

1. **Configure client_secrets.json**: Ensure proper Keycloak and LRS settings
2. **Set simva.external_url**: Essential for LRS direct read
3. **Monitor Performance**: Watch the LRS polling interval and adjust as needed
4. **User Training**: Train users on the interface and features

### For Developers

1. **Extend the Application**: Add new visualization types in the "Create" tab
2. **Modify the Interface**: Update the browser panel and home page layout
3. **Add New Features**: Extend the chart types and filtering options
4. **Integrate with Other Systems**: Use the xAPI data export for external analysis

## Frequently Asked Questions

### Q: How do I reset the view to default?
A: Refresh the page or click the "HomePage" tab and select "Reset" if available.

### Q: Why are some visualizations empty?
A: This can happen if:
- No statements exist for the selected study/activity
- The LRS polling hasn't captured the data yet
- Filter settings are too restrictive
- The study doesn't have the expected data types

### Q: How do I export my results?
A: Use the "xAPI Data" tab to explore and copy data, or use your browser's print/save features.

### Q: Can I use T-Mon without a SIMVA account?
A: T-Mon is designed to work with SIMVA accounts. Without SIMVA credentials, you can:
- Use sample data provided in the application
- Create custom visualizations with your own xAPI data (if the API supports it)

## Contact and Support

- **Documentation**: This guide and the AGENTS.md file
- **Issues**: Check the GitHub repository for known issues
- **Support**: Contact the T-Mon development team

## Next Steps

After mastering the basics:

1. Explore different visualization tabs
2. Create custom charts in the "Create" tab
3. Use live updates for real-time monitoring
4. Share URLs with colleagues
5. Experiment with different filter combinations

## Additional Resources

- [T-Mon GitHub Repository](...): Source code and issues
- [xAPI-SG Specification](...): The data standard used
- [Keycloak Documentation](...): Authentication details
- [LRS Documentation](...): Learning Record Store configuration

---

*Last updated: November 2026*
*T-Mon version: latest*
