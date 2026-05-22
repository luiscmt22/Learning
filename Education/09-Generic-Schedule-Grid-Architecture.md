# Generic Schedule Grid - Technical Architecture

## Overview

The Generic Schedule Grid is a reusable Blazor component that provides schedule management functionality across different entity types (Employees, Equipment) with a common UI and behavior while using entity-specific data providers.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          UI LAYER                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│  │   Jobs.razor    │  │Colaboradores    │  │Equipamento      │          │
│  │                 │  │Detalhe.razor    │  │Detalhe.razor    │          │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘          │
│           │                    │                    │                    │
│           ▼                    ▼                    ▼                    │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    WRAPPER COMPONENTS                        │        │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │        │
│  │  │JobEmployee   │ │Employee      │ │Equipment     │         │        │
│  │  │ScheduleTab  │ │ScheduleTab   │ │ScheduleTab   │         │        │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘         │        │
│  └─────────┼────────────────┼────────────────┼─────────────────┘        │
│            │                │                │                           │
│            └────────────────┼────────────────┘                           │
│                             ▼                                            │
│            ┌─────────────────────────────────────┐                       │
│            │   GenericScheduleGrid<TSchedule>    │                       │
│            │                                     │                       │
│            │  Parameters:                        │                       │
│            │  - ContextId: int                   │                       │
│            │  - DataProvider: IScheduleGrid...   │                       │
│            │  - CompanyDatabase: string          │                       │
│            │  - UserId: int                      │                       │
│            └──────────────┬──────────────────────┘                       │
│                           │                                              │
└───────────────────────────┼──────────────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────────────┐
│                           │     SERVICE LAYER                            │
├───────────────────────────┼──────────────────────────────────────────────┤
│                           ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │           IScheduleGridDataProvider<TSchedule>               │        │
│  │                                                              │        │
│  │  + GetRowsAsync(contextId, companyDb)                       │        │
│  │  + GetSchedulesAsync(contextId, start, end, companyDb)      │        │
│  │  + CreateScheduleAsync(schedule, companyDb, userId)         │        │
│  │  + UpdateScheduleAsync(schedule, companyDb, userId)         │        │
│  │  + DeleteScheduleAsync(scheduleId, companyDb, userId)       │        │
│  │  + CreateNewSchedule(contextId, rowId, rowLabel, date)      │        │
│  │  + CloneSchedule(source, newRowId, newRowLabel, newDate)    │        │
│  │  + GetContextTitleAsync(contextId, companyDb)               │        │
│  │  + GetContextInfoAsync(contextId, companyDb)                │        │
│  └─────────────────────────────────────────────────────────────┘        │
│                           │                                              │
│        ┌──────────────────┼──────────────────┐                          │
│        │                  │                  │                          │
│        ▼                  ▼                  ▼                          │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                  │
│  │JobEmployee    │ │EmployeeJob    │ │EquipmentJob   │                  │
│  │Schedule       │ │Schedule       │ │Schedule       │                  │
│  │DataProvider   │ │DataProvider   │ │DataProvider   │                  │
│  └───────┬───────┘ └───────┬───────┘ └───────┬───────┘                  │
│          │                 │                 │                          │
└──────────┼─────────────────┼─────────────────┼──────────────────────────┘
           │                 │                 │
┌──────────┼─────────────────┼─────────────────┼──────────────────────────┐
│          │                 │                 │     DATA LAYER           │
├──────────┼─────────────────┼─────────────────┼──────────────────────────┤
│          ▼                 ▼                 ▼                          │
│    ┌───────────┐     ┌───────────┐     ┌───────────────────┐           │
│    │JobSchedule│     │JobSchedule│     │JobEquipmentSchedule│          │
│    │  (table)  │     │  (table)  │     │     (table)        │          │
│    └───────────┘     └───────────┘     └───────────────────┘           │
│                                                                         │
│    Both implement IScheduleEntry                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Interfaces

### IScheduleGridRow

Represents a single row in the schedule grid (Employee, Equipment, or Job):

```csharp
public interface IScheduleGridRow
{
    int RowId { get; }
    string RowLabel { get; }
    string RowIcon { get; }
    string? RowSecondaryLabel { get; }
    string NavigationUrl { get; }
}
```

### IScheduleGridDataProvider<TSchedule>

Defines the contract for data operations:

```csharp
public interface IScheduleGridDataProvider<TSchedule> where TSchedule : IScheduleEntry
{
    // Identity
    string EntityType { get; }
    ScheduleRowType RowType { get; }
    ScheduleViewMode ViewMode { get; }

    // Data Loading
    Task<List<IScheduleGridRow>> GetRowsAsync(int contextId, string companyDatabase);
    Task<List<TSchedule>> GetSchedulesAsync(int contextId, DateTime startDate, DateTime endDate, string companyDatabase);

    // CRUD Operations
    Task<ServiceResult> CreateScheduleAsync(TSchedule schedule, string companyDatabase, int userId);
    Task<ServiceResult> UpdateScheduleAsync(TSchedule schedule, string companyDatabase, int userId);
    Task<ServiceResult> DeleteScheduleAsync(int scheduleId, string companyDatabase, int userId);
    Task<ServiceResult> CreateSchedulesBatchAsync(List<TSchedule> schedules, string companyDatabase, int userId);
    Task<ServiceResult> DeleteSchedulesBatchAsync(List<int> scheduleIds, string companyDatabase, int userId);

    // Factory Methods
    TSchedule CreateNewSchedule(int contextId, int rowId, string rowLabel, DateTime date);
    TSchedule CloneSchedule(TSchedule source, int newRowId, string newRowLabel, DateTime newDate);

    // Context Information
    Task<string> GetContextTitleAsync(int contextId, string companyDatabase);
    Task<ScheduleGridContext> GetContextInfoAsync(int contextId, string companyDatabase);
}
```

### IScheduleEntry

Common interface for all schedule types:

```csharp
public interface IScheduleEntry
{
    int Id { get; }
    int JobId { get; }
    int EntityId { get; }
    DateTime ScheduleDate { get; }
    DateTime? EndDate { get; }
    TimeSpan? CheckInTime { get; }
    TimeSpan? CheckOutTime { get; }

    // Computed Properties
    DateTime ActualStartDateTime { get; }
    DateTime ActualEndDateTime { get; }
    bool IsCrossMidnightShift { get; }
    decimal CalculatedTotalHours { get; }

    bool OverlapsWith(IScheduleEntry other);
}
```

## Data Providers

### JobEmployeeScheduleDataProvider

**Location:** `Services/Core/Scheduling/DataProviders/JobEmployeeScheduleDataProvider.cs`

**Purpose:** Provides Employee schedules for a specific Job (Job → Employees view)

**Context:** JobId | **Rows:** Employees | **Schedule Type:** JobSchedule

```csharp
public class JobEmployeeScheduleDataProvider : IScheduleGridDataProvider<JobSchedule>
{
    public string EntityType => ConflictEntityTypes.Employee;
    public ScheduleRowType RowType => ScheduleRowType.Employee;
    public ScheduleViewMode ViewMode => ScheduleViewMode.JobCentric;
}
```

### JobEquipmentScheduleDataProvider

**Location:** `Services/Core/Scheduling/DataProviders/JobEquipmentScheduleDataProvider.cs`

**Purpose:** Provides Equipment schedules for a specific Job (Job → Equipment view)

**Context:** JobId | **Rows:** Equipment | **Schedule Type:** JobEquipmentSchedule

```csharp
public class JobEquipmentScheduleDataProvider : IScheduleGridDataProvider<JobEquipmentSchedule>
{
    public string EntityType => ConflictEntityTypes.Equipment;
    public ScheduleRowType RowType => ScheduleRowType.Equipment;
    public ScheduleViewMode ViewMode => ScheduleViewMode.JobCentric;
}
```

### EmployeeJobScheduleDataProvider

**Location:** `Services/Core/Scheduling/DataProviders/EmployeeJobScheduleDataProvider.cs`

**Purpose:** Provides Job schedules for a specific Employee (Employee → Jobs view)

**Context:** EmployeeId | **Rows:** Jobs | **Schedule Type:** JobSchedule

```csharp
public class EmployeeJobScheduleDataProvider : IScheduleGridDataProvider<JobSchedule>
{
    public string EntityType => ConflictEntityTypes.Employee;
    public ScheduleRowType RowType => ScheduleRowType.Job;
    public ScheduleViewMode ViewMode => ScheduleViewMode.EntityCentric;
}
```

### EquipmentJobScheduleDataProvider

**Location:** `Services/Core/Scheduling/DataProviders/EquipmentJobScheduleDataProvider.cs`

**Purpose:** Provides Job schedules for a specific Equipment (Equipment → Jobs view)

**Context:** EquipmentId | **Rows:** Jobs | **Schedule Type:** JobEquipmentSchedule

```csharp
public class EquipmentJobScheduleDataProvider : IScheduleGridDataProvider<JobEquipmentSchedule>
{
    public string EntityType => ConflictEntityTypes.Equipment;
    public ScheduleRowType RowType => ScheduleRowType.Job;
    public ScheduleViewMode ViewMode => ScheduleViewMode.EntityCentric;
}
```

## View Modes

```csharp
public enum ScheduleViewMode
{
    /// <summary>
    /// Fixed axis is a Job, rows are entities (Employees or Equipment)
    /// Used in Jobs page to see "who/what is working on this job"
    /// </summary>
    JobCentric,

    /// <summary>
    /// Fixed axis is an Entity (Employee or Equipment), rows are Jobs
    /// Used in detail pages to see "where is this entity scheduled"
    /// </summary>
    EntityCentric
}

public enum ScheduleRowType
{
    Employee,
    Equipment,
    Job
}
```

## Dependency Injection Registration

```csharp
// Program.cs

// Schedule Grid Data Providers (for GenericScheduleGrid component)
builder.Services.AddScoped<JobEmployeeScheduleDataProvider>();
builder.Services.AddScoped<JobEquipmentScheduleDataProvider>();
builder.Services.AddScoped<EmployeeJobScheduleDataProvider>();
builder.Services.AddScoped<EquipmentJobScheduleDataProvider>();
```

## Wrapper Components

### JobEmployeeScheduleTab

**Location:** `Pages/Jobs/Components/JobEmployeeScheduleTab.razor`

```razor
@inject JobEmployeeScheduleDataProvider DataProvider

<GenericScheduleGrid TSchedule="JobSchedule"
                    ContextId="@JobId"
                    CompanyDatabase="@CompanyDatabase"
                    UserId="@UserId"
                    DataProvider="@DataProvider"
                    RowHeaderLabel="Colaborador" />

@code {
    [Parameter] public int JobId { get; set; }
    [Parameter] public string CompanyDatabase { get; set; } = string.Empty;
    [Parameter] public int UserId { get; set; }
}
```

### EmployeeScheduleTab

**Location:** `Pages/HR/EmployeeManagement/Components/EmployeeScheduleTab.razor`

```razor
@inject EmployeeJobScheduleDataProvider DataProvider

<GenericScheduleGrid TSchedule="JobSchedule"
                    ContextId="@EmployeeId"
                    CompanyDatabase="@CompanyDatabase"
                    UserId="@UserId"
                    DataProvider="@DataProvider"
                    RowHeaderLabel="Obra" />

@code {
    [Parameter] public int EmployeeId { get; set; }
    [Parameter] public string CompanyDatabase { get; set; } = string.Empty;
    [Parameter] public int UserId { get; set; }
}
```

### EquipmentScheduleTab

**Location:** `Pages/Equipments/Components/EquipmentScheduleTab.razor`

```razor
@inject EquipmentJobScheduleDataProvider DataProvider

<GenericScheduleGrid TSchedule="JobEquipmentSchedule"
                    ContextId="@EquipmentId"
                    CompanyDatabase="@CompanyDatabase"
                    UserId="@UserId"
                    DataProvider="@DataProvider"
                    RowHeaderLabel="Obra" />

@code {
    [Parameter] public int EquipmentId { get; set; }
    [Parameter] public string CompanyDatabase { get; set; } = string.Empty;
    [Parameter] public int UserId { get; set; }
}
```

## Folder Structure

```
Services/Core/Scheduling/
├── Contracts/
│   ├── IScheduleEntry.cs
│   ├── IScheduleGridRow.cs
│   └── IScheduleGridDataProvider.cs
├── ConflictDetection/
│   ├── IScheduleConflictStrategy.cs
│   ├── IScheduleConflictDetector.cs
│   ├── ScheduleConflictDetector.cs
│   └── Strategies/
│       ├── EmployeeScheduleConflictStrategy.cs
│       └── EquipmentScheduleConflictStrategy.cs
├── DataProviders/
│   ├── JobEmployeeScheduleDataProvider.cs
│   ├── JobEquipmentScheduleDataProvider.cs
│   ├── EmployeeJobScheduleDataProvider.cs
│   └── EquipmentJobScheduleDataProvider.cs
└── DTOs/
    ├── ScheduleViewMode.cs
    ├── ScheduleRowType.cs
    ├── GenericCellState.cs
    ├── ScheduleEditResult.cs
    └── ScheduleGridContext.cs

Pages/Shared/Scheduling/
├── GenericScheduleGrid.razor
└── GenericScheduleEditDialog.razor

Pages/Jobs/Components/
├── JobEmployeeScheduleTab.razor
└── JobEquipmentScheduleTab.razor

Pages/HR/EmployeeManagement/Components/
└── EmployeeScheduleTab.razor

Pages/Equipments/Components/
└── EquipmentScheduleTab.razor
```

## Integration Points

### Jobs.razor

Toggle between Employee and Equipment schedules:

```razor
<MudButtonGroup Color="Color.Primary" Variant="Variant.Outlined" Size="Size.Small">
    <MudButton StartIcon="@Icons.Material.Filled.People"
               Variant="@(!_showEquipmentSchedule ? Variant.Filled : Variant.Outlined)"
               OnClick="@(() => _showEquipmentSchedule = false)">
        Colaboradores
    </MudButton>
    <MudButton StartIcon="@Icons.Material.Filled.Build"
               Variant="@(_showEquipmentSchedule ? Variant.Filled : Variant.Outlined)"
               OnClick="@(() => _showEquipmentSchedule = true)">
        Equipamentos
    </MudButton>
</MudButtonGroup>

@if (!_showEquipmentSchedule)
{
    <JobsScheduleView Jobs="_filteredJobs" ... />
}
else
{
    <JobEquipmentScheduleTab JobId="@_selectedJobId" ... />
}
```

### ColaboradoresDetalhe.razor

Add "Horários" tab:

```razor
<MudTabPanel Text="Horários" Icon="@Icons.Material.Filled.Schedule">
    <EmployeeScheduleTab EmployeeId="@Id"
                         CompanyDatabase="@CompanyDatabase"
                         UserId="@CurrentUserId" />
</MudTabPanel>
```

### EquipamentoDetalhe.razor

Add "Horários" tab:

```razor
<MudTabPanel Text="Horários" Icon="@Icons.Material.Filled.Schedule">
    <EquipmentScheduleTab EquipmentId="@EquipmentId"
                          CompanyDatabase="@(UserSession?.Empresa?.BaseNome ?? string.Empty)"
                          UserId="@CurrentUserId" />
</MudTabPanel>
```

## Adding a New Entity Type

To add scheduling support for a new entity type (e.g., Vehicles):

1. **Create the schedule model** implementing `IScheduleEntry`:
   ```csharp
   public class JobVehicleSchedule : IScheduleEntry { ... }
   ```

2. **Create the data provider**:
   ```csharp
   public class JobVehicleScheduleDataProvider : IScheduleGridDataProvider<JobVehicleSchedule> { ... }
   ```

3. **Create conflict strategy** (if needed):
   ```csharp
   public class VehicleScheduleConflictStrategy : IScheduleConflictStrategy { ... }
   ```

4. **Register in DI**:
   ```csharp
   builder.Services.AddScoped<JobVehicleScheduleDataProvider>();
   builder.Services.AddScoped<IScheduleConflictStrategy, VehicleScheduleConflictStrategy>();
   ```

5. **Create wrapper component**:
   ```razor
   <GenericScheduleGrid TSchedule="JobVehicleSchedule"
                       ContextId="@VehicleId"
                       DataProvider="@DataProvider" ... />
   ```

6. **Integrate** into the appropriate detail page.

## Design Patterns Applied

| Pattern | Application |
|---------|-------------|
| **Strategy** | Different data providers for different entity types |
| **Adapter** | IScheduleEntry makes different schedule types compatible |
| **Facade** | GenericScheduleGrid hides complexity behind simple interface |
| **Factory Method** | CreateNewSchedule and CloneSchedule methods |
| **Template Method** | Data providers follow the same interface pattern |

## SOLID Principles

| Principle | Application |
|-----------|-------------|
| **SRP** | Each data provider handles one entity type |
| **OCP** | New entity types = new providers, no modification to grid |
| **LSP** | Any IScheduleEntry can be used interchangeably |
| **ISP** | IScheduleGridRow has only what's needed for display |
| **DIP** | Grid depends on IScheduleGridDataProvider abstraction |
