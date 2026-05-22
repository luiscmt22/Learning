# Agnostic Schedule Conflict Detection - Educational Guide

## Overview

This document explains the **Strategy Pattern** implementation used for schedule conflict detection in HRModule. The system is designed to be **entity-agnostic**, meaning the same conflict detection logic works for Employees, Equipment, and any future entity types.

---

## The Problem

Previously, schedule conflict detection was tightly coupled to Employees:

```csharp
// OLD: Employee-specific, hard to extend
public class JobConflictService : IJobConflictService
{
    public Task<bool> HasTimeOverlapAsync(int employeeId, ...)
    {
        // Queries JobSchedule table directly
        // Adding Equipment would require duplicating this entire service
    }
}
```

**Issues:**
- Adding Equipment scheduling would require copy-pasting the entire service
- Violates **DRY** (Don't Repeat Yourself)
- Violates **OCP** (Open/Closed Principle) - must modify existing code to add new types

---

## The Solution: Strategy Pattern

### SOLID Principles Applied

| Principle | How It's Applied |
|-----------|------------------|
| **S**ingle Responsibility | Each strategy handles ONE entity type |
| **O**pen/Closed | Add new entities by creating strategies, not modifying existing code |
| **L**iskov Substitution | All strategies are interchangeable via the interface |
| **I**nterface Segregation | `IScheduleEntry` has only what's needed for conflict detection |
| **D**ependency Inversion | Detector depends on `IScheduleConflictStrategy` abstraction |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    IScheduleConflictDetector                     │
│                         (Facade)                                 │
│  Routes requests to appropriate strategy based on entityType     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ GetStrategy(entityType)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              IEnumerable<IScheduleConflictStrategy>              │
│                    (Injected via DI)                             │
└─────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────┐          ┌─────────────────────────┐
│ EmployeeSchedule    │          │ EquipmentSchedule       │
│ ConflictStrategy    │          │ ConflictStrategy        │
│                     │          │                         │
│ EntityType="Employee"│         │ EntityType="Equipment"  │
│ Uses: JobSchedule   │          │ Uses: JobEquipmentSchedule│
└─────────────────────┘          └─────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────┐          ┌─────────────────────────┐
│    JobSchedule      │          │  JobEquipmentSchedule   │
│ (implements         │          │ (implements             │
│  IScheduleEntry)    │          │  IScheduleEntry)        │
└─────────────────────┘          └─────────────────────────┘
```

---

## Key Components

### 1. IScheduleEntry Interface (ISP)

Defines the common contract for any schedule entry:

```csharp
public interface IScheduleEntry
{
    int Id { get; }
    int JobId { get; }
    int EntityId { get; }           // EmployeeId OR EquipmentId
    DateTime ScheduleDate { get; }
    DateTime? EndDate { get; }
    TimeSpan? CheckInTime { get; }
    TimeSpan? CheckOutTime { get; }

    // Computed properties for overlap detection
    DateTime ActualStartDateTime { get; }
    DateTime ActualEndDateTime { get; }
    bool IsCrossMidnightShift { get; }
    decimal CalculatedTotalHours { get; }

    bool OverlapsWith(IScheduleEntry other);
}
```

**Why?** Both `JobSchedule` and `JobEquipmentSchedule` implement this interface, allowing the conflict detection logic to work with either type.

**Both models now implement IScheduleEntry:**

```csharp
// JobSchedule.cs
public partial class JobSchedule : IScheduleEntry
{
    public int EmployeeId { get; set; }

    [NotMapped]
    public int EntityId => EmployeeId;  // Maps to EmployeeId

    public bool OverlapsWith(IScheduleEntry other) { ... }
}

// JobEquipmentSchedule.cs
public class JobEquipmentSchedule : IScheduleEntry
{
    public int EquipmentId { get; set; }

    [NotMapped]
    public int EntityId => EquipmentId;  // Maps to EquipmentId

    public bool OverlapsWith(IScheduleEntry other) { ... }
}
```

### 2. IScheduleConflictStrategy Interface (Strategy Pattern)

Each entity type has its own strategy:

```csharp
public interface IScheduleConflictStrategy
{
    string EntityType { get; }  // "Employee", "Equipment", etc.

    Task<List<ScheduleConflict>> GetScheduleConflictsAsync(...);
    Task<DetailedConflictInfo> GetDetailedConflictsAsync(...);
    Task<bool> WouldCreateConflictAsync(...);
    Task<bool> HasTimeOverlapAsync(...);
    Task<decimal> CalculateDailyHoursAsync(...);
}
```

### 3. ScheduleConflictDetector (Facade)

Routes to the correct strategy:

```csharp
public class ScheduleConflictDetector : IScheduleConflictDetector
{
    private readonly IEnumerable<IScheduleConflictStrategy> _strategies;

    public async Task<bool> HasTimeOverlapAsync(
        string entityType,    // <-- This determines which strategy
        int entityId,
        ...)
    {
        var strategy = GetStrategy(entityType);
        return await strategy.HasTimeOverlapAsync(entityId, ...);
    }

    private IScheduleConflictStrategy GetStrategy(string entityType)
    {
        return _strategies.FirstOrDefault(s =>
            s.EntityType.Equals(entityType, StringComparison.OrdinalIgnoreCase))
            ?? throw new ArgumentException($"No strategy for: {entityType}");
    }
}
```

---

## The Magic: DI Registration

```csharp
// Program.cs

// Register ALL strategies as the same interface type
builder.Services.AddScoped<IScheduleConflictStrategy, EmployeeScheduleConflictStrategy>();
builder.Services.AddScoped<IScheduleConflictStrategy, EquipmentScheduleConflictStrategy>();
// Future: builder.Services.AddScoped<IScheduleConflictStrategy, VehicleScheduleConflictStrategy>();

// The detector receives ALL registered strategies via IEnumerable<T>
builder.Services.AddScoped<IScheduleConflictDetector, ScheduleConflictDetector>();
```

**How it works:** When `ScheduleConflictDetector` is constructed, DI injects an `IEnumerable<IScheduleConflictStrategy>` containing ALL registered strategies. The detector then selects the right one based on `EntityType`.

---

## Usage Examples

### Current Usage (Employee)

```csharp
// In JobService or JobScheduleService
var hasConflict = await _conflictDetector.HasTimeOverlapAsync(
    ConflictEntityTypes.Employee,  // "Employee"
    employeeId,
    startDate,
    startTime,
    endDate,
    endTime,
    excludeJobId,
    companyDatabase);
```

### Current Usage (Equipment)

```csharp
// In EquipmentAssignmentService (future)
var hasConflict = await _conflictDetector.HasTimeOverlapAsync(
    ConflictEntityTypes.Equipment,  // "Equipment"
    equipmentId,
    startDate,
    startTime,
    endDate,
    endTime,
    excludeJobId,
    companyDatabase);
```

---

## Adding a New Entity Type (e.g., Vehicle)

### Step 1: Create the Schedule Model

```csharp
// Models/Jobs/JobVehicleSchedule.cs
[Table("JobVehicleSchedules")]
public class JobVehicleSchedule : IScheduleEntry
{
    public int Id { get; set; }
    public int JobId { get; set; }
    public int VehicleId { get; set; }

    // IScheduleEntry.EntityId implementation
    [NotMapped]
    public int EntityId => VehicleId;

    // ... rest of properties (copy from JobEquipmentSchedule)
}
```

### Step 2: Create the Strategy

```csharp
// Services/Core/Scheduling/Strategies/VehicleScheduleConflictStrategy.cs
public class VehicleScheduleConflictStrategy : IScheduleConflictStrategy
{
    public string EntityType => ConflictEntityTypes.Vehicle;  // Add this constant

    // Copy from EquipmentScheduleConflictStrategy
    // Replace JobEquipmentSchedule with JobVehicleSchedule
    // Replace EquipmentId with VehicleId
}
```

### Step 3: Register in DI

```csharp
// Program.cs
builder.Services.AddScoped<IScheduleConflictStrategy, VehicleScheduleConflictStrategy>();
```

### Step 4: Add Entity Type Constant

```csharp
// Services/Core/Scheduling/ConflictEntityTypes.cs
public static class ConflictEntityTypes
{
    public const string Employee = "Employee";
    public const string Equipment = "Equipment";
    public const string Vehicle = "Vehicle";  // Add this
}
```

**That's it!** No modification to existing code. The detector automatically picks up the new strategy.

---

## Why This Design?

### Before (Switch Statement - Violates OCP)

```csharp
public Task<bool> HasConflictAsync(string entityType, int entityId, ...)
{
    return entityType switch
    {
        "Employee" => CheckEmployeeConflict(entityId, ...),
        "Equipment" => CheckEquipmentConflict(entityId, ...),
        "Vehicle" => CheckVehicleConflict(entityId, ...),  // Must modify!
        _ => throw new ArgumentException()
    };
}
```

**Problem:** Every new entity type requires modifying this method.

### After (Strategy Pattern - Follows OCP)

```csharp
public Task<bool> HasConflictAsync(string entityType, int entityId, ...)
{
    var strategy = _strategies.First(s => s.EntityType == entityType);
    return strategy.HasConflictAsync(entityId, ...);
    // Add new types without touching this code!
}
```

**Benefit:** New entity types are added by registration, not modification.

---

## Key Takeaways

1. **Strategy Pattern** allows runtime selection of algorithm based on type
2. **DI with IEnumerable<T>** collects all implementations of an interface
3. **IScheduleEntry interface** provides a common contract for different schedule types
4. **EntityType string** is the discriminator that routes to the correct strategy
5. **OCP compliance** means adding new types never modifies existing code

---

## Files Reference

| File | Purpose |
|------|---------|
| `Services/Core/Scheduling/IScheduleEntry.cs` | Common interface for schedules |
| `Services/Core/Scheduling/IScheduleConflictStrategy.cs` | Strategy interface |
| `Services/Core/Scheduling/IScheduleConflictDetector.cs` | Facade interface + DTOs |
| `Services/Core/Scheduling/ScheduleConflictDetector.cs` | Facade implementation |
| `Services/Core/Scheduling/Strategies/EmployeeScheduleConflictStrategy.cs` | Employee strategy |
| `Services/Core/Scheduling/Strategies/EquipmentScheduleConflictStrategy.cs` | Equipment strategy |
| `Models/Jobs/JobSchedule.cs` | Employee schedule model (implements IScheduleEntry) |
| `Models/Jobs/JobEquipmentSchedule.cs` | Equipment schedule model (implements IScheduleEntry) |
