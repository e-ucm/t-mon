# ADR 0006: Initial Plotly Demo Foundation

## Context and Problem Statement

The initial version of T-Mon was a demo notebook using Plotly for visualizing xAPI-SG data.
This established the foundational approach for data visualization in the project.

## Context

### Background
The project began as a Jupyter Notebook demo (T-Mon-SIMVA.ipynb) for visualizing xAPI-SG 
statement data. The initial implementation used Plotly for chart creation and processxAPISGStatement.py 
for statement processing.

### Problem
The initial demo was a notebook-based approach that:
- Required manual execution of notebook cells
- Had limited interactivity
- Could not be easily integrated into a web application
- Needed transformation into a proper web application

### Drivers
1. **Prototype Validation**: Need to validate the core visualization concepts
2. **Web Integration**: Transform notebook into a web application (T-Mon)
3. **Statement Processing**: Establish how xAPI-SG statements would be processed
4. **Chart Types**: Determine which chart types to support initially

### Drivers Against
1. **Notebook Limitations**: Notebooks are not ideal for production web applications
2. **Code Duplication**: Moving from notebook to app risks code duplication
3. **Maintainability**: Notebook code is harder to maintain and test

### Drivers Decision
- **ADR Decision**: Accept the notebook as the foundation and plan the migration to a web app
- **Alternative Considered**: Start from scratch (rejected - lost validation work)
- **Alternative Considered**: Keep as notebook only (rejected - not scalable)

## Status

- **Status**: Accepted (migrated to T-Mon web app)
- **Date**: 2024-07-12
- **Author**: Julio SANTILARIO BERTHILIER
- **Tags**: #foundation #initial-demo #migration

## Consequences

### Positive Consequences
- Established the core visualization concepts (Plotly charts, xAPI-SG processing)
- Provided a prototype that validated the core ideas
- Created the basis for the T-Mon web application
- Established the statement processing pipeline

### Negative Consequences
- Required migration from notebook to web application
- Required refactoring of chart creation code
- Required updating the UI framework (from notebook to Dash/Dash)

### Neutral Consequences
- Some code duplication between notebook and web app (planned refactoring)
- Some API patterns established that continue in T-Mon

## Related Decisions

- [ADR 0007](0007-chartbuilder-module.md) - Chart module built on this foundation
- [ADR 0008](0008-lrs-polling-mechanism.md) - Live updates built on data processing

---

## Previous Decision Records

Previous ADRs in the simva project address database architecture, authentication, API contracts,
and storage solutions. This ADR is the first in the T-Mon project, establishing the foundation.
