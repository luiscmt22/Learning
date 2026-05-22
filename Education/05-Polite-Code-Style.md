# Polite Code Style Guide

## What is "Polite Code"?

Polite code is self-documenting, readable, and expressive. Instead of forcing developers to trace through complex logic, polite code tells you exactly what it does at a glance.

## Key Principles

### 1. Boolean Properties with Clear Names

```csharp
// GOOD - "Polite" boolean properties
protected bool IsSuperAdmin => RoleLevel >= 100;
protected bool IsAdminOrAbove => RoleLevel >= 80;
protected bool IsManagerOrAbove => RoleLevel >= 60;
protected bool HasLinkedEmployee => employeeLinkage != null && employeeLinkage.IsActive;

// BAD - Unclear
protected bool CheckAdmin() => role > 2;
protected bool HasEmployee => emp != null;
```

### 2. Compound Conditions That Read Like English

```csharp
// GOOD - Reads like a sentence: "If admin or above AND employee belongs to current company AND has linked employee ID"
@if (IsAdminOrAbove && colaboradorBelongsToCurrentCompany && LinkedEmployeeId.HasValue)
{
    <EmployeeConfigurationPanel ... />
}

// BAD - Hard to understand at a glance
@if (_role >= 80 && _empCoId == _sessCoId && _linkId != null)
{
    ...
}
```

### 3. Descriptive Variable Names

```csharp
// GOOD
private bool colaboradorBelongsToCurrentCompany = false;
private string? linkedEmployeeCompanyName;
private int? LinkedEmployeeId => employeeLinkage?.EmployeeId;

// BAD
private bool sameCo = false;
private string? empCoName;
private int? empId => link?.EmpId;
```

### 4. Properties Over Direct Access

```csharp
// GOOD - Use properties that express intent
protected int CurrentUserId => UserSession?.User.Id ?? 0;
protected string CompanyDatabase => UserSession?.Empresa?.BaseNome ?? string.Empty;

// Component usage
<SomeComponent UserId="@CurrentUserId" Database="@CompanyDatabase" />

// BAD - Direct access scattered throughout
<SomeComponent UserId="@UserSession?.User.Id ?? 0" Database="@UserSession?.Empresa?.BaseNome ?? string.Empty" />
```

## Real-World Examples from HRModule

### Authorization Checks

```csharp
// In AuthenticatedComponentBase - "Polite" convenience properties
protected bool IsSuperAdmin => RoleLevel >= 100;
protected bool IsAdminOrAbove => RoleLevel >= 80;
protected bool IsManagerOrAbove => RoleLevel >= 60;

// Usage in Razor - crystal clear intent
@if (IsSuperAdmin)
{
    <MudButton Color="Color.Error">Delete System</MudButton>
}

@if (IsAdminOrAbove)
{
    <MudButton>Manage Users</MudButton>
}

@if (IsManagerOrAbove)
{
    <MudButton>View Team Reports</MudButton>
}
```

### Conditional UI Rendering

```csharp
// UtilizadorDetalhes.razor - All conditions are immediately understandable
@if (IsAdminOrAbove && colaboradorBelongsToCurrentCompany && LinkedEmployeeId.HasValue)
{
    <MudTabPanel Text="Configurações HR" Icon="@Icons.Material.Filled.Settings">
        <EmployeeConfigurationPanel EmployeeId="@LinkedEmployeeId.Value"
                                    CompanyDatabase="@CompanyDatabase"
                                    CurrentUserId="@CurrentUserId"
                                    ReadOnly="@(!IsAdminOrAbove)" />
    </MudTabPanel>
}
```

### Service Methods

```csharp
// IEmployeeConfigurationService - Method names express exactly what they do
Task<bool> CanEmployeeCheckInAsync(int employeeId, string companyDatabase);
Task<bool> CanEmployeeValidateAttendanceAsync(int employeeId, string companyDatabase);
Task<bool> RequiresGeolocationAsync(int employeeId, string companyDatabase);
Task<bool> HasHoursBankEnabledAsync(int employeeId, string companyDatabase);
```

## Code Review Checklist

When reviewing code, ask:

1. **Readability**: Can you understand the condition without tracing variable definitions?
2. **Intent**: Does the code express *what* it's checking, not *how*?
3. **Naming**: Are booleans named as questions that return true/false answers?
4. **Compound Conditions**: Do multi-part conditions read like English sentences?
5. **Consistency**: Are similar checks using the same patterns throughout?

## Migration Strategy

When refactoring existing code to "polite" style:

1. **Identify unclear patterns**: Look for magic numbers, abbreviations, direct property chains
2. **Create expressive properties**: Add `IsXxx`, `HasXxx`, `CanXxx` properties
3. **Update usages**: Replace direct checks with property references
4. **Document intent**: Use XML comments for non-obvious properties

```csharp
// Before
@if (userSession?.User?.Role >= 80 && linkedFuncId != null)

// After - with supporting properties
/// <summary>
/// User has Admin role or higher (SuperAdmin, Admin)
/// </summary>
protected bool IsAdminOrAbove => RoleLevel >= 80;

protected int? LinkedEmployeeId => employeeLinkage?.EmployeeId;

@if (IsAdminOrAbove && LinkedEmployeeId.HasValue)
```

## Summary

Polite code:
- Uses clear, descriptive names
- Expresses intent, not implementation
- Reads like English
- Is self-documenting
- Reduces cognitive load for future maintainers

**Remember**: Code is read far more often than it's written. Invest in readability.
