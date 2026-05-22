# SignalR Real-Time Communication in Blazor Server

> **Level**: Intermediate to Advanced
> **Topic**: Real-time updates using SignalR Hubs and Groups

## What is SignalR?

SignalR is a library for adding **real-time** web functionality to applications. It enables server-side code to push content to connected clients instantly, rather than requiring clients to poll for updates.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Hub** | Server-side class that handles connections and messages |
| **Connection** | A single client connected to the hub |
| **Group** | A named collection of connections that receive messages together |
| **Client** | The browser/component receiving messages |

### How SignalR Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            SERVER                                       │
│                                                                         │
│   ┌───────────────────────────────────────────────────────────────┐     │
│   │                     SignalR Hub                               │     │
│   │                                                               │     │
│   │  Groups:                                                      │     │
│   │  ┌─────────────────────┐  ┌─────────────────────┐             │     │
│   │  │ CompanyAttendance_1 │  │ TeamAttendance_5_1  │             │     │
│   │  │  - Connection A     │  │  - Connection C     │             │     │
│   │  │  - Connection B     │  │                     │             │     │
│   │  └─────────────────────┘  └─────────────────────┘             │     │
│   └───────────────────────────────────────────────────────────────┘     │
│                    │                    │                               │
└────────────────────┼────────────────────┼───────────────────────────────┘
                     │                    │
        ┌────────────┴────────┐           │
        │                     │           │
        ▼                     ▼           ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Client A   │    │   Client B   │    │   Client C   │
│  (Admin UI)  │    │  (Admin UI)  │    │ (Manager UI) │
└──────────────┘    └──────────────┘    └──────────────┘
```

## Step-by-Step Implementation

### Step 1: Create the Hub

The Hub is the server-side endpoint that clients connect to.

```csharp
// Services/MyFeature/Hubs/MyFeatureHub.cs
using Microsoft.AspNetCore.SignalR;

namespace MyApp.Services.MyFeature.Hubs
{
    public class MyFeatureHub : Hub
    {
        private readonly ILogger<MyFeatureHub> _logger;

        public MyFeatureHub(ILogger<MyFeatureHub> logger)
        {
            _logger = logger;
        }

        #region Connection Lifecycle

        public override async Task OnConnectedAsync()
        {
            _logger.LogInformation("Client connected: {ConnectionId}", Context.ConnectionId);
            await base.OnConnectedAsync();
        }

        public override async Task OnDisconnectedAsync(Exception? exception)
        {
            if (exception != null)
            {
                _logger.LogError(exception, "Client disconnected with error: {ConnectionId}", Context.ConnectionId);
            }
            else
            {
                _logger.LogInformation("Client disconnected: {ConnectionId}", Context.ConnectionId);
            }
            await base.OnDisconnectedAsync(exception);
        }

        #endregion

        #region Group Management

        /// <summary>
        /// Join a company-wide group (all users in a company receive updates)
        /// </summary>
        public async Task JoinCompanyGroup(int companyId)
        {
            var groupName = $"Company_{companyId}";
            await Groups.AddToGroupAsync(Context.ConnectionId, groupName);
            _logger.LogInformation("Connection {ConnectionId} joined group {GroupName}",
                Context.ConnectionId, groupName);

            // Optionally confirm to the client
            await Clients.Caller.SendAsync("JoinedGroup", new { groupName });
        }

        /// <summary>
        /// Leave a company group
        /// </summary>
        public async Task LeaveCompanyGroup(int companyId)
        {
            var groupName = $"Company_{companyId}";
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, groupName);
            _logger.LogInformation("Connection {ConnectionId} left group {GroupName}",
                Context.ConnectionId, groupName);
        }

        /// <summary>
        /// Join a team-specific group (only team members receive updates)
        /// </summary>
        public async Task JoinTeamGroup(int managerId, int companyId)
        {
            var groupName = $"Team_{managerId}_{companyId}";
            await Groups.AddToGroupAsync(Context.ConnectionId, groupName);
            _logger.LogInformation("Connection {ConnectionId} joined team group {GroupName}",
                Context.ConnectionId, groupName);
        }

        /// <summary>
        /// Leave a team group
        /// </summary>
        public async Task LeaveTeamGroup(int managerId, int companyId)
        {
            var groupName = $"Team_{managerId}_{companyId}";
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, groupName);
        }

        #endregion
    }
}
```

### Step 2: Create the Hub Service

The Hub Service is used by other services to send notifications. It uses `IHubContext<T>` to send messages without needing a direct connection.

```csharp
// Services/MyFeature/MyFeatureHubService.cs
using Microsoft.AspNetCore.SignalR;
using MyApp.Services.MyFeature.Hubs;

namespace MyApp.Services.MyFeature
{
    public interface IMyFeatureHubService
    {
        Task NotifyItemCreatedAsync(int companyId, int? teamManagerId, ItemDto item);
        Task NotifyItemUpdatedAsync(int companyId, int? teamManagerId, ItemDto item);
        Task NotifyItemDeletedAsync(int companyId, int? teamManagerId, int itemId);
    }

    public class MyFeatureHubService : IMyFeatureHubService
    {
        private readonly IHubContext<MyFeatureHub> _hubContext;
        private readonly ILogger<MyFeatureHubService> _logger;

        public MyFeatureHubService(
            IHubContext<MyFeatureHub> hubContext,
            ILogger<MyFeatureHubService> logger)
        {
            _hubContext = hubContext;
            _logger = logger;
        }

        public async Task NotifyItemCreatedAsync(int companyId, int? teamManagerId, ItemDto item)
        {
            await NotifyAsync(companyId, teamManagerId, "ItemCreated", item);
        }

        public async Task NotifyItemUpdatedAsync(int companyId, int? teamManagerId, ItemDto item)
        {
            await NotifyAsync(companyId, teamManagerId, "ItemUpdated", item);
        }

        public async Task NotifyItemDeletedAsync(int companyId, int? teamManagerId, int itemId)
        {
            await NotifyAsync(companyId, teamManagerId, "ItemDeleted", new { itemId });
        }

        private async Task NotifyAsync(int companyId, int? teamManagerId, string eventName, object data)
        {
            try
            {
                var payload = new
                {
                    eventType = eventName,
                    data,
                    timestamp = DateTime.UtcNow
                };

                // Always notify the company group (admins see everything)
                var companyGroup = $"Company_{companyId}";
                await _hubContext.Clients.Group(companyGroup)
                    .SendAsync("ReceiveUpdate", payload);

                // Also notify the team group if a manager is specified
                if (teamManagerId.HasValue)
                {
                    var teamGroup = $"Team_{teamManagerId.Value}_{companyId}";
                    await _hubContext.Clients.Group(teamGroup)
                        .SendAsync("ReceiveUpdate", payload);
                }

                _logger.LogDebug("Sent {EventName} to Company_{CompanyId}" +
                    (teamManagerId.HasValue ? $" and Team_{teamManagerId.Value}_{companyId}" : ""),
                    eventName, companyId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error sending SignalR notification for {EventName}", eventName);
            }
        }
    }
}
```

### Step 3: Register Services in Program.cs

```csharp
// Program.cs

// Add SignalR
builder.Services.AddSignalR();

// Register the hub service
builder.Services.AddScoped<IMyFeatureHubService, MyFeatureHubService>();

// ... other services ...

var app = builder.Build();

// Map the hub endpoint
app.MapHub<MyFeatureHub>("/myFeatureHub");

app.Run();
```

### Step 4: Connect from a Blazor Component

```razor
@page "/my-feature"
@using Microsoft.AspNetCore.SignalR.Client
@inject NavigationManager Navigation
@inject ILogger<MyFeaturePage> Logger
@implements IAsyncDisposable

<h3>My Feature</h3>

@if (_isConnected)
{
    <MudChip Color="Color.Success" Size="Size.Small">Live Updates Active</MudChip>
}
else
{
    <MudChip Color="Color.Warning" Size="Size.Small">Connecting...</MudChip>
}

<!-- Your UI here -->

@code {
    private HubConnection? _hubConnection;
    private bool _signalRInitialized = false;
    private bool _isConnected = false;

    // Assuming these come from your session/auth
    [CascadingParameter] public UserSession UserSession { get; set; } = default!;

    protected override async Task OnInitializedAsync()
    {
        await LoadDataAsync();
    }

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        // Initialize SignalR only once, after first render
        if (firstRender && !_signalRInitialized)
        {
            _signalRInitialized = true;
            await InitializeSignalR();
        }
    }

    private async Task InitializeSignalR(int retryCount = 0)
    {
        try
        {
            // 1. Build the connection
            _hubConnection = new HubConnectionBuilder()
                .WithUrl(Navigation.ToAbsoluteUri("/myFeatureHub"))
                .WithAutomaticReconnect(new[] {
                    TimeSpan.FromSeconds(0),   // Immediate first retry
                    TimeSpan.FromSeconds(2),   // Then 2s
                    TimeSpan.FromSeconds(5),   // Then 5s
                    TimeSpan.FromSeconds(30)   // Then 30s
                })
                .Build();

            // 2. Set up connection state handlers
            _hubConnection.Reconnecting += error =>
            {
                _isConnected = false;
                Logger.LogWarning("SignalR reconnecting...");
                InvokeAsync(StateHasChanged);
                return Task.CompletedTask;
            };

            _hubConnection.Reconnected += async connectionId =>
            {
                _isConnected = true;
                Logger.LogInformation("SignalR reconnected: {ConnectionId}", connectionId);

                // IMPORTANT: Rejoin groups after reconnection!
                await JoinGroupsAsync();
                await InvokeAsync(StateHasChanged);
            };

            _hubConnection.Closed += error =>
            {
                _isConnected = false;
                Logger.LogError(error, "SignalR connection closed");
                InvokeAsync(StateHasChanged);
                return Task.CompletedTask;
            };

            // 3. Register message handlers BEFORE starting connection
            _hubConnection.On<object>("ReceiveUpdate", async (payload) =>
            {
                await HandleUpdateAsync(payload);
            });

            // 4. Start the connection
            await _hubConnection.StartAsync();
            _isConnected = true;
            Logger.LogInformation("SignalR connected successfully");

            // 5. Join the appropriate groups
            await JoinGroupsAsync();
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Error connecting to SignalR (attempt {RetryCount})", retryCount + 1);

            // Retry with exponential backoff
            if (retryCount < 3)
            {
                var delay = 1000 * (retryCount + 1); // 1s, 2s, 3s
                await Task.Delay(delay);
                await InitializeSignalR(retryCount + 1);
            }
        }
    }

    private async Task JoinGroupsAsync()
    {
        if (_hubConnection?.State != HubConnectionState.Connected) return;

        try
        {
            // Join company group for admin-level updates
            await _hubConnection.InvokeAsync("JoinCompanyGroup", UserSession.Empresa.Id);

            // OR join team group for team-level updates
            // await _hubConnection.InvokeAsync("JoinTeamGroup", UserSession.User.Id, UserSession.Empresa.Id);
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Error joining SignalR groups");
        }
    }

    private async Task HandleUpdateAsync(object payload)
    {
        Logger.LogInformation("Received update: {Payload}", payload);

        try
        {
            // Reload your data
            await LoadDataAsync();

            // Update the UI (must use InvokeAsync from SignalR callback)
            await InvokeAsync(StateHasChanged);
        }
        catch (Exception ex)
        {
            Logger.LogError(ex, "Error handling SignalR update");
        }
    }

    private async Task LoadDataAsync()
    {
        // Your data loading logic
    }

    public async ValueTask DisposeAsync()
    {
        if (_hubConnection is not null)
        {
            try
            {
                // Leave groups before disposing
                if (_hubConnection.State == HubConnectionState.Connected)
                {
                    await _hubConnection.InvokeAsync("LeaveCompanyGroup", UserSession.Empresa.Id);
                }

                await _hubConnection.DisposeAsync();
            }
            catch (Exception ex)
            {
                Logger.LogError(ex, "Error disposing SignalR connection");
            }
        }
    }
}
```

## Understanding Groups

Groups are the key to targeting notifications to the right users.

### Group Naming Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GROUP NAMING PATTERNS                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Company-Wide (Admins see all):                                         │
│  ┌─────────────────────────────────────────┐                            │
│  │  "Company_{companyId}"                  │                            │
│  │  Example: "Company_1"                   │                            │
│  │  Receives: All events for the company   │                            │
│  └─────────────────────────────────────────┘                            │
│                                                                         │
│  Team-Specific (Managers see their team):                               │
│  ┌─────────────────────────────────────────┐                            │
│  │  "Team_{managerId}_{companyId}"         │                            │
│  │  Example: "Team_5_1"                    │                            │
│  │  Receives: Events for manager #5's team │                            │
│  └─────────────────────────────────────────┘                            │
│                                                                         │
│  User-Specific (Private notifications):                                 │
│  ┌─────────────────────────────────────────┐                            │
│  │  "User_{userId}"                        │                            │
│  │  Example: "User_42"                     │                            │
│  │  Receives: Events only for user #42     │                            │
│  └─────────────────────────────────────────┘                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### When to Notify Which Group

```csharp
// In your service that triggers the event:
public async Task CreateItemAsync(CreateItemRequest request)
{
    // ... create the item ...

    // Determine who should be notified
    int companyId = GetCompanyId();
    int? teamManagerId = GetManagerIdForEmployee(request.EmployeeId);

    // Both groups are notified:
    // - Company group (admins see it)
    // - Team group (manager sees it) - only if managerId is not null
    await _hubService.NotifyItemCreatedAsync(companyId, teamManagerId, item);
}
```

### Common Pitfall: Mismatched Group Names

```
THE BUG: Manager Dashboard not receiving updates

Dashboard joins:    "Team_{UserSession.User.Id}_{empresaId}"
                    "Team_5_1" (Manager's User ID is 5)

Notification sent to: "Team_{employee.ReportToUser}_{empresaId}"
                      "Team_null_1" (Employee has no ReportToUser set!)

RESULT: Notification goes to a group nobody has joined!
```

**Solution**: Ensure the employee's data has the correct manager reference, OR use a different group strategy.

## Message Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          COMPLETE MESSAGE FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

1. USER ACTION (e.g., Employee checks in)
   │
   ▼
2. SERVICE LAYER (AttendanceOperationService)
   │
   │  // After saving to database...
   │  var (empresaId, managerId) = await GetNotificationContext(employeeId);
   │  await _hubService.NotifyCheckInAsync(empresaId, managerId, attendance);
   │
   ▼
3. HUB SERVICE (AttendanceHubService)
   │
   │  // Send to company group
   │  await _hubContext.Clients.Group($"Company_{empresaId}")
   │      .SendAsync("ReceiveUpdate", payload);
   │
   │  // Send to team group (if manager exists)
   │  if (managerId.HasValue)
   │      await _hubContext.Clients.Group($"Team_{managerId}_{empresaId}")
   │          .SendAsync("ReceiveUpdate", payload);
   │
   ▼
4. SIGNALR HUB (Routes to connections in groups)
   │
   ├────────────────────────────────────────────┐
   │                                            │
   ▼                                            ▼
5a. ADMIN DASHBOARD                         5b. MANAGER DASHBOARD
    (Member of "Company_1")                     (Member of "Team_5_1")
    │                                           │
    │  _hubConnection.On("ReceiveUpdate",       │  _hubConnection.On("ReceiveUpdate",
    │      HandleUpdateAsync);                  │      HandleUpdateAsync);
    │                                           │
    ▼                                           ▼
6a. RELOAD DATA & UPDATE UI                 6b. RELOAD DATA & UPDATE UI
    await LoadDashboardDataAsync();             await LoadTeamDataAsync();
    await InvokeAsync(StateHasChanged);         await InvokeAsync(StateHasChanged);
```

## Best Practices

### 1. Always Handle Reconnection

```csharp
_hubConnection.Reconnected += async connectionId =>
{
    // CRITICAL: Rejoin groups after reconnection!
    // SignalR does NOT remember your groups after disconnect
    await JoinGroupsAsync();
};
```

### 2. Use InvokeAsync for UI Updates

```csharp
// WRONG - May cause threading issues
_hubConnection.On<object>("ReceiveUpdate", (data) =>
{
    _items = LoadItems();
    StateHasChanged(); // DANGER: Not on UI thread!
});

// CORRECT - Use InvokeAsync
_hubConnection.On<object>("ReceiveUpdate", async (data) =>
{
    await LoadItemsAsync();
    await InvokeAsync(StateHasChanged); // Safe: Marshals to UI thread
});
```

### 3. Always Dispose Connections

```csharp
public async ValueTask DisposeAsync()
{
    if (_hubConnection is not null)
    {
        // Leave groups first (optional but polite)
        if (_hubConnection.State == HubConnectionState.Connected)
        {
            await _hubConnection.InvokeAsync("LeaveCompanyGroup", _companyId);
        }

        await _hubConnection.DisposeAsync();
    }
}
```

### 4. Register Handlers Before Starting

```csharp
// WRONG - May miss early messages
await _hubConnection.StartAsync();
_hubConnection.On("ReceiveUpdate", HandleUpdate); // Too late!

// CORRECT - Register first
_hubConnection.On("ReceiveUpdate", HandleUpdate);
await _hubConnection.StartAsync(); // Now ready to receive
```

### 5. Initialize in OnAfterRenderAsync

```csharp
// WRONG - NavigationManager not ready in OnInitializedAsync
protected override async Task OnInitializedAsync()
{
    await InitializeSignalR(); // May fail!
}

// CORRECT - Wait for first render
protected override async Task OnAfterRenderAsync(bool firstRender)
{
    if (firstRender && !_signalRInitialized)
    {
        _signalRInitialized = true;
        await InitializeSignalR();
    }
}
```

## Attendance Hub - Real Implementation

This project uses SignalR for live attendance updates. Here are the **actual** names used:

### Actual Group Names

| Group Type | Pattern | Example |
|------------|---------|---------|
| Company-wide | `CompanyAttendance_{empresaId}` | `CompanyAttendance_1` |
| Team-specific | `TeamAttendance_{managerId}_{empresaId}` | `TeamAttendance_5_1` |

### Actual Hub Methods

| Method | Purpose |
|--------|---------|
| `JoinCompanyAttendance(int empresaId)` | Join company group |
| `LeaveCompanyAttendance(int empresaId)` | Leave company group |
| `JoinTeamAttendance(int managerId, int empresaId)` | Join team group |
| `LeaveTeamAttendance(int managerId, int empresaId)` | Leave team group |

### Actual Event Names

| Event | Sent By | Purpose |
|-------|---------|---------|
| `ReceiveAttendanceUpdate` | AttendanceHubService | All attendance events (check-in, check-out, break, validation) |
| `JoinedCompanyAttendance` | Hub | Confirmation of joining company group |
| `JoinedTeamAttendance` | Hub | Confirmation of joining team group |

### AttendanceHubService Event Payload

When `ReceiveAttendanceUpdate` is sent, the payload includes:

```csharp
{
    eventType,          // "CheckIn", "CheckOut", "BreakStart", "BreakEnd", "Validation"
    attendanceId,
    employeeId,
    employeeName,
    checkInTime,
    checkOutTime,
    breakStartTime,
    breakEndTime,
    isValidated,
    isValidLocation,
    jobId,
    jobName,
    totalHours,
    timestamp
}
```

### Working Example: AttendanceInsightsHub.razor

```csharp
// 1. Build connection to the correct endpoint
_hub = new HubConnectionBuilder()
    .WithUrl(Navigation.ToAbsoluteUri("/attendanceHub"))  // Must match Program.cs
    .WithAutomaticReconnect()
    .Build();

// 2. Listen for the CORRECT event name
_hub.On<object>("ReceiveAttendanceUpdate", async (_) =>
{
    // Refresh the child component that displays data
    if (_liveStatsViewRef != null)
    {
        await InvokeAsync(async () =>
        {
            await _liveStatsViewRef.RefreshAsync();
        });
    }
});

// 3. Start connection
await _hub.StartAsync();

// 4. Join the company group with correct method name
await _hub.InvokeAsync("JoinCompanyAttendance", UserSession.Empresa.Id);
```

### Refreshing Child Components

When the parent receives a SignalR event, it must tell the child to reload data:

```csharp
// Parent component
private ChildView? _childRef;

// In SignalR handler - DON'T just call StateHasChanged!
_hub.On<object>("ReceiveAttendanceUpdate", async (_) =>
{
    await InvokeAsync(async () =>
    {
        await _childRef.RefreshAsync();  // Tell child to reload
    });
});

// Child component - expose a refresh method
public async Task RefreshAsync()
{
    await LoadDataAsync();  // Actually reload data
    StateHasChanged();      // Then update UI
}
```

**Why?** Parent's `StateHasChanged()` doesn't make children re-execute their `OnInitializedAsync()`.

---

## Debugging SignalR Issues

### Enable Detailed Logging

```csharp
// In Program.cs
builder.Logging.AddFilter("Microsoft.AspNetCore.SignalR", LogLevel.Debug);
builder.Logging.AddFilter("Microsoft.AspNetCore.Http.Connections", LogLevel.Debug);
```

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Not receiving messages | Wrong event name | Check `SendAsync("EventName")` matches `.On("EventName")` exactly |
| Not receiving messages | Not in the right group | Check group name matches exactly |
| Child component not updating | Only calling parent StateHasChanged | Call child's RefreshAsync() to reload data |
| Messages stop after reconnect | Groups lost on reconnect | Rejoin groups in `Reconnected` handler |
| "Connection not found" error | Hub disposed too early | Implement proper `IAsyncDisposable` |
| UI not updating | Not using `InvokeAsync` | Wrap `StateHasChanged` in `InvokeAsync` |
| Connection fails | Wrong hub URL | Check `MapHub` matches `WithUrl` |

### Critical Bug: Wrong Event Name

This is the **#1 cause** of "SignalR not working":

```csharp
// ❌ WRONG - listening for event that doesn't exist
_hub.On<object>("AttendanceUpdated", async (data) => { ... });

// ✅ CORRECT - matches what AttendanceHubService.SendAsync sends
_hub.On<object>("ReceiveAttendanceUpdate", async (data) => { ... });
```

**How to find the correct name:**
1. Look at `AttendanceHubService.cs` (or your HubService)
2. Find the `SendAsync` calls
3. The first parameter is the event name clients must listen for

## Related Files in This Project

- [AttendanceHub.cs](../../Services/Attendance/Hubs/AttendanceHub.cs) - Hub implementation
- [AttendanceHubService.cs](../../Services/Attendance/AttendanceHubService.cs) - Service for sending notifications
- [AdminDashboard.razor](../../Pages/HR/Attendances/Dashboard/AdminDashboard.razor) - Working SignalR consumer
- [SignalRConfiguration.cs](../../Configuration/SignalRConfiguration.cs) - Configuration setup
