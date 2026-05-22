# Education & Learning Materials

> Learning resources for understanding HRModule architecture and patterns.

## Overview

These documents explain the concepts and patterns used in HRModule to help developers understand the system design.

## Document Index

| Document | Level | Description |
|----------|-------|-------------|
| [01-Understanding-Clean-Architecture.md](01-Understanding-Clean-Architecture.md) | Beginner | Clean Architecture principles |
| [02-Role-Based-Authorization.md](02-Role-Based-Authorization.md) | Intermediate | How authorization works |
| [03-Adapter-Pattern-Explained.md](03-Adapter-Pattern-Explained.md) | Advanced | Module decoupling (future) |
| [04-Authorization-Architecture.md](04-Authorization-Architecture.md) | Advanced | Full auth system design |
| [05-Polite-Code-Style.md](05-Polite-Code-Style.md) | Essential | Self-documenting code patterns |
| [06-Blazor-JS-Interop-Static-Events.md](06-Blazor-JS-Interop-Static-Events.md) | Advanced | JS/Blazor event isolation |
| [07-Facial-Recognition-Architecture.md](07-Facial-Recognition-Architecture.md) | Intermediate | Face recognition system |
| [08-Agnostic-Schedule-Conflict-Detection.md](08-Agnostic-Schedule-Conflict-Detection.md) | Advanced | Schedule conflict detection |
| [09-Generic-Schedule-Grid-Architecture.md](09-Generic-Schedule-Grid-Architecture.md) | Advanced | Reusable schedule grid design |
| [10-Web-Fundamentals.md](10-Web-Fundamentals.md) | Beginner | Static files, caching, Kestrel, middleware |

## For Dummies (Simple Explanations)

Non-technical explanations with analogies for complex concepts:

| Document | Description |
|----------|-------------|
| [Static Events - For Dummies](ForDummies/06-Blazor-JS-Interop-Static-Events-ForDummies.md) | Why two kiosk users saw each other's data |
| [Facial Recognition - For Dummies](ForDummies/07-Facial-Recognition-Architecture-ForDummies.md) | How the app knows it's you |

## Quick Start

### For New Developers
1. Read [01-Understanding-Clean-Architecture.md](01-Understanding-Clean-Architecture.md)
2. Review `CLAUDE.md` in project root
3. Study `AuthenticatedComponentBase.cs`

### For Authorization Work
1. Read [02-Role-Based-Authorization.md](02-Role-Based-Authorization.md)
2. Review `Services/Authorization/AuthorizationService.cs`
3. Check [Authorization README](../Authorization/README.md)

### For Module Design
1. Read [03-Adapter-Pattern-Explained.md](03-Adapter-Pattern-Explained.md)
2. Review the plan in [Plans](../Plans/)

## Key Concepts

### Service Layer Pattern
All business logic lives in Services, never in Razor components:
```
UI (Razor) -> Service -> Repository/DbContext
```

### Multi-Tenancy
- Central auth database (BaseControleContext)
- Per-company databases (CompanyContext)
- Cross-database linking via `UserEmployeeLinkage`

### Role-Based Access
- Database-based roles (not boolean flags)
- Hierarchical levels (100 > 80 > 60 > 40)
- Convenience properties in `AuthenticatedComponentBase`
