# ADR 0007: ChartBuilder Module

## Context and Problem Statement

The T-Mon application needed a dedicated module for chart creation and management, 
separating chart logic from the main widget code. The initial implementation used inline 
chart creation in TMonWidget.py, which was becoming difficult to maintain.

## Context

### Background
The ChartBuilder module was introduced in commit 8f95b74 to handle chart creation from xAPI-SG 
statements. Before this, chart specifications were handled inline in the TMonWidget.py callbacks,
making the code harder to read and maintain.

### Problem
The inline chart creation approach had several issues:
- Chart specifications were scattered across multiple callbacks
- Chart types and configurations were hard to modify
- The code violated separation of concerns
- Reusing chart specifications across different contexts was difficult

### Drivers
1. **Code Maintainability**: Separate chart logic from widget code
2. **Reusability**: Enable chart specifications to be shared across contexts
3. **Testability**: Enable unit testing of chart creation logic
4. **Consistency**: Ensure consistent chart specifications across the application

### Drivers Against
1. **Added Complexity**: New module adds to the codebase structure
2. **Learning Curve**: Developers need to understand the new module structure

### Drivers Decision
- **ADR Decision**: Create a dedicated ChartBuilder module
- **Alternative Considered**: Keep inline chart creation (rejected - maintainability issues)
- **Alternative Considered**: Use a separate charting library (rejected - inconsistent with project)

## Status

- **Status**: Accepted
- **Date**: 2026-09-30
- **Author**: Julio SANTILARIO BERTHILIER
- **Tags**: #modularization #chart-management

## Consequences

### Positive Consequences
- Chart creation logic is now in a dedicated module (ChartBuilder.py)
- Chart specifications can be reused across different contexts
- Easier to test chart creation logic independently
- Improved code readability and maintainability
- Consistent chart specifications across the application

### Negative Consequences
- New file added to the codebase (ChartBuilder.py)
- Developers need to understand the module structure
- Some initial refactoring effort required

### Neutral Consequences
- Existing chart creation callbacks updated to use the new module
- No changes to chart types or specifications
- Backward compatibility maintained

## Related Decisions

- [ADR 0006](0006-initial-plotly-demo.md) - Foundation for chart creation
- [ADR 0008](0008-lrs-polling-mechanism.md) - Live updates use charts
- [ADR 0003](0006-simlet-tiles-architecture.md) - Data flow integrates charts

