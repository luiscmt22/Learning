# Adapter Pattern Explained

> **Status**: Future implementation - concepts documented for planning

## The Problem

Currently, modules are coupled to HRModule-specific data models:

```csharp
// Jobs module depends on HRModule's CrmFuncionario
public interface IJobService
{
    Task AssignEmployeeToJobAsync(int jobId, CrmFuncionario employee);
}
```

If we want to reuse the Jobs module in another application that doesn't have `CrmFuncionario`, it won't work.

## The Solution: Adapter Pattern

Each module defines its **own interfaces and DTOs**. The host application provides adapters that translate between its models and the module's DTOs.

```
┌─────────────────────────────────────────────────────────┐
│                    JOBS MODULE                           │
│  (Portable, doesn't know about CrmFuncionario)           │
│                                                          │
│  interface IEmployeeAdapter                              │
│  {                                                       │
│      Task<EmployeeInfo> GetEmployeeAsync(int id);        │
│  }                                                       │
│                                                          │
│  class EmployeeInfo  // Module's own DTO                 │
│  {                                                       │
│      int Id;                                             │
│      string Name;                                        │
│      string Email;                                       │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ implements
                          │
┌─────────────────────────────────────────────────────────┐
│                    HRMODULE ADAPTER                      │
│  (Translates CrmFuncionario -> EmployeeInfo)             │
│                                                          │
│  class HRModuleEmployeeAdapter : IEmployeeAdapter        │
│  {                                                       │
│      async Task<EmployeeInfo> GetEmployeeAsync(int id)   │
│      {                                                   │
│          var func = await _service.GetByIdAsync(id);     │
│          return new EmployeeInfo                         │
│          {                                               │
│              Id = func.Id,                               │
│              Name = func.Nome,                           │
│              Email = func.Email                          │
│          };                                              │
│      }                                                   │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
```

## Before vs After

### Before (Coupled)
```csharp
// Jobs module - DIRECTLY uses CrmFuncionario
public class JobService
{
    private readonly IEmployeeService _employeeService;

    public async Task AssignEmployeeAsync(int jobId, int employeeId)
    {
        CrmFuncionario employee = await _employeeService.GetByIdAsync(employeeId);
        // Uses CrmFuncionario properties directly
        _logger.Log($"Assigned {employee.Nome} to job {jobId}");
    }
}
```

### After (Decoupled)
```csharp
// Jobs module - Uses its own adapter interface
public class JobService
{
    private readonly IEmployeeAdapter _employeeAdapter;  // Module's interface

    public async Task AssignEmployeeAsync(int jobId, int employeeId)
    {
        EmployeeInfo employee = await _employeeAdapter.GetEmployeeAsync(employeeId);
        // Uses module's own DTO
        _logger.Log($"Assigned {employee.Name} to job {jobId}");
    }
}

// In different app (not HRModule)
public class OtherAppEmployeeAdapter : IEmployeeAdapter
{
    private readonly IWorkerRepository _workerRepo;

    public async Task<EmployeeInfo> GetEmployeeAsync(int id)
    {
        var worker = await _workerRepo.GetAsync(id);
        return new EmployeeInfo
        {
            Id = worker.WorkerId,
            Name = worker.FullName,  // Different property name!
            Email = worker.ContactEmail
        };
    }
}
```

## Benefits

1. **Portability**: Modules can be NuGet packages
2. **Independence**: Modules don't know about host models
3. **Testability**: Mock adapters for unit tests
4. **Flexibility**: Different apps provide different adapters

## Module Structure (Future)

```
Modules/
├── Jobs/
│   ├── Jobs.Module.csproj
│   ├── Interfaces/
│   │   └── IEmployeeAdapter.cs
│   ├── DTOs/
│   │   └── EmployeeInfo.cs
│   └── Services/
│       └── JobService.cs
│
└── HRModule.Adapters/
    └── HRModuleEmployeeAdapter.cs
```

## When to Use

Use adapters when:
- Module needs to be reusable across applications
- Module should not depend on specific data models
- Testing requires isolation from real data models

Don't use adapters when:
- Module is tightly integrated with the application
- Performance is critical (adapters add overhead)
- Simple direct dependencies are clearer

## Implementation Plan

This pattern is **deferred** until:
1. Core schema refactoring is complete and stable
2. Module boundaries are clearly identified
3. Adapter interfaces are designed (Interface Segregation)
4. Gradual migration can be done without breaking functionality
