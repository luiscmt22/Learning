# Generic Schedule Grid - For Dummies

## The Real-World Problem

We had a beautiful schedule grid that showed **Employees on Jobs**:

```
         | Mon 16 | Tue 17 | Wed 18 | Thu 19 |
---------+--------+--------+--------+--------+
Employee1| 08-17  |        | 08-17  |        |
Employee2|        | 08-17  | 08-17  | 08-17  |
```

But then we needed:
- **Equipment on Jobs** (same view, but equipment instead of employees)
- **Jobs on Employee** (inverted: see all jobs where Employee X is assigned)
- **Jobs on Equipment** (inverted: see all jobs where Equipment Y is assigned)

**The naive approach:** Copy-paste the 2000+ line JobsScheduleView.razor four times.

**The problem:**
- 8000+ lines to maintain
- Bug fix? Fix it in 4 places
- Feature request? Add it in 4 places
- Nightmare!

**The smart approach:** One generic component that works for ALL four views.

---

## What We Built

```
┌─────────────────────────────────────────────────────────────────┐
│              GenericScheduleGrid<TSchedule>                      │
│                                                                  │
│   "I don't care WHAT you're scheduling.                         │
│    Just tell me HOW to get the data."                           │
└─────────────────────────────────────────────────────────────────┘
                              │
           Uses DataProvider to load/save data
                              │
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ JobEmployee  │ JobEquipment │ EmployeeJob  │ EquipmentJob │
│ DataProvider │ DataProvider │ DataProvider │ DataProvider │
│              │              │              │              │
│ Job→Employees│ Job→Equipment│ Emp→Jobs     │ Equip→Jobs   │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

---

## The Four Views

| View | Where It's Used | Fixed Axis | Rows | Columns |
|------|-----------------|------------|------|---------|
| **Job → Employees** | Jobs.razor (Schedule tab) | Job | Employees | Days |
| **Job → Equipment** | Jobs.razor (toggle) | Job | Equipment | Days |
| **Employee → Jobs** | ColaboradoresDetalhe.razor | Employee | Jobs | Days |
| **Equipment → Jobs** | EquipamentoDetalhe.razor | Equipment | Jobs | Days |

---

## How It Works

### Step 1: The Data Provider Contract

Every data provider "signs a contract" promising to implement these methods:

```csharp
public interface IScheduleGridDataProvider<TSchedule>
{
    // "Tell me who goes in the rows"
    Task<List<IScheduleGridRow>> GetRowsAsync(int contextId, string companyDatabase);

    // "Tell me the schedules for the date range"
    Task<List<TSchedule>> GetSchedulesAsync(int contextId, DateTime start, DateTime end, ...);

    // "Create a new schedule when user clicks a cell"
    TSchedule CreateNewSchedule(int contextId, int rowId, string rowLabel, DateTime date);

    // "Save this schedule"
    Task<ServiceResult> CreateScheduleAsync(TSchedule schedule, ...);
    Task<ServiceResult> UpdateScheduleAsync(TSchedule schedule, ...);
    Task<ServiceResult> DeleteScheduleAsync(int scheduleId, ...);
}
```

### Step 2: Each View Has Its Own Provider

**JobEmployeeScheduleDataProvider** (Job → Employees):
```csharp
// GetRowsAsync returns: Employees assigned to this Job
var employees = context.Set<JobEmployee>()
    .Where(je => je.JobId == jobId && je.IsActive)
    .Select(je => je.Employee)
    .ToList();

// GetSchedulesAsync queries: JobSchedule table
var schedules = context.Set<JobSchedule>()
    .Where(s => s.JobId == jobId && s.ScheduleDate >= start && s.ScheduleDate <= end)
    .ToList();
```

**EmployeeJobScheduleDataProvider** (Employee → Jobs):
```csharp
// GetRowsAsync returns: Jobs where this Employee is assigned
var jobs = context.Set<JobEmployee>()
    .Where(je => je.EmployeeId == employeeId && je.IsActive)
    .Select(je => je.Job)
    .ToList();

// GetSchedulesAsync queries: Same JobSchedule table, different filter
var schedules = context.Set<JobSchedule>()
    .Where(s => s.EmployeeId == employeeId && s.ScheduleDate >= start && ...)
    .ToList();
```

### Step 3: The Generic Grid Uses the Provider

```razor
<GenericScheduleGrid TSchedule="JobSchedule"
                    ContextId="@JobId"
                    DataProvider="@_dataProvider"
                    CompanyDatabase="@CompanyDb"
                    UserId="@UserId" />
```

The grid doesn't know or care about:
- What type of entity the rows represent
- Where the schedules are stored
- The specific database queries

It just asks the provider: "Give me rows" and "Give me schedules."

---

## The Row Abstraction

Every row (Employee, Equipment, or Job) looks the same to the grid:

```csharp
public interface IScheduleGridRow
{
    int RowId { get; }              // Employee 123, Equipment 456, Job 789
    string RowLabel { get; }         // "John Doe", "Excavator-001", "Project Alpha"
    string RowIcon { get; }          // "person", "build", "work"
    string? RowSecondaryLabel { get; } // Optional subtitle
    string NavigationUrl { get; }    // "/employees/123", "/equipments/456"
}
```

The grid renders:
```
[icon] RowLabel        | Mon | Tue | Wed | Thu |
       RowSecondaryLabel
```

---

## Wrapper Components (The Easy Part)

We create thin "wrapper" components that configure the generic grid:

**JobEmployeeScheduleTab.razor:**
```razor
@inject JobEmployeeScheduleDataProvider DataProvider

<GenericScheduleGrid TSchedule="JobSchedule"
                    ContextId="@JobId"
                    DataProvider="@DataProvider"
                    RowHeaderLabel="Colaborador" />

@code {
    [Parameter] public int JobId { get; set; }
    // ... other parameters
}
```

**EmployeeScheduleTab.razor:**
```razor
@inject EmployeeJobScheduleDataProvider DataProvider

<GenericScheduleGrid TSchedule="JobSchedule"
                    ContextId="@EmployeeId"
                    DataProvider="@DataProvider"
                    RowHeaderLabel="Obra" />

@code {
    [Parameter] public int EmployeeId { get; set; }
    // ... other parameters
}
```

**The magic:** Same grid component, different providers, different views!

---

## Where To Find Each Piece

### Data Providers
```
Services/Core/Scheduling/DataProviders/
├── JobEmployeeScheduleDataProvider.cs    (Job → Employees)
├── JobEquipmentScheduleDataProvider.cs   (Job → Equipment)
├── EmployeeJobScheduleDataProvider.cs    (Employee → Jobs)
└── EquipmentJobScheduleDataProvider.cs   (Equipment → Jobs)
```

### Contracts
```
Services/Core/Scheduling/Contracts/
├── IScheduleGridDataProvider.cs          (Data provider interface)
├── IScheduleGridRow.cs                   (Row abstraction)
└── IScheduleEntry.cs                     (Schedule entry interface)
```

### UI Components
```
Pages/Shared/Scheduling/
├── GenericScheduleGrid.razor             (The main component)
└── GenericScheduleEditDialog.razor       (Edit dialog)

Pages/Jobs/Components/
├── JobEmployeeScheduleTab.razor          (Wrapper for Jobs page)
└── JobEquipmentScheduleTab.razor         (Wrapper for Jobs page)

Pages/HR/EmployeeManagement/Components/
└── EmployeeScheduleTab.razor             (Wrapper for Employee detail)

Pages/Equipments/Components/
└── EquipmentScheduleTab.razor            (Wrapper for Equipment detail)
```

### Integration Points
```
Pages/Jobs/Jobs.razor                     (Toggle between Employee/Equipment)
Pages/HR/EmployeeManagement/ColaboradoresDetalhe.razor  (Horários tab)
Pages/Equipments/EquipamentoDetalhe.razor              (Horários tab)
```

---

## Adding a New View (Example: Teams → Employees)

Want to show which employees are in a team, with their schedules?

**Step 1:** Create the provider
```csharp
// Services/Core/Scheduling/DataProviders/TeamEmployeeScheduleDataProvider.cs
public class TeamEmployeeScheduleDataProvider : IScheduleGridDataProvider<TeamSchedule>
{
    public string EntityType => "Team";

    public async Task<List<IScheduleGridRow>> GetRowsAsync(int teamId, ...)
    {
        // Query TeamMembers to get employees in this team
    }

    public async Task<List<TeamSchedule>> GetSchedulesAsync(int teamId, ...)
    {
        // Query team schedules
    }

    // ... other methods
}
```

**Step 2:** Register in Program.cs
```csharp
builder.Services.AddScoped<TeamEmployeeScheduleDataProvider>();
```

**Step 3:** Create wrapper component
```razor
@inject TeamEmployeeScheduleDataProvider DataProvider

<GenericScheduleGrid TSchedule="TeamSchedule"
                    ContextId="@TeamId"
                    DataProvider="@DataProvider"
                    RowHeaderLabel="Membro" />
```

**Step 4:** Add to your page

Done! No changes to GenericScheduleGrid.razor needed.

---

## Key Concepts

| Concept | What It Means | Example |
|---------|---------------|---------|
| **ContextId** | The "fixed axis" entity | JobId, EmployeeId, EquipmentId |
| **RowId** | What appears in each row | EmployeeId, JobId |
| **DataProvider** | Knows how to fetch/save data | JobEmployeeScheduleDataProvider |
| **TSchedule** | The schedule entity type | JobSchedule, JobEquipmentSchedule |

---

## Why This Design Rocks

### Before (Without Abstraction)
- 4 separate schedule components
- 8000+ lines of duplicated code
- Bug fix = edit 4 files
- New feature = implement 4 times

### After (With Generic Grid)
- 1 schedule component + 4 thin providers
- ~1500 lines total
- Bug fix = edit 1 file
- New feature = implement once

### Adding New Entity Types
Before: Copy-paste entire component, rename everything, pray you didn't miss anything

After:
1. Create new DataProvider (~200 lines)
2. Create wrapper component (~30 lines)
3. Register in DI
4. Use it!

---

## The Schedule Entry Interface

Both `JobSchedule` and `JobEquipmentSchedule` implement:

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

    // Computed properties
    bool IsCrossMidnightShift { get; }
    decimal CalculatedTotalHours { get; }
    bool OverlapsWith(IScheduleEntry other);
}
```

This means the generic grid can:
- Display any schedule type in cells
- Calculate hours
- Detect overlaps
- Handle cross-midnight shifts

All without knowing if it's an employee or equipment schedule!

---

## Quick Reference

**Want to show Employees on a Job?**
→ Use `JobEmployeeScheduleTab` with `JobId`

**Want to show Equipment on a Job?**
→ Use `JobEquipmentScheduleTab` with `JobId`

**Want to show Jobs for an Employee?**
→ Use `EmployeeScheduleTab` with `EmployeeId`

**Want to show Jobs for Equipment?**
→ Use `EquipmentScheduleTab` with `EquipmentId`

---

## Remember

1. **The grid is generic** - It works with any schedule type
2. **Providers do the work** - They know WHERE the data lives
3. **Wrappers are thin** - Just configuration, no logic
4. **One codebase** - Fix once, works everywhere
5. **Extensible** - New views = new provider, not new grid
