# ADR 0010: T-Mon Project Structure

## Context and Problem Statement

The T-Mon project needed a clear organizational structure that separates concerns between 
the web application, the SIMVA integration, and the documentation. This ADR documents 
the project structure decisions.

## Context

### Background
The project structure was refined over multiple commits, particularly in commit 4ee91ed 
("fix tmon structure") which reorganized the T-Mon project structure.

### Problem
The project needed a clear structure that:
1. Separates the web application from SIMVA integration
2. Organizes documentation using Diátaxis method
3. Provides clear entry points for different users
4. Maintains backward compatibility

### Drivers
1. **Code Organization**: Separate concerns between web app and SIMVA integration
2. **Documentation**: Organize documentation using Diátaxis method
3. **User Entry Points**: Clear entry points for different user types
4. **Maintainability**: Easy to navigate and modify

### Drivers Against
1. **Restructuring Effort**: Requires moving files and updating imports
2. **Import Updates**: Need to update all import paths

### Drivers Decision
- **ADR Decision**: Adopt the current project structure with docs/, src/, tests/ directories
- **Alternative Considered**: Keep flat structure (rejected - hard to maintain)
- **Alternative Considered**: Mirror simva project structure (rejected - different project)

## Status

- **Status**: Accepted
- **Date**: 2026-11-15
- **Author**: T-Mon Team
- **Tags**: #structure #organization #diataxis

## Consequences

### Positive Consequences
- Clear separation between web app and SIMVA integration
- Diátaxis-method documentation organization
- Clear entry points for different user types
- Easy to navigate and modify

### Negative Consequences
- Requires moving files and updating imports
- Some import paths need updating

### Neutral Consequences
- Existing code functionality maintained
- Documentation structure provides good overview

## Related Decisions

- [ADR 0001](0006-simlet-tiles-architecture.md) - Tiles fit into this structure
- [ADR 0006](0006-initial-plotly-demo.md) - Initial structure foundation
- [ADR 0008](0008-lrs-polling-mechanism.md) - Polling integrates with structure

