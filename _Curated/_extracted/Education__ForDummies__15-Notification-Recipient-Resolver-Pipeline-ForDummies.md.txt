# Notification Recipient Resolver Pipeline - For Dummies

## The Problem

When something happens in the HR system (employee checks in, document expires, birthday), we need to notify the right people. But who are "the right people"?

- The employee's manager?
- HR administrators?
- Team leads?
- Department heads?

And what if we want to add more recipient types later without breaking everything?

## The Solution: A Pipeline of "Finders"

Think of it like a **relay race** where each runner (resolver) finds some people to notify, then passes the baton to the next runner.

```
Event Happens (e.g., "João checked in")
         │
         ▼
┌─────────────────┐
│ Manager Finder  │ → Finds João's boss (Maria)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HR Admin Finder │ → Finds all HR admins (Carlos, Ana)
└────────┬────────┘
         │
         ▼
Final List: [Maria, Carlos, Ana] ← No duplicates!
```

## Real-World Analogy

Imagine you're planning a surprise party for a coworker. You need to invite:

1. **First**, their direct boss (they should know)
2. **Then**, HR (they handle events)
3. **Maybe later**, their team members

Each person you ask gives you names. You write them all down, but you cross out duplicates. At the end, you have your guest list.

That's exactly what this system does!

## The Three Pieces

### 1. The Context (The "Who" and "Where")

```csharp
// "We need to find recipients for THIS employee in THIS company"
var context = new NotificationRecipientContext(
    EmployeeId: 42,           // João's ID
    CompanyDatabase: "acme",  // Which company
    ExcludeUserId: 10         // Don't notify João himself
);
```

### 2. The Finders (Resolvers)

Each finder knows how to find ONE type of recipient:

```csharp
// Manager Finder - "I find the employee's boss"
class ManagerRecipientResolver
{
    int Order => 10;  // I go first!

    // Returns: [Maria's ID]
}

// HR Admin Finder - "I find all HR people"
class HRAdminRecipientResolver
{
    int Order => 20;  // I go second

    // Returns: [Carlos's ID, Ana's ID]
}
```

### 3. The Coordinator (Service)

The coordinator runs all finders in order and combines the results:

```csharp
// "Run all finders, give me everyone who should be notified"
var recipients = await recipientService.GetRecipientsAsync(context);
// Result: [Maria, Carlos, Ana]
```

## Why Order Matters

The `Order` property determines who runs first:

| Order | Finder | Why This Order? |
|-------|--------|-----------------|
| 10 | Manager | Most important - direct supervisor |
| 20 | HR Admin | Administrative oversight |
| 30+ | (Future) | Additional people as needed |

Lower number = runs earlier. Like priority in a queue.

## Adding New Finders (The Magic Part)

Want to also notify team leads? Just add a new finder:

```csharp
class TeamLeadRecipientResolver
{
    int Order => 15;  // Between Manager (10) and HR (20)

    // Find team leads...
}

// Register it
builder.Services.AddTransient<INotificationRecipientResolver, TeamLeadRecipientResolver>();
```

**That's it!** You didn't touch the Manager finder or the HR finder. They don't even know Team Lead exists. This is the **Open/Closed Principle** - open for extension, closed for modification.

## Before vs After

### Before (Hardcoded - Bad)

```csharp
// Every time you add a recipient type, you modify this method
public List<int> GetRecipients(int employeeId)
{
    var recipients = new List<int>();

    // Find manager
    var managerId = GetManagerId(employeeId);
    if (managerId.HasValue) recipients.Add(managerId.Value);

    // Find HR admins
    var admins = GetHRAdminIds();
    recipients.AddRange(admins);

    // TODO: Add team leads... (requires modifying this method!)
    // TODO: Add department heads... (more modifications!)

    return recipients;
}
```

### After (Pipeline - Good)

```csharp
// Never needs to change - just add new resolvers
public async Task<IReadOnlyList<int>> GetRecipientsAsync(NotificationRecipientContext context)
{
    var recipientIds = new HashSet<int>();

    foreach (var resolver in _resolvers.OrderBy(r => r.Order))
    {
        var ids = await resolver.GetRecipientUserIdsAsync(context);
        foreach (var id in ids)
            recipientIds.Add(id);
    }

    return recipientIds.ToList();
}
```

## Where It's Used

| Feature | What Triggers It |
|---------|------------------|
| NotificationSchedulerService | Daily at 08:00 - birthdays, expiring docs/contracts |
| AttendanceNotificationService | When employee checks in |
| LeaveApprovalService | When leave is requested/approved |

All these features use the **same pipeline** to find recipients. One system, many uses.

## Summary

| Concept | Explanation |
|---------|-------------|
| **Context** | "Find recipients for this employee" |
| **Resolver** | One finder that knows how to find one type of recipient |
| **Order** | Which finder runs first (lower = earlier) |
| **Service** | Runs all finders, combines results, removes duplicates |
| **OCP** | Add new finders without changing existing code |

## File Locations

```
Services/Notifications/Resolvers/
├── INotificationRecipientResolver.cs    # The "contract" - what a finder must do
├── NotificationRecipientService.cs      # The coordinator
├── ManagerRecipientResolver.cs          # Finder #1: finds managers
└── HRAdminRecipientResolver.cs          # Finder #2: finds HR admins
```

---

**Remember**: Each finder does ONE job. The coordinator combines them. Adding new finders is easy and safe!
