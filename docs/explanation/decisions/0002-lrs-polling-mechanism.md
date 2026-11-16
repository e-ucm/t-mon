# ADR 0008: LRS Polling Mechanism

## Context and Problem Statement

The T-Mon application needed a mechanism to poll the Learning Record Store (LRS) for new 
statements in near real-time. This was essential for the live updates feature and the 
simlet tiles feature to show recent activity.

## Context

### Background
The LRS polling mechanism was implemented in commit 8af7126 to address the need for near 
real-time statement updates. Before this, the application only had static data from the 
initial load.

### Problem
The application needed a mechanism to:
1. Poll the LRS for new statements in near real-time
2. Handle polling errors gracefully
3. Integrate with the existing tile and visualization features
4. Provide user control over polling frequency

### Problem Against
1. **Resource Usage**: Polling consumes API resources
2. **Stale Data Risk**: Polling could show data that's already been viewed
3. **Complexity**: Added polling mechanism increases feature complexity

### Drivers
1. **Real-time Data**: Users need to see recently arrived statements
2. **Existing Infrastructure**: LRS already supports polling via the `more` cursor
3. **User Expectation**: Users expect live updates in modern dashboards
4. **Integration**: Must integrate with existing tile and visualization features

### Drivers Against
1. **Resource Usage**: Polling consumes API resources and could impact performance
2. **Complexity**: Adding polling mechanism increases feature complexity

### Drivers Decision
- **ADR Decision**: Implement LRS polling with user-controlled frequency and error handling
- **Alternative Considered**: WebSocket-based updates (rejected - not supported by current infrastructure)
- **Alternative Considered**: Manual refresh only (rejected - poor user experience)

## Status

- **Status**: Accepted
- **Date**: 2026-09-28
- **Author**: Julio SANTILARIO BERTHILIER
- **Tags**: #live-updates #polling #real-time

## Consequences

### Positive Consequences
- Tiles and visualizations can show recently arrived statements
- Reuses existing LRS polling infrastructure (the `more` cursor mechanism)
- Users can enable/disable live updates via a checkbox
- Polling interval configurable (5, 10, 30, 60, 300 seconds)
- Error handling gracefully handles LRS unavailability

### Negative Consequences
- Slight increase in API polling frequency when live updates enabled
- Potential stale data if polling interval is too high
- Additional UI element (live update checkbox) in home page and browser panel

### Neutral Consequences
- No impact on static data (still shows initial load data)
- Existing error handling for LRS errors applies equally
- Live updates can be disabled if performance becomes concern

## Related Decisions

- [ADR 0003](0006-simlet-tiles-architecture.md) - Data flow integrates with polling
- [ADR 0005](0005-simlet-tiles-live-updates.md) - Tiles live updates feature
- [ADR 0007](0007-chartbuilder-module.md) - Charts use polled data

