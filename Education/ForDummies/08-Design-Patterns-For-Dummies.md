# Design Patterns & SOLID Principles - For Dummies

## The Real-World Problem

We had a scheduling system that only worked for **Employees**. Now we needed to add **Equipment** scheduling with the same conflict detection logic.

**The naive approach:** Copy-paste the entire service and change "Employee" to "Equipment" everywhere.

**The problem with copy-paste:**
- Bug in one place? Fix it in two places.
- Add a feature? Add it in two places.
- Add Vehicles later? Now fix bugs in THREE places.

**The smart approach:** Use design patterns to write it ONCE and reuse it for any entity type.

---

## What We Built

```
"Hey system, does Employee #123 have a conflict on Monday?"
"Hey system, does Equipment #456 have a conflict on Monday?"
"Hey system, does Vehicle #789 have a conflict on Monday?"

Same question, same code, different data sources.
```

---

## The Patterns We Used (In Order)

### Pattern 1: Interface (ISP - Interface Segregation Principle)

**The Problem:** Employee schedules and Equipment schedules are different classes, but they share common properties (start time, end time, etc.).

**The Solution:** Create a "contract" that both must follow.

```csharp
// The contract - "If you want to be a schedule, you must have these things"
public interface IScheduleEntry
{
    DateTime ActualStartDateTime { get; }
    DateTime ActualEndDateTime { get; }
    bool OverlapsWith(IScheduleEntry other);
}
```

**Now both models "sign the contract":**

```csharp
public class JobSchedule : IScheduleEntry          // "I promise to have these properties"
public class JobEquipmentSchedule : IScheduleEntry // "I also promise!"
```

**Why this matters:**

```csharp
// WITHOUT interface - need separate methods:
bool CheckOverlap(JobSchedule a, JobSchedule b) { ... }
bool CheckOverlap(JobEquipmentSchedule a, JobEquipmentSchedule b) { ... }
bool CheckOverlap(JobSchedule a, JobEquipmentSchedule b) { ... }  // Combinations explode!

// WITH interface - one method handles ALL types:
bool CheckOverlap(IScheduleEntry a, IScheduleEntry b)
{
    return a.OverlapsWith(b);  // Works with ANY schedule type!
}
```

**SOLID Principle Applied:** **ISP** - Interface Segregation Principle
> "Don't force classes to implement things they don't need"

We only put what's needed for conflict detection in `IScheduleEntry`. Employee-specific stuff (like `EmployeeName`) stays out.

---

### Pattern 2: Strategy Pattern (OCP - Open/Closed Principle)

**The Problem:** Employee schedules live in `JobSchedules` table. Equipment schedules live in `JobEquipmentSchedules` table. The LOGIC is the same, but the DATA SOURCE is different.

**The Solution:** Each entity type gets its own "strategy" for fetching data.

```csharp
// The strategy contract
public interface IScheduleConflictStrategy
{
    string EntityType { get; }  // "Employee" or "Equipment"
    Task<bool> HasConflictAsync(int entityId, ...);
}

// Employee strategy - queries JobSchedules table
public class EmployeeScheduleConflictStrategy : IScheduleConflictStrategy
{
    public string EntityType => "Employee";

    public async Task<bool> HasConflictAsync(int entityId, ...)
    {
        // Query JobSchedules WHERE EmployeeId = entityId
    }
}

// Equipment strategy - queries JobEquipmentSchedules table
public class EquipmentScheduleConflictStrategy : IScheduleConflictStrategy
{
    public string EntityType => "Equipment";

    public async Task<bool> HasConflictAsync(int entityId, ...)
    {
        // Query JobEquipmentSchedules WHERE EquipmentId = entityId
    }
}
```

**Why this matters:**

```csharp
// WITHOUT strategy - ugly switch statement:
public bool HasConflict(string type, int id)
{
    switch (type)
    {
        case "Employee": return CheckEmployeeConflict(id);
        case "Equipment": return CheckEquipmentConflict(id);
        case "Vehicle": return CheckVehicleConflict(id);  // Must modify!
        default: throw new Exception();
    }
}

// WITH strategy - no modification needed:
public bool HasConflict(string type, int id)
{
    var strategy = strategies.First(s => s.EntityType == type);
    return strategy.HasConflictAsync(id);
    // Adding Vehicle? Just register a new strategy. This code never changes!
}
```

**SOLID Principle Applied:** **OCP** - Open/Closed Principle
> "Open for extension, closed for modification"

To add Vehicles, we CREATE a new `VehicleScheduleConflictStrategy`. We DON'T MODIFY existing code.

---

### Pattern 3: Dependency Injection with IEnumerable<T>

**The Problem:** How does the system know which strategies exist?

**The Solution:** Register all strategies in `Program.cs`, and .NET DI collects them automatically.

```csharp
// Program.cs - Registration
builder.Services.AddScoped<IScheduleConflictStrategy, EmployeeScheduleConflictStrategy>();
builder.Services.AddScoped<IScheduleConflictStrategy, EquipmentScheduleConflictStrategy>();
```

```csharp
// The detector asks for ALL strategies
public class ScheduleConflictDetector
{
    public ScheduleConflictDetector(IEnumerable<IScheduleConflictStrategy> strategies)
    {
        // .NET DI automatically gives us [EmployeeStrategy, EquipmentStrategy]
        // We don't manually create them!
    }
}
```

**The magic:** When you inject `IEnumerable<IScheduleConflictStrategy>`, .NET DI gives you ALL registered implementations as a collection.

**SOLID Principle Applied:** **DIP** - Dependency Inversion Principle
> "Depend on abstractions, not concrete classes"

The detector doesn't know about `EmployeeScheduleConflictStrategy` directly. It only knows `IScheduleConflictStrategy`. The concrete classes are "injected" from outside.

---

### Pattern 4: Facade Pattern (SRP - Single Responsibility)

**The Problem:** The caller shouldn't need to know about strategies. They just want to ask "is there a conflict?"

**The Solution:** Create a simple "facade" that hides the complexity.

```csharp
// The simple interface callers use
public interface IScheduleConflictDetector
{
    Task<bool> HasTimeOverlapAsync(string entityType, int entityId, ...);
}

// The implementation that hides the strategy selection
public class ScheduleConflictDetector : IScheduleConflictDetector
{
    public async Task<bool> HasTimeOverlapAsync(string entityType, int entityId, ...)
    {
        // 1. Find the right strategy
        var strategy = _strategies.First(s => s.EntityType == entityType);

        // 2. Delegate to it
        return await strategy.HasTimeOverlapAsync(entityId, ...);
    }
}
```

**From the caller's perspective:**

```csharp
// Simple! Caller doesn't know about strategies
await _conflictDetector.HasTimeOverlapAsync("Employee", 123, ...);
await _conflictDetector.HasTimeOverlapAsync("Equipment", 456, ...);
```

**SOLID Principle Applied:** **SRP** - Single Responsibility Principle
> "A class should have only one reason to change"

- `ScheduleConflictDetector` - routes to strategies (ONE job)
- `EmployeeScheduleConflictStrategy` - queries employee schedules (ONE job)
- `EquipmentScheduleConflictStrategy` - queries equipment schedules (ONE job)

---

## The Complete Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CALLER                                   │
│   "Does Employee 123 have a conflict?"                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              IScheduleConflictDetector (Facade)                  │
│                                                                  │
│   HasTimeOverlapAsync("Employee", 123, ...)                     │
│                                                                  │
│   1. Look through _strategies                                    │
│   2. Find one where EntityType == "Employee"                    │
│   3. Call that strategy's method                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         IEnumerable<IScheduleConflictStrategy>                   │
│                                                                  │
│   [0] EmployeeStrategy   (EntityType = "Employee")  ◄── MATCH!  │
│   [1] EquipmentStrategy  (EntityType = "Equipment")             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            EmployeeScheduleConflictStrategy                      │
│                                                                  │
│   Queries: context.Set<JobSchedule>()                           │
│            .Where(s => s.EmployeeId == 123)                     │
│                                                                  │
│   JobSchedule implements IScheduleEntry                         │
│   So overlap logic works via the interface                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## SOLID Principles Summary

| Principle | What It Means | How We Applied It |
|-----------|---------------|-------------------|
| **S**ingle Responsibility | One class = One job | Each strategy handles ONE entity type |
| **O**pen/Closed | Add features without modifying existing code | New entity = new strategy file, no changes elsewhere |
| **L**iskov Substitution | Subtypes are interchangeable | Any `IScheduleEntry` can be compared with any other |
| **I**nterface Segregation | Don't force unnecessary implementations | `IScheduleEntry` has ONLY conflict-related properties |
| **D**ependency Inversion | Depend on abstractions | Detector depends on `IScheduleConflictStrategy`, not concrete classes |

---

## Design Patterns Summary

| Pattern | What It Does | Where We Used It |
|---------|--------------|------------------|
| **Strategy** | Different algorithms, same interface | Employee vs Equipment conflict detection |
| **Facade** | Simple interface hiding complexity | `IScheduleConflictDetector` hides strategy selection |
| **Adapter** (via interface) | Makes incompatible types compatible | `IScheduleEntry` makes JobSchedule and JobEquipmentSchedule comparable |

---

## The Payoff: Adding a New Entity Type

**Before (without patterns):**
1. Copy-paste EmployeeConflictService
2. Rename everything to Vehicle
3. Hope you didn't miss anything
4. Now maintain two (or three, or four) copies

**After (with patterns):**
1. Create `JobVehicleSchedule : IScheduleEntry`
2. Create `VehicleScheduleConflictStrategy : IScheduleConflictStrategy`
3. Register in `Program.cs`
4. Done. Existing code unchanged.

```csharp
// This code NEVER changes, no matter how many entity types we add:
var strategy = _strategies.First(s => s.EntityType == entityType);
return await strategy.HasConflictAsync(entityId, ...);
```

---

## Key Takeaways

1. **Interfaces define contracts** - "If you want to play, follow these rules"
2. **Strategy pattern = pluggable algorithms** - Same question, different data sources
3. **IEnumerable<T> in DI = collect all implementations** - Register many, inject as collection
4. **Facade = simple front door** - Hide complexity behind a simple interface
5. **SOLID = maintainable code** - Changes are additions, not modifications

---

## Real Code Locations

| Concept | File |
|---------|------|
| Interface contract | `Services/Core/Scheduling/IScheduleEntry.cs` |
| Strategy interface | `Services/Core/Scheduling/IScheduleConflictStrategy.cs` |
| Facade interface | `Services/Core/Scheduling/IScheduleConflictDetector.cs` |
| Facade implementation | `Services/Core/Scheduling/ScheduleConflictDetector.cs` |
| Employee strategy | `Services/Core/Scheduling/Strategies/EmployeeScheduleConflictStrategy.cs` |
| Equipment strategy | `Services/Core/Scheduling/Strategies/EquipmentScheduleConflictStrategy.cs` |
| DI registration | `Program.cs` (search for "Schedule Conflict Detection") |
