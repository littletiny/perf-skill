---
name: DMGR
description: Maintain and update perf-hunter documentation structure after major refactoring. Use when updating existing docs, creating new docs, or migrating legacy docs to follow the new module-based directory structure.
---

# Docs Maintainer

Guide for maintaining perf-hunter documentation following the refactored structure.

## Directory Structure (Post-Refactoring)

```
docs/
├── task/              # Task lifecycle management
│   ├── active/        # In-progress tasks
│   ├── backlog/       # Pending tasks
│   ├── completed/     # Recently completed tasks
│   └── archive/       # Historical archive by quarter/version
├── module/            # Functional modules (what/how/why)
│   ├── core/          # Core Layer
│   ├── analysis/      # Analysis Layer
│   ├── composite/     # Composite Layer
│   ├── cli/           # CLI Layer
│   ├── pipeline/      # Agent Pipeline
│   ├── report/        # Report/Output
│   └── shared/        # Cross-module components
├── system/            # System-level docs
│   ├── what/          # Overview, glossary, setup
│   ├── how/           # Processes, methodologies
│   └── why/           # ADRs, lessons learned
├── discussion/        # Discussion thoughts (date-prefixed)
└── meta/              # Metadata and navigation
    └── migration/     # Migration records
```

## Document Placement Rules

### 1. Task Documents (`task/`)

| Status | Directory | Naming |
|--------|-----------|--------|
| Pending | `task/backlog/` | `<type>-<id>-<brief-title>.md` |
| Active | `task/active/` | `<type>-<id>-<brief-title>.md` |
| Completed | `task/completed/` | `<type>-<id>-<brief-title>.md` |
| Archived | `task/archive/<quarter>/` | Same as above |

Examples: `perf-2024-001-cpu-optimize.md`, `refactor-2024-003-cli-cleanup.md`

### 2. Module Documents (`module/<name>/`)

Each module has three subdirectories:

- **`what/`** - Specifications, interfaces, examples, glossaries
- **`how/`** - Design docs, implementation guides, processes
- **`why/`** - ADRs (Architecture Decision Records), rationale

#### ADR Naming Convention

`adr-XXX-short-title.md` where XXX is a sequential number (e.g., `adr-001-three-tier-architecture.md`)

### 3. System Documents (`system/`)

- **`what/`** - Project overview, setup guides, global glossary
- **`how/`** - Development processes, team workflows, methodologies
- **`why/`** - System-level ADRs, lessons learned

### 4. Discussion (`discussion/`)

Date-prefixed free-form thoughts:

`YYYY-MM-DD-topic-name.md`

Example: `2024-03-07-docs-restructure-rationale.md`

## Migration Guidelines

### From Old Structure to New

| Old Location | New Location |
|--------------|--------------|
| `docs/design/*.md` | `docs/module/<module>/how/` or `why/` |
| `docs/interface/*.md` | `docs/module/<module>/what/` |
| `docs/process/*.md` | `docs/system/how/` |
| `docs/report/*.md` | `docs/module/<module>/what/` or `task/completed/` |
| `docs/plan/*.md` | `docs/task/active/` or `backlog/` |
| `docs/pipeline/*.md` | `docs/module/pipeline/` |
| `docs/LESSONS.md` | `docs/system/why/LESSONS.md` |
| `docs/project-structure.md` | `docs/meta/project-structure.md` |

## Updating References

When updating docs, also check and update references in:

1. **`AGENTS.md`** (project root) - Update doc links if paths changed
2. **`SKILL.md`** files - Update any hardcoded paths
3. **Scripts** - Check for hardcoded doc paths
4. **Comments** - Update TODO/FIXME comments with doc references

## Document Template

### For Design Docs (`module/<name>/how/`)

```markdown
# Title

## Problem

## Solution

## Implementation

## Related
- ADR: [adr-XXX](path)
- Interface: [interface](path)
```

### For ADRs (`module/<name>/why/`)

```markdown
# ADR-XXX: Title

- Status: proposed/accepted/deprecated/superseded
- Date: YYYY-MM-DD
- Decision Maker: @name

## Context

## Decision

## Consequences

### Positive

### Negative

## Alternatives Considered

## References
```

### For Task Docs (`task/<status>/`)

```markdown
# Task: Title

- ID: <type>-<id>
- Status: active/completed/backlog
- Created: YYYY-MM-DD
- Owner: @name

## Objective

## Background

## Plan

## Progress

## Notes
```

## Quick Checklist

When creating or updating docs:

- [ ] File in correct directory (task/module/system/discussion/meta)
- [ ] Correct subdirectory (what/how/why) for module docs
- [ ] Filename uses kebab-case (lowercase, hyphens)
- [ ] ADRs use `adr-XXX-` prefix
- [ ] Discussion files date-prefixed
- [ ] Task files have ID prefix
- [ ] Internal links updated
- [ ] AGENTS.md references checked
- [ ] meta/project-structure.md updated if structure changed
