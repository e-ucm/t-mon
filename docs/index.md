# T-Mon Documentation

## Overview

T-Mon (Traces Monitor in xAPI-SG) is a set of tools to process data in the
**xAPI-SG** data format. T-Mon loads xAPI-SG statements (traces), analyzes them,
and displays a default set of visualizations that provide a quick overview of its
contents.

Documentation is organized using the **Diátaxis** method into four categories:

- **[Tutorials](tutorials/)** - Step-by-step learning paths
- **[How-to guides](how-to/)** - Specific task completion
- **[Reference](reference/)** - Factual API and component information
- **[Explanation](explanation/)** - Background, concepts, and decisions

## Documentation Structure

```text
/docs/
├── index.md                    # This page
├── explanation/                # Background and design decisions
│   ├── architecture.md
│   ├── authentication-and-identity.md
│   ├── lrs-integration.md
│   ├── decisions/              # Key architectural decisions
│   └── simlet-tiles.md         # Simlet tiles design explanation
├── how-to/                     # Task completion guides
│   ├── 01-first-study.md
│   ├── 02-run-a-study.md
│   ├── 03-read-the-data.md
│   ├── 04-simlet-tiles.md         # Using simlet tiles
│   └── ... (other how-to guides)
├── reference/                  # API and component references
│   ├── activity-types.md
│   ├── api.md
│   ├── data-model.md
│   ├── simlet-tiles.md         # Simlet tiles reference
│   └── ... (other reference docs)
└── tutorials/                  # Step-by-step tutorials
    ├── 01-first-study.md
    ├── 02-run-a-study.md
    ├── 03-read-the-data.md
    └── 04-simlet-tiles.md      # Using simlet tiles
```

## Getting Started

1. **Installation**: Follow the [T-Mon installation guide](...)
2. **Authentication**: Log in via Keycloak/OIDC
3. **First study**: Follow the [first study tutorial](tutorials/01-first-study.md)
4. **Explore visualizations**: Use the [how-to guides](how-to/)

## Documentation Categories

### Tutorials
- Step-by-step learning paths
- Get started with T-Mon
- Run your first study analysis
- [01-first-study.md](tutorials/01-first-study.md)
- [02-run-a-study.md](tutorials/02-run-a-study.md)
- [03-read-the-data.md](tutorials/03-read-the-data.md)
- [04-simlet-tiles.md](tutorials/04-simlet-tiles.md) **<-- New**

### How-to Guides
- Specific task completion
- Manage studies and simlets
- Query xAPI statements
- [add-an-activity-type.md](how-to/add-an-activity-type.md)
- [tag-simlets-and-sessions.md](how-to/tag-simlets-and-sessions.md)
- [simlet-tiles.md](how-to/simlet-tiles.md) **<-- New**
- ... (other guides)

### Reference
- Factual information about components and APIs
- Data model reference
- API endpoints
- [data-model.md](reference/data-model.md)
- [api.md](reference/api.md)
- [simlet-tiles.md](reference/simlet-tiles.md) **<-- New**
- ... (other reference docs)

### Explanation
- Background, concepts, and design decisions
- Architecture explanation
- [architecture.md](explanation/architecture.md)
- [authentication-and-identity.md](explanation/authentication-and-identity.md)
- [lrs-integration.md](explanation/lrs-integration.md)
- [decisions/](../simva/docs/explanation/decisions/) **(contains key decisions)**
- [simlet-tiles.md](explanation/simlet-tiles.md) **<-- New**
- ... (other explanation docs)

## Agent Readiness

The T-Mon API has been assessed for AI agent readiness. See [AGENTS.md](AGENTS.md)
for the full assessment, including:

- ✅ Agent-ready features
- ⚠️ Agent-requirements
- ❌ Not yet agent-ready
- Agent readiness threshold
- Known limitations
- Next steps

## Related Projects

- **SIMVA API**: The backend service providing study data
- **SIMVA Frontend**: User interface component
- **SIMVA Infra**: Infrastructure and deployment tools

## Links

- [T-Mon GitHub Repository](...)
- [SIMVA API Documentation](...)
- [Keycloak Documentation](...)
- [xAPI-SG Specification](...)
