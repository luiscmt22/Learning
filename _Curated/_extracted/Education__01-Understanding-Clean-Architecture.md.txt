# Understanding Clean Architecture

## What is Clean Architecture?

Clean Architecture separates your application into layers, where each layer has a specific responsibility. The key principle is that **dependencies point inward** - outer layers depend on inner layers, never the reverse.

## HRModule Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    UI LAYER                              │
│  (Razor Pages, Components)                               │
│  - Displays data                                         │
│  - Handles user input                                    │
│  - Calls services                                        │
│  - NO business logic                                     │
└────────────────────────┬────────────────────────────────┘
                         │ depends on
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  SERVICE LAYER                           │
│  (IEmployeeService, IAuthorizationService, etc.)         │
│  - ALL business logic                                    │
│  - Validation                                            │
│  - Orchestration                                         │
│  - Returns ServiceResult<T>                              │
└────────────────────────┬────────────────────────────────┘
                         │ depends on
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   DATA LAYER                             │
│  (DbContext, Models)                                     │
│  - Database access                                       │
│  - Entity definitions                                    │
│  - EF Core configurations                                │
└─────────────────────────────────────────────────────────┘
```

## The Golden Rules

### 1. UI Layer: Display Only
```razor
<!-- GOOD: UI just displays and calls service -->
@inject IEmployeeService EmployeeService

<MudText>@employee.Nome</MudText>
<MudButton OnClick="SaveEmployee">Guardar</MudButton>

@code {
    private async Task SaveEmployee()
    {
        var result = await EmployeeService.UpdateEmployeeAsync(employee);
        if (!result.Success) Snackbar.Add(result.Message, Severity.Error);
    }
}
```

```razor
<!-- BAD: Business logic in UI -->
@code {
    private async Task SaveEmployee()
    {
        // DON'T DO THIS - validation belongs in service
        if (string.IsNullOrEmpty(employee.Nome))
        {
            Snackbar.Add("Nome obrigatorio", Severity.Error);
            return;
        }

        // DON'T DO THIS - DB access belongs in service
        await _context.Funcionarios.AddAsync(employee);
        await _context.SaveChangesAsync();
    }
}
```

### 2. Service Layer: All Business Logic
```csharp
// GOOD: Business logic in service
public class EmployeeService : IEmployeeService
{
    public async Task<ServiceResult<CrmFuncionario>> UpdateEmployeeAsync(
        EmpresaUserSession session,
        CrmFuncionario employee)
    {
        // Validation
        if (string.IsNullOrEmpty(employee.Nome))
            return ServiceResult<CrmFuncionario>.Failure("Nome obrigatorio");

        // Business rules
        if (employee.DataNascimento > DateTime.Today)
            return ServiceResult<CrmFuncionario>.Failure("Data invalida");

        // Database operation
        await using var context = await _contextFactory.CreateDbContextAsync(session.CompanyDatabase);
        context.Funcionarios.Update(employee);
        await context.SaveChangesAsync();

        // Audit
        await _auditService.LogAsync(session.User.Id, $"Updated employee {employee.Id}");

        return ServiceResult<CrmFuncionario>.Success(employee);
    }
}
```

### 3. ServiceResult Pattern
Always return results with success/failure status:
```csharp
public class ServiceResult<T>
{
    public bool Success { get; set; }
    public string Message { get; set; }
    public T? Data { get; set; }

    public static ServiceResult<T> Success(T data) => new() { Success = true, Data = data };
    public static ServiceResult<T> Failure(string message) => new() { Success = false, Message = message };
}
```

## Why This Matters

### Testability
Services can be unit tested without UI:
```csharp
[Test]
public async Task UpdateEmployee_InvalidName_ReturnsFailure()
{
    var service = new EmployeeService(mockContext, mockAudit);
    var result = await service.UpdateEmployeeAsync(session, new CrmFuncionario { Nome = "" });
    Assert.IsFalse(result.Success);
}
```

### Maintainability
- Change business rules in one place (service)
- UI changes don't affect logic
- Easy to find where logic lives

### Reusability
Same service can be used by:
- Web UI (Blazor)
- API endpoints
- Background jobs
- Other services

## Common Mistakes to Avoid

| Mistake | Problem | Fix |
|---------|---------|-----|
| LINQ in Razor | Logic in UI | Move to service |
| DbContext in component | Direct DB access | Inject service |
| Validation in UI | Duplicated logic | Validate in service |
| Complex `@code` blocks | Too much UI logic | Extract to service |
