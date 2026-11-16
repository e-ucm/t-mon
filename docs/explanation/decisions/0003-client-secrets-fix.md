# ADR 0009: client_secrets.json Error Fix

## Context and Problem Statement

The project needed fixes to the client_secrets.json configuration file to resolve 
authentication and connection issues with the SIMVA API and LRS. This was particularly 
important for the simlet tiles feature and overall T-Mon functionality.

## Context

### Background
The client_secrets.json configuration fixes were implemented in commit f636627 to address 
authentication and connection issues. The fixes were necessary for the simlet tiles feature 
and overall T-Mon functionality to work correctly.

### Problem
The client_secrets.json configuration had issues that prevented:
1. Successful Keycloak/OIDC authentication
2. LRS direct read connectivity
3. SimVA API integration
4. Simlet tiles feature functionality

### Problem Against
1. **Configuration Complexity**: client_secrets.json has multiple fields that must be correctly set
2. **Authentication Failures**: Missing or incorrect fields prevent authentication
3. **LRS Connectivity**: Missing LRS credentials prevent data access

### Drivers
1. **Authentication Success**: Ensure Keycloak/OIDC authentication works
2. **LRS Connectivity**: Enable direct LRS reading
3. **SimVA API Integration**: Enable SimVA API integration
4. **Simlet Tiles Functionality**: Ensure tiles feature works correctly

### Drivers Against
1. **Configuration Complexity**: client_secrets.json has multiple fields that must be correctly set

### Drivers Decision
- **ADR Decision**: Fix client_secrets.json with proper configuration values
- **Alternative Considered**: Document workarounds (rejected - poor user experience)
- **Alternative Considered**: Remove LRS direct read feature (rejected - essential for tiles)

## Status

- **Status**: Accepted
- **Date**: 2026-10-13
- **Author**: Julio SANTILARIO BERTHILIER
- **Tags**: #configuration #authentication #lrs

## Consequences

### Positive Consequences
- Successful Keycloak/OIDC authentication
- LRS direct read connectivity
- SimVA API integration
- Simlet tiles feature functionality
- CI/CD pipeline fixes (workflow files)

### Negative Consequences
- None significant

### Neutral Consequences
- Minor configuration file changes
- CI/CD pipeline updates

## Related Decisions

- [ADR 0001](0006-simlet-tiles-architecture.md) - Tiles need authentication
- [ADR 0005](0006-simlet-tiles-architecture.md) - Live updates need auth
- [ADR 0006](0006-initial-plotly-demo.md) - Foundation setup

