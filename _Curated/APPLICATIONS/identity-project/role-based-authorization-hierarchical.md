# Role-Based Authorization Explained

## The Old Way (Boolean Flags)

Previously, roles were stored as boolean flags directly on the User:
```csharp
// OLD - Don't do this anymore
public class CrmUtilizador
{
    public bool IsSuperAdmin { get; set; }
    public bool Isadmin { get; set; }
    public bool Ismanager { get; set; }
}

// Check was simple but inflexible
if (user.Isadmin) { ... }
```

### Problems with Boolean Flags
1. **No hierarchy**: Can't easily check "admin or above"
2. **Hard to extend**: Adding new roles requires schema changes
3. **No audit trail**: Can't track who assigned roles
4. **Multiple roles**: User could be both admin and manager (inconsistent)

## The New Way (Database Roles)

### Role Table
```sql
SystemRole
├── Id: 1, Code: 'SUPER_ADMIN', Level: 100
├── Id: 2, Code: 'ADMIN', Level: 80
├── Id: 3, Code: 'MANAGER', Level: 60
└── Id: 4, Code: 'USER', Level: 40
```

### User-Role Assignment
```sql
UserSystemRole
├── UserId: 123, RoleId: 2 (Admin)
├── UserId: 456, RoleId: 3 (Manager)
└── UserId: 789, RoleId: 4 (User)
```

### Benefits
1. **Hierarchical checks**: `Level >= 80` means "Admin or above"
2. **Extensible**: Add new roles without code changes
3. **Audit trail**: Track when/who assigned roles
4. **Single role**: Each user has one highest role

## How It Works in Code

### 1. Service Layer
```csharp
public class AuthorizationService : IAuthorizationService
{
    public async Task<UserRole> GetUserRoleAsync(int userId)
    {
        var assignment = await _context.UserSystemRoles
            .Include(usr => usr.Role)
            .Where(usr => usr.UserId == userId && usr.IsActive)
            .OrderByDescending(usr => usr.Role.Level)
            .FirstOrDefaultAsync();

        if (assignment?.Role == null) return UserRole.Regular;

        return assignment.Role.Level switch
        {
            >= 100 => UserRole.SuperAdmin,
            >= 80 => UserRole.Admin,
            >= 60 => UserRole.Manager,
            _ => UserRole.Regular
        };
    }
}
```

### 2. Base Component
```csharp
public class AuthenticatedComponentBase : ComponentBase
{
    [Inject] protected IAuthorizationService AuthorizationService { get; set; }

    protected UserRole CurrentUserRole { get; private set; }
    protected int RoleLevel { get; private set; }

    // Convenience properties
    protected bool IsSuperAdmin => RoleLevel >= 100;
    protected bool IsAdminOrAbove => RoleLevel >= 80;
    protected bool IsManagerOrAbove => RoleLevel >= 60;

    protected override async Task OnInitializedAsync()
    {
        CurrentUserRole = await AuthorizationService.GetUserRoleAsync(UserId);
        RoleLevel = (int)CurrentUserRole;
    }
}
```

### 3. Page Usage
```razor
@inherits AuthenticatedComponentBase

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

<!-- All authenticated users can see this -->
<MudButton>My Profile</MudButton>
```

## Role Assignment Rules

```
Super Admin can create:  Super Admin, Admin, Manager, User
Admin can create:        Manager, User
Manager can create:      User
User can create:         Nothing
```

```csharp
// In AuthorizationService
public async Task<bool> CanAssignRoleAsync(int assignerId, UserRole targetRole)
{
    var assignerRole = await GetUserRoleAsync(assignerId);

    return assignerRole switch
    {
        UserRole.SuperAdmin => true, // Can assign any
        UserRole.Admin => targetRole <= UserRole.Manager,
        UserRole.Manager => targetRole == UserRole.Regular,
        _ => false
    };
}
```

## Migration Checklist

When updating code from boolean flags to role checks:

| Old Pattern | New Pattern |
|-------------|-------------|
| `user.IsSuperAdmin` | `IsSuperAdmin` (base class) |
| `user.Isadmin == true` | `IsAdminOrAbove` (base class) |
| `user.Ismanager` | `IsManagerOrAbove` (base class) |
| Direct DB query for admin | Query `UserSystemRoles` with `Level >= 80` |
