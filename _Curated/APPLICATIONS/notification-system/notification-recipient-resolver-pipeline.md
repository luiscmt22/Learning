# Notification Recipient Resolver Pipeline

## Overview

The Notification Recipient Resolver Pipeline is an **OCP-compliant** (Open/Closed Principle) system for determining who should receive notifications when events occur in the HR system. Instead of hardcoding recipient logic, it uses a **strategy pipeline** pattern that allows adding new recipient types without modifying existing code.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NotificationRecipientService                  │
│                         (Orchestrator)                           │
├─────────────────────────────────────────────────────────────────┤
│  Executes resolvers in order, collects unique recipient IDs     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Manager    │ │  HR Admin   │ │   Future    │
    │  Resolver   │ │  Resolver   │ │  Resolver   │
    │  Order: 10  │ │  Order: 20  │ │  Order: 30  │
    └─────────────┘ └─────────────┘ └─────────────┘
```

## Key Components

### 1. Context Record

```csharp
// Services/Notifications/Resolvers/INotificationRecipientResolver.cs

public record NotificationRecipientContext(
    int EmployeeId,           // Employee whose action triggered notification
    string CompanyDatabase,   // Company context for data resolution
    int? ExcludeUserId = null // User to exclude (usually the action initiator)
);
```

### 2. Resolver Interface

```csharp
public interface INotificationRecipientResolver
{
    /// <summary>
    /// Order in which this resolver executes (lower = earlier)
    /// </summary>
    int Order { get; }

    /// <summary>
    /// Resolves user IDs that should receive notifications
    /// </summary>
    Task<IEnumerable<int>> GetRecipientUserIdsAsync(NotificationRecipientContext context);
}
```

### 3. Orchestrator Service

```csharp
// Services/Notifications/Resolvers/NotificationRecipientService.cs

public class NotificationRecipientService : INotificationRecipientService
{
    private readonly IEnumerable<INotificationRecipientResolver> _resolvers;

    public async Task<IReadOnlyList<int>> GetRecipientsAsync(NotificationRecipientContext context)
    {
        var recipientIds = new HashSet<int>();

        // Execute resolvers in order
        foreach (var resolver in _resolvers.OrderBy(r => r.Order))
        {
            var ids = await resolver.GetRecipientUserIdsAsync(context);

            foreach (var id in ids)
            {
                if (id != context.ExcludeUserId)
                {
                    recipientIds.Add(id);  // HashSet ensures uniqueness
                }
            }
        }

        return recipientIds.ToList();
    }
}
```

## Current Resolvers

### ManagerRecipientResolver (Order: 10)

Resolves the employee's direct manager via the `ReportToUser` or `Reportto` field.

**Resolution path:**
1. Find `UserEmployeeLinkage` for the employee
2. Get the linked user's `ReportToUser` (or fallback to `Reportto`)
3. Return that manager's user ID

```csharp
// Order 10: Manager is resolved first (most direct supervisor)
public int Order => 10;

public async Task<IEnumerable<int>> GetRecipientUserIdsAsync(NotificationRecipientContext context)
{
    // 1. Find user linked to employee
    var linkage = await baseContext.Set<UserEmployeeLinkage>()
        .FirstOrDefaultAsync(l => l.EmployeeId == context.EmployeeId && ...);

    // 2. Get manager from user's ReportToUser field
    var employeeUser = await baseContext.CrmUtilizadors
        .FirstOrDefaultAsync(u => u.Id == linkage.UserId);

    var managerId = employeeUser?.ReportToUser ?? employeeUser?.Reportto;

    // 3. Return manager ID if found and not excluded
    if (managerId.HasValue && managerId.Value != context.ExcludeUserId)
        recipients.Add(managerId.Value);

    return recipients;
}
```

### HRAdminRecipientResolver (Order: 20)

Resolves all HR administrators (users with system role level >= 50).

```csharp
// Order 20: HR Admins are resolved after manager
public int Order => 20;

public async Task<IEnumerable<int>> GetRecipientUserIdsAsync(NotificationRecipientContext context)
{
    // Uses INotificationService.GetAdminUserIdsAsync()
    // Returns users with UserSystemRole.RoleLevel >= 50
    var adminIds = await _notificationService.GetAdminUserIdsAsync();

    return adminIds.Where(id => id != context.ExcludeUserId);
}
```

## DI Registration

```csharp
// Program.cs

// Notification recipient resolvers (SOLID: OCP-compliant pipeline)
builder.Services.AddTransient<INotificationRecipientResolver, ManagerRecipientResolver>();
builder.Services.AddTransient<INotificationRecipientResolver, HRAdminRecipientResolver>();
builder.Services.AddScoped<INotificationRecipientService, NotificationRecipientService>();
```

## Usage Example

### In NotificationSchedulerService (Background Service)

```csharp
// Get recipients using the shared resolver pipeline
var context = new NotificationRecipientContext(employee.Id, company.Database);
var recipients = await recipientService.GetRecipientsAsync(context);

if (!recipients.Any()) continue;

// Send notification to all resolved recipients
foreach (var recipientId in recipients)
{
    await notificationService.SendNotificationToUserAsync(recipientId, notification);
}
```

### In AttendanceNotificationService

```csharp
public async Task NotifyValidatorsAsync(Attendance attendance, string companyDatabase, int? fromUserId)
{
    var context = new NotificationRecipientContext(
        attendance.EmployeeId,
        companyDatabase,
        fromUserId  // Exclude the person who triggered the action
    );

    var recipients = await _recipientService.GetRecipientsAsync(context);

    var notification = new CreateNotificationDto
    {
        Title = "Nova Presenca para Validar",
        Message = $"{attendance.EmployeeName} registou entrada as {attendance.CheckInTime:HH:mm}.",
        Type = "Task",
        Url = "/Myinfo?tab=inbox"
    };

    foreach (var recipientId in recipients)
    {
        await _notificationService.SendNotificationToUserAsync(recipientId, notification, fromUserId);
    }
}
```

## Adding New Resolvers (OCP in Action)

To add a new recipient type, simply create a new resolver class and register it. **No existing code needs to change.**

### Example: TeamLeadRecipientResolver

```csharp
public class TeamLeadRecipientResolver : INotificationRecipientResolver
{
    public int Order => 15;  // Between Manager (10) and HR Admin (20)

    public async Task<IEnumerable<int>> GetRecipientUserIdsAsync(NotificationRecipientContext context)
    {
        // Find team memberships for employee
        // Get TeamLead user IDs from those teams
        // Return unique lead IDs
    }
}

// Register in Program.cs
builder.Services.AddTransient<INotificationRecipientResolver, TeamLeadRecipientResolver>();
```

### Example: DepartmentHeadRecipientResolver

```csharp
public class DepartmentHeadRecipientResolver : INotificationRecipientResolver
{
    public int Order => 25;  // After HR Admin

    public async Task<IEnumerable<int>> GetRecipientUserIdsAsync(NotificationRecipientContext context)
    {
        // Get employee's department
        // Find department head (ResponsavelId)
        // Return head's user ID
    }
}
```

## Resolver Order Convention

| Order | Resolver | Rationale |
|-------|----------|-----------|
| 10 | Manager | Direct supervisor, most relevant |
| 15 | Team Lead | Team-level oversight |
| 20 | HR Admin | Administrative oversight |
| 25 | Department Head | Departmental oversight |
| 30+ | Future resolvers | Additional stakeholders |

## Benefits of This Pattern

| Benefit | Description |
|---------|-------------|
| **OCP Compliance** | Add new resolvers without modifying existing ones |
| **Single Responsibility** | Each resolver handles one recipient type |
| **Testability** | Each resolver can be unit tested in isolation |
| **Reusability** | Same pipeline used by scheduler, attendance, leave, etc. |
| **Flexibility** | Easy to adjust order or disable resolvers |
| **Deduplication** | HashSet ensures each user receives only one notification |

## File Locations

```
Services/Notifications/Resolvers/
├── INotificationRecipientResolver.cs    # Interface + Context record
├── NotificationRecipientService.cs      # Orchestrator (INotificationRecipientService)
├── ManagerRecipientResolver.cs          # Order 10
└── HRAdminRecipientResolver.cs          # Order 20
```

## Related Documentation

- [14-SignalR-Notification-System.md](14-SignalR-Notification-System.md) - Real-time notification delivery
- [08-Agnostic-Schedule-Conflict-Detection.md](08-Agnostic-Schedule-Conflict-Detection.md) - Similar strategy pattern
