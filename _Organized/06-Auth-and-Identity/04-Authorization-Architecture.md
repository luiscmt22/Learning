# Authorization Architecture

## Overview

This document explains the unified authorization architecture that combines:
1. **Database-based roles** (UserSystemRole table)
2. **Base class convenience methods** (AuthenticatedComponentBase)
3. **Future: Declarative attributes** ([RequirePermission])

## Architecture Layers

```
┌────────────────────────────────────────────────────────────────┐
│                    PAGE LEVEL (Routing)                         │
│  @attribute [RequireSystemRole("ADMIN")]  // Future             │
│  Prevents unauthorized users from accessing page                │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                  COMPONENT LEVEL (UI)                           │
│  @if (IsAdminOrAbove) { <button>Admin Action</button> }         │
│  Controls what UI elements are visible                          │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                  SERVICE LEVEL (Business)                       │
│  if (!await _auth.CanUserPerformAction(userId))                 │
│      return ServiceResult.Failure("Unauthorized");              │
│  Final authorization check before action                        │
└────────────────────────────────────────────────────────────────┘
```

## Current Implementation

### AuthenticatedComponentBase
```csharp
public class AuthenticatedComponentBase : ComponentBase
{
    [Inject] protected IAuthorizationService AuthorizationService { get; set; }

    // Role properties (cached from UserSystemRole table)
    protected bool IsSuperAdmin { get; private set; }
    protected bool IsAdminOrAbove { get; private set; }
    protected bool IsManagerOrAbove { get; private set; }
    protected int RoleLevel { get; private set; }

    // HR config checks (from EmployeeConfiguration)
    protected async Task<bool> CanClockInOutAsync() { ... }
    protected async Task<bool> CanValidateAttendanceAsync() { ... }

    protected override async Task OnInitializedAsync()
    {
        var role = await AuthorizationService.GetUserRoleAsync(UserId);
        RoleLevel = (int)role;
        IsSuperAdmin = RoleLevel >= 100;
        IsAdminOrAbove = RoleLevel >= 80;
        IsManagerOrAbove = RoleLevel >= 60;
    }
}
```

### Using in Pages
```razor
@inherits AuthenticatedComponentBase
@page "/admin/users"

<!-- UI-level authorization -->
@if (IsSuperAdmin)
{
    <MudButton OnClick="DeleteAll">Delete All Users</MudButton>
}

@if (IsAdminOrAbove)
{
    <MudButton OnClick="CreateUser">Create User</MudButton>
}

@if (IsManagerOrAbove)
{
    <MudButton OnClick="ViewTeamReports">Team Reports</MudButton>
}
```

### AuthorizationService
```csharp
public class AuthorizationService : IAuthorizationService
{
    public async Task<UserRole> GetUserRoleAsync(int userId)
    {
        using var context = _contextFactory.CreateBaseControleContext();

        var roleAssignment = await context.UserSystemRoles
            .Include(usr => usr.Role)
            .Where(usr => usr.UserId == userId && usr.IsActive)
            .OrderByDescending(usr => usr.Role.Level)
            .FirstOrDefaultAsync();

        if (roleAssignment?.Role == null)
            return UserRole.Regular;

        return roleAssignment.Role.Level switch
        {
            >= 100 => UserRole.SuperAdmin,
            >= 80 => UserRole.Admin,
            >= 60 => UserRole.Manager,
            _ => UserRole.Regular
        };
    }

    public async Task<bool> AssignRoleToUserAsync(
        int targetUserId,
        UserRole role,
        int assignedByUserId)
    {
        // Find or create role assignment
        // Validate assigner can assign this role
        // Save to UserSystemRole table
    }
}
```

## Future: Declarative Attributes

### RequireSystemRole
```csharp
[AttributeUsage(AttributeTargets.Class)]
public class RequireSystemRoleAttribute : AuthorizeAttribute
{
    public RequireSystemRoleAttribute(string roleCode)
    {
        Policy = $"SystemRole:{roleCode}";
    }
}

// Usage
@attribute [RequireSystemRole("ADMIN")]
@page "/admin/users"
```

### RequirePermission
```csharp
[AttributeUsage(AttributeTargets.Class | AttributeTargets.Method)]
public class RequirePermissionAttribute : AuthorizeAttribute
{
    public RequirePermissionAttribute(string permission)
    {
        Policy = $"Permission:{permission}";
    }
}

// Usage
@attribute [RequirePermission("USERS.CREATE")]
@page "/admin/users/create"
```

## HR Configuration Checks

For HR-specific features (attendance, timesheets), we check EmployeeConfiguration:

```csharp
// In AuthenticatedComponentBase
protected async Task<bool> CanClockInOutAsync()
{
    if (LinkedEmployeeId == null) return false;

    var config = await _employeeConfigService
        .GetConfigurationAsync(LinkedEmployeeId.Value, CompanyDatabase);

    return config?.FazPicagens ?? false;
}

protected async Task<bool> CanValidateAttendanceAsync()
{
    if (LinkedEmployeeId == null) return false;

    var config = await _employeeConfigService
        .GetConfigurationAsync(LinkedEmployeeId.Value, CompanyDatabase);

    return config?.ValidaPicagens ?? false;
}
```

## Summary Table

| Check Type | Method | Source |
|------------|--------|--------|
| Super Admin | `IsSuperAdmin` | UserSystemRole.Level >= 100 |
| Admin+ | `IsAdminOrAbove` | UserSystemRole.Level >= 80 |
| Manager+ | `IsManagerOrAbove` | UserSystemRole.Level >= 60 |
| Can Clock In | `CanClockInOutAsync()` | EmployeeConfiguration.FazPicagens |
| Can Validate | `CanValidateAttendanceAsync()` | EmployeeConfiguration.ValidaPicagens |
| Specific Permission | `HasPermission()` | Future: SystemRolePermission |
