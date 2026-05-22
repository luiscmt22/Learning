# SignalR Real-Time Communication Part 2: Notification System

> **Level**: Intermediate to Advanced
> **Topic**: Building a comprehensive notification system with SignalR
> **Prerequisites**: [11-SignalR-Real-Time-Communication.md](11-SignalR-Real-Time-Communication.md)

## Overview

In Part 1, we covered the basics of SignalR with the Attendance Hub. Now we'll explore a more complex use case: a comprehensive notification system that supports multiple targeting strategies.

### What We Built

| Feature | Description |
|---------|-------------|
| **Multi-Target Notifications** | Send to Users, Groups, Departments, Jobs, Employee Roles |
| **Cross-Database Resolution** | Resolve targets from per-company databases |
| **Real-Time Delivery** | Instant notification via SignalR |
| **Persistent Storage** | Notifications saved for offline users |

## Architecture Overview

### Why Two Hubs?

We have two separate SignalR hubs for different purposes:

```
AttendanceHub
├── Purpose: Real-time attendance events
├── Events: CheckIn, CheckOut, AttendanceUpdate
└── Groups: CompanyAttendance_{id}, TeamAttendance_{id}_{teamId}

NotificationHub
├── Purpose: Push notifications to users
├── Events: ReceiveNotification, NotificationMarkedRead
└── Groups: User_{id}, All, Admins, Company_{id}, UserGroup_{gid}_{eid}
            Dept_{eid}_{did}, Job_{eid}_{jid}, Role_{eid}_{rid}
```

### The Notification Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NOTIFICATION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  1. Admin sends notification (EnvioGlobal.razor)                             │
│                    │                                                          │
│                    ▼                                                          │
│  2. NotificationService receives request                                      │
│                    │                                                          │
│     ┌──────────────┴──────────────┐                                          │
│     │                             │                                          │
│     ▼                             ▼                                          │
│  3a. Save to Database      3b. Resolve Targets                               │
│     (BaseControleContext)       (NotificationTargetResolver)                 │
│                    │                             │                           │
│                    │             ┌───────────────┴───────────────┐           │
│                    │             │                               │           │
│                    │        Query Company DB            Query Central DB     │
│                    │        (Employees by Dept)        (Users by Linkage)    │
│                    │             │                               │           │
│                    │             └───────────────┬───────────────┘           │
│                    │                             │                           │
│                    │                             ▼                           │
│                    │                     User IDs Resolved                   │
│                    │                             │                           │
│                    └──────────────┬──────────────┘                           │
│                                   │                                          │
│                                   ▼                                          │
│  4. NotificationHubService.SendNotificationToUserAsync()                     │
│                                   │                                          │
│                                   ▼                                          │
│  5. SignalR pushes to connected clients                                      │
│                                   │                                          │
│              ┌────────────────────┼────────────────────┐                     │
│              │                    │                    │                     │
│              ▼                    ▼                    ▼                     │
│         User A (online)     User B (online)     User C (offline)            │
│         Receives instantly  Receives instantly  Sees on next login          │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Why Do We Need a Controller?

The `NotificationController` provides REST API endpoints. But if Blazor components can inject `INotificationService` directly, why do we need it?

### Use Cases for the Controller

| Use Case | Why Controller? |
|----------|-----------------|
| **External Systems** | CI/CD pipelines, external apps send notifications via HTTP |
| **Mobile Apps** | Mobile clients use REST API, not SignalR directly |
| **Background Jobs** | Scheduled tasks run server-side without UI |
| **Testing** | Easy to test with Postman/Swagger |
| **Microservices** | Other services can trigger notifications |

### Controller vs Direct Service Call

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│  BLAZOR UI                                                                    │
│  (EnvioGlobal.razor)                                                         │
│         │                                                                     │
│         │ @inject INotificationService                                       │
│         │                                                                     │
│         └─────────────────────────┐                                          │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │               INotificationService                              │        │
│  │                                                                 │        │
│  │  SendNotificationToDepartmentAsync()                            │        │
│  │  SendNotificationToJobAsync()                                   │        │
│  │  SendNotificationToMultipleTargetsAsync()                       │        │
│  │  ...                                                            │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                   ▲                                          │
│                                   │                                          │
│         ┌─────────────────────────┘                                          │
│         │                                                                     │
│  EXTERNAL (API)                                                               │
│  (Mobile App, CI/CD)                                                         │
│         │                                                                     │
│         │ POST /api/notification/send-to-department                          │
│         │                                                                     │
│         └─────► NotificationController ─────┘                                │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Rule of Thumb:**
- **Inside Blazor**: Inject `INotificationService` directly
- **Outside Blazor**: Use the REST API (Controller)

## SignalR Groups in Notifications

### Group Naming Convention

We use a consistent naming pattern for SignalR groups:

| Target Type | Pattern | Example |
|-------------|---------|---------|
| All users | `All` | `All` |
| Admins | `Admins` | `Admins` |
| Company | `Company_{id}` | `Company_1` |
| User Group | `UserGroup_{groupId}_{empresaId}` | `UserGroup_5_1` |
| Department | `Dept_{empresaId}_{deptId}` | `Dept_1_3` |
| Job | `Job_{empresaId}_{jobId}` | `Job_1_42` |
| Employee Role | `Role_{empresaId}_{roleId}` | `Role_1_7` |
| Individual User | `User_{userId}` | `User_123` |

### Auto-Joining Groups

When a user connects to the NotificationHub, they automatically join relevant groups:

```csharp
// NotificationHub.cs
public override async Task OnConnectedAsync()
{
    var userId = GetUserId();

    // Always join personal group
    await Groups.AddToGroupAsync(Context.ConnectionId, $"User_{userId}");

    // Join "All" group
    await Groups.AddToGroupAsync(Context.ConnectionId, "All");

    // Join admin group if applicable
    if (await _notificationService.IsUserAdminAsync(userId))
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, "Admins");
    }

    // Join company groups
    var companies = await _notificationService.GetUserCompaniesAsync(userId);
    foreach (var company in companies)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, $"Company_{company.Id}");
    }

    // Join user groups
    // ... and so on for departments, jobs, roles
}
```

## Cross-Database Resolution

### The Challenge

Our architecture uses multiple databases:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATABASE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────┐                                         │
│  │    LoginDatabase (Central)      │                                         │
│  │    - BaseControleContext        │                                         │
│  │                                 │                                         │
│  │    Tables:                      │                                         │
│  │    - CRM_UTILIZADOR (Users)     │                                         │
│  │    - CRM_EMPRESA (Companies)    │                                         │
│  │    - NOTIFICATIONS              │  ◄─── Notifications stored here        │
│  │    - USER_EMPLOYEE_LINKAGE      │  ◄─── Maps Users ↔ Employees           │
│  └─────────────────────────────────┘                                         │
│                                                                               │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   CompanyA_DB       │  │   CompanyB_DB       │  │   CompanyC_DB       │  │
│  │   - Employees       │  │   - Employees       │  │   - Employees       │  │
│  │   - Departments     │  │   - Departments     │  │   - Departments     │  │
│  │   - Jobs            │  │   - Jobs            │  │   - Jobs            │  │
│  │   - EmployeeRoles   │  │   - EmployeeRoles   │  │   - EmployeeRoles   │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Problem:** When someone sends a notification to "IT Department", how do we find the actual users?

### The Solution: NotificationTargetResolver

```csharp
public interface INotificationTargetResolver
{
    // Resolve targets to user IDs (the magic!)
    Task<List<int>> GetUserIdsForDepartmentAsync(int departmentId, string companyDatabase);
    Task<List<int>> GetUserIdsForJobAsync(int jobId, string companyDatabase);
    Task<List<int>> GetUserIdsForEmployeeRoleAsync(int roleId, string companyDatabase);

    // Check if user belongs to target
    Task<bool> IsUserInDepartmentAsync(int userId, int departmentId, string companyDatabase);

    // Get names for UI display
    Task<string?> GetDepartmentNameAsync(int departmentId, string companyDatabase);
}
```

### Resolution Flow Example

```
Send to "IT Department" (ID: 3, Company: CompanyA_DB)
                │
                ▼
NotificationTargetResolver.GetUserIdsForDepartmentAsync(3, "CompanyA_DB")
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Query Company Database                                               │
│                                                                               │
│  SELECT Id FROM CrmFuncionarios                                               │
│  WHERE DepartamentoId = 3 AND IsActive = 1                                   │
│                                                                               │
│  Result: Employee IDs [101, 102, 103]                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Query Central Database (UserEmployeeLinkage)                        │
│                                                                               │
│  SELECT UserId FROM UserEmployeeLinkage                                       │
│  WHERE EmployeeId IN (101, 102, 103)                                         │
│    AND CompanyDatabase = 'CompanyA_DB'                                       │
│    AND IsActive = 1                                                          │
│                                                                               │
│  Result: User IDs [5, 8, 12]                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
Send notification to Users 5, 8, 12
```

## Complete Implementation Example

### Sending to a Department

Here's the full flow when an admin sends a notification to the IT Department:

**1. UI (EnvioGlobal.razor)**
```razor
@inject INotificationService NotificationService
@inject INotificationTargetResolver TargetResolver

<!-- Admin selects Department tab, picks "IT Department" -->

@code {
    private async Task SendNotification()
    {
        var request = new NotificationToMultipleTargetsDto
        {
            EmpresaId = _selectedEmpresaId,
            CompanyDatabase = _companyDatabase,
            Title = _notificationTitle,
            Message = _notificationMessage,
            Type = _notificationType,
            DepartmentIds = new List<int> { 3 }  // IT Department
        };

        await NotificationService.SendNotificationToMultipleTargetsAsync(
            request,
            UserSession.User.Id);
    }
}
```

**2. Service (NotificationService.cs)**
```csharp
public async Task<bool> SendNotificationToMultipleTargetsAsync(
    NotificationToMultipleTargetsDto request,
    int? fromUserId)
{
    // Collect all unique user IDs from all target types
    var allUserIds = new HashSet<int>();

    // Resolve department targets
    if (request.DepartmentIds?.Any() == true)
    {
        foreach (var deptId in request.DepartmentIds)
        {
            var userIds = await _targetResolver.GetUserIdsForDepartmentAsync(
                deptId, request.CompanyDatabase);
            foreach (var id in userIds) allUserIds.Add(id);
        }
    }

    // ... resolve other target types ...

    // Create notification for each user
    foreach (var userId in allUserIds)
    {
        // Save to database
        var notification = new Notification { /* ... */ };
        _context.Notifications.Add(notification);

        // Push via SignalR
        await _hubService.SendNotificationToUserAsync(userId, notificationDto);
    }

    await _context.SaveChangesAsync();
    return true;
}
```

**3. SignalR Push (NotificationHubService.cs)**
```csharp
public async Task SendNotificationToUserAsync(int userId, NotificationDto notification)
{
    await _hubContext.Clients
        .Group($"User_{userId}")
        .SendAsync("ReceiveNotification", notification);
}
```

**4. Client Receives (NotificationBadge.razor)**
```razor
@code {
    protected override async Task OnInitializedAsync()
    {
        _hubConnection.On<NotificationDto>("ReceiveNotification", async (notification) =>
        {
            // Update badge count
            _unreadCount++;

            // Show toast for important notifications
            if (notification.Type == "Error" || notification.Type == "Warning")
            {
                Snackbar.Add(notification.Title, Severity.Warning);
            }

            StateHasChanged();
        });
    }
}
```

## Database Schema

### New Tables and Columns

```sql
-- Added to NOTIFICATIONS table
ALTER TABLE NOTIFICATIONS ADD TO_DEPARTMENT_ID INT NULL;
ALTER TABLE NOTIFICATIONS ADD TO_JOB_ID INT NULL;
ALTER TABLE NOTIFICATIONS ADD TO_EMPLOYEE_ROLE_ID INT NULL;
ALTER TABLE NOTIFICATIONS ADD COMPANY_DATABASE NVARCHAR(100) NULL;

-- New junction table for multi-target notifications
CREATE TABLE NOTIFICATION_TARGETS (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    NOTIFICATION_ID INT NOT NULL,
    TARGET_TYPE NVARCHAR(20) NOT NULL,  -- 'Department', 'Job', 'EmployeeRole', 'UserGroup'
    TARGET_ID INT NOT NULL,
    CREATED_AT DATETIME2 DEFAULT GETDATE(),

    INDEX IX_NotificationTargets_NotificationId (NOTIFICATION_ID),
    INDEX IX_NotificationTargets_Lookup (TARGET_TYPE, TARGET_ID)
);
```

### Why Junction Table Instead of JSON Arrays?

| JSON Arrays | Junction Table |
|------------|----------------|
| Can't index | Fully indexable |
| Slow JSON parsing | Fast SQL joins |
| No query optimization | Query optimizer works |
| Violates 1NF | Proper normalization |

## Best Practices

### 1. Always Validate Targets Before Sending
```csharp
var userIds = await _targetResolver.GetUserIdsForDepartmentAsync(deptId, companyDb);
if (!userIds.Any())
{
    _logger.LogWarning("Department {DeptId} has no linked users", deptId);
    return false;
}
```

### 2. Log All Notification Sends
```csharp
_logger.LogInformation(
    "Notification sent to {Count} users for Department {DeptId}",
    userIds.Count, deptId);
```

### 3. Handle Offline Users Gracefully
- Notifications are saved to database first
- Users see them on next login
- SignalR push is best-effort

### 4. Set Reasonable Expiration Dates
```csharp
var notification = new CreateNotificationDto
{
    Title = "Promocao Especial",
    ExpiresAt = DateTime.Now.AddDays(7)  // Auto-cleanup after 7 days
};
```

### 5. Use Batch Operations for Multiple Targets
```csharp
// Good: Single call with multiple targets
await NotificationService.SendNotificationToMultipleTargetsAsync(new NotificationToMultipleTargetsDto
{
    DepartmentIds = new List<int> { 1, 2, 3 },
    JobIds = new List<int> { 10, 20 },
    // ...
});

// Avoid: Multiple individual calls
// foreach (var deptId in deptIds)
//     await NotificationService.SendNotificationToDepartmentAsync(deptId, ...);
```

## Troubleshooting

### Notification Not Received?

1. **Check SignalR Connection**
   - Green dot in NotificationBadge = connected
   - Browser console for SignalR errors

2. **Verify User is in Correct Group**
   ```csharp
   // In NotificationHub, log group joins
   _logger.LogInformation("User {UserId} joined {GroupName}", userId, groupName);
   ```

3. **Check Database**
   - Is notification saved in NOTIFICATIONS table?
   - Is target resolution working? (check logs)

4. **Verify Employee-User Linkage**
   ```sql
   SELECT * FROM USER_EMPLOYEE_LINKAGE
   WHERE EmployeeId = @empId AND CompanyDatabase = @db
   ```

### Connection Drops Frequently?

- Check server memory/CPU
- Review SignalR connection limits
- Consider sticky sessions for load balancers

## Summary

The notification system demonstrates advanced SignalR patterns:

| Pattern | Implementation |
|---------|----------------|
| **Multi-Database** | NotificationTargetResolver handles cross-DB queries |
| **Multiple Hubs** | Separate concerns (Attendance vs Notifications) |
| **Group Management** | Dynamic group joining based on user context |
| **Offline Support** | Database persistence + real-time push |
| **API + SignalR** | REST for external systems, SignalR for real-time |

## Related Documentation

- [11-SignalR-Real-Time-Communication.md](11-SignalR-Real-Time-Communication.md) - Part 1: Basics
- [Services/Notifications/README.md](../../Services/Notifications/README.md) - Service documentation
