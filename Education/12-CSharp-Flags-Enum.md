# C# Flags Enum Guide

## What is the [Flags] Attribute?

The `[Flags]` attribute allows an enum to represent **multiple values simultaneously** using bitwise operations. It's ideal for situations where an entity can have multiple characteristics at the same time.

## Practical Example: Employee Warnings

```csharp
[Flags]
public enum EmployeeWarning
{
    None = 0,                   // 00000000 (binary)
    GeoLockNoLocation = 1,      // 00000001
    JobBoundNoSchedule = 2,     // 00000010
    InvalidLocationCheckIn = 4, // 00000100
    PendingValidation = 8,      // 00001000
    CheckInsDisabled = 16,      // 00010000
    NoScheduleAssigned = 32,    // 00100000
    NoLocationAssigned = 64,    // 01000000
    NoConfiguration = 128       // 10000000
}
```

## Golden Rule: Powers of 2

**Each value MUST be a power of 2:**
- 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024...

This is because each value occupies a **unique bit** in the binary representation:

| Value | Binary     | Bit Position |
|-------|------------|--------------|
| 1     | 0000 0001  | 0            |
| 2     | 0000 0010  | 1            |
| 4     | 0000 0100  | 2            |
| 8     | 0000 1000  | 3            |
| 16    | 0001 0000  | 4            |
| 32    | 0010 0000  | 5            |
| 64    | 0100 0000  | 6            |
| 128   | 1000 0000  | 7            |

## Basic Operations

### 1. Add a Flag

Use the `|=` operator (bitwise OR):

```csharp
var warnings = EmployeeWarning.None;

// Add NoConfiguration
warnings |= EmployeeWarning.NoConfiguration;
// warnings = 128 (10000000)

// Add NoScheduleAssigned
warnings |= EmployeeWarning.NoScheduleAssigned;
// warnings = 160 (10100000) = 128 + 32
```

### 2. Check if a Flag is Set

Use `.HasFlag()`:

```csharp
if (warnings.HasFlag(EmployeeWarning.NoConfiguration))
{
    // This flag is active!
}

// Alternative (more performant but less readable):
if ((warnings & EmployeeWarning.NoConfiguration) != 0)
{
    // This flag is active!
}
```

### 3. Remove a Flag

Use `&= ~` (AND with NOT):

```csharp
// Remove NoConfiguration
warnings &= ~EmployeeWarning.NoConfiguration;
```

### 4. Check if ANY Flag is Set

```csharp
if (warnings != EmployeeWarning.None)
{
    // Has at least one flag active
}
```

### 5. Clear All Flags

```csharp
warnings = EmployeeWarning.None;
```

## Real-World Example: LiveInsightsService

```csharp
var insight = new LiveEmployeeInsight();

// Check employee configuration
var config = employee.Configuration;

if (config == null)
{
    // Add warning: no configuration
    insight.Warnings |= EmployeeWarning.NoConfiguration;
}
else
{
    // Check if JobBound but missing schedule
    if (config.IsJobBound && !hasAnyJobScheduleToday)
    {
        insight.Warnings |= EmployeeWarning.JobBoundNoSchedule;
    }

    // Check if GeoLock required but no location source
    if (config.RequiresGeolocation && !hasAnyLocationSource)
    {
        insight.Warnings |= EmployeeWarning.GeoLockNoLocation;
    }
}

// At the end, the employee can have MULTIPLE warnings:
// warnings = GeoLockNoLocation | NoScheduleAssigned = 1 + 32 = 33
```

## Usage in Blazor/Razor

```razor
@if (emp.HasWarnings)
{
    <div class="d-flex gap-1">
        @if (emp.Warnings.HasFlag(EmployeeWarning.NoConfiguration))
        {
            <MudTooltip Text="No HR configuration found!">
                <MudIcon Icon="@Icons.Material.Filled.Settings" Color="Color.Error" />
            </MudTooltip>
        }
        @if (emp.Warnings.HasFlag(EmployeeWarning.JobBoundNoSchedule))
        {
            <MudTooltip Text="JobBound but no schedule assigned">
                <MudIcon Icon="@Icons.Material.Filled.EventBusy" Color="Color.Warning" />
            </MudTooltip>
        }
        @* ... more flags ... *@
    </div>
}
```

## Pre-defined Combinations

You can define common combinations:

```csharp
[Flags]
public enum EmployeeWarning
{
    None = 0,
    GeoLockNoLocation = 1,
    JobBoundNoSchedule = 2,
    InvalidLocationCheckIn = 4,

    // Combination: all urgent warnings
    AllUrgent = GeoLockNoLocation | JobBoundNoSchedule,  // = 3

    // Combination: all configuration issues
    AllConfigIssues = GeoLockNoLocation | JobBoundNoSchedule | InvalidLocationCheckIn  // = 7
}
```

## Common Mistakes

### ❌ Using Values That Are NOT Powers of 2

```csharp
// WRONG!
[Flags]
public enum BadExample
{
    None = 0,
    First = 1,
    Second = 2,
    Third = 3,  // ❌ 3 = 1 + 2, will conflict!
    Fourth = 4
}
```

### ❌ Forgetting the 0 Value (None)

```csharp
// WRONG!
[Flags]
public enum BadExample
{
    First = 1,
    Second = 2
    // Without None = 0, there's no way to represent "nothing"
}
```

### ❌ Using == Instead of HasFlag

```csharp
var warnings = EmployeeWarning.NoConfiguration | EmployeeWarning.NoScheduleAssigned;

// WRONG - only true if warnings is EXACTLY NoConfiguration
if (warnings == EmployeeWarning.NoConfiguration) { } // false!

// CORRECT - checks if NoConfiguration is included
if (warnings.HasFlag(EmployeeWarning.NoConfiguration)) { } // true!
```

## Quick Reference

| Operation      | Code                    | Description           |
|----------------|-------------------------|-----------------------|
| Add            | `flags \|= Flag`        | Bitwise OR            |
| Remove         | `flags &= ~Flag`        | AND with NOT          |
| Check          | `flags.HasFlag(Flag)`   | Returns bool          |
| Clear All      | `flags = None`          | Full reset            |
| Has Any?       | `flags != None`         | Any flag active       |

## When to Use [Flags]?

✅ **Use when:**
- An entity can have multiple simultaneous characteristics
- You need to filter by combinations of characteristics
- You want to represent permissions, states, or warnings

❌ **Don't use when:**
- Values are mutually exclusive (use regular enum)
- You need more than ~32 different values (use a different approach)
- Logic is too complex (consider using classes instead)

---

*Created for HRModule project - See `EmployeeWarning` in `Services/Attendance/AttendanceModels.cs`*
