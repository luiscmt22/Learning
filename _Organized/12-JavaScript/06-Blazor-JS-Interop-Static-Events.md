# Blazor JS Interop: Static Events vs Instance-Isolated Callbacks

> **Level**: Advanced
> **Topic**: Blazor Server + JavaScript Interop Race Conditions

## The Problem

When Blazor components need to receive callbacks from JavaScript, a common pattern is using static events:

```csharp
// Static helper class
public static class MyHelper
{
    public static event Action<string>? OnDataReceived;

    [JSInvokable]
    public static void NotifyDataReceived(string data)
    {
        OnDataReceived?.Invoke(data);
    }
}
```

```javascript
// JavaScript
DotNet.invokeMethodAsync('MyApp', 'NotifyDataReceived', data);
```

**This works perfectly when only ONE component is active.** But when multiple component instances exist simultaneously (e.g., two kiosks, two browser tabs), **all subscribers receive all events**.

## The Bug: Data Leakage Between Concurrent Users

### Scenario

Two facial recognition kiosks running simultaneously:

```
Kiosk A (Component Instance #1)
├── Subscribes to: FacialRecognitionHelper.OnFacialIdentifyComplete
└── User Alice approaches and scans face

Kiosk B (Component Instance #2)
├── Subscribes to: FacialRecognitionHelper.OnFacialIdentifyComplete (SAME EVENT!)
└── User Bob approaches and scans face
```

### Timeline of Bug

```
T0: Alice's face detected    → JS calls NotifyFacialIdentifyComplete(aliceDescriptor)
T1: Static event broadcasts to ALL subscribers
T2: BOTH Kiosk A and Kiosk B receive Alice's descriptor
T3: Both kiosks call IdentifyUserForAttendanceAsync(aliceDescriptor)
T4: Both kiosks display "Welcome, Alice!" (BOB SEES ALICE'S DATA!)

T5: Bob's face detected     → JS calls NotifyFacialIdentifyComplete(bobDescriptor)
T6: BOTH kiosks receive Bob's descriptor
T7: BOTH kiosks now show "Welcome, Bob!" (ALICE'S SCREEN CHANGES!)
```

### Diagram: Broadcast Problem

```
┌─────────────────────────────────────────────────────────────────────┐
│                        JAVASCRIPT (face-api.js)                      │
│                                                                       │
│  Face Detected → DotNet.invokeMethodAsync('NotifyFacialIdentify')   │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STATIC HELPER (C#)                                │
│                                                                       │
│  [JSInvokable]                                                       │
│  public static void NotifyFacialIdentifyComplete(string descriptor)  │
│  {                                                                   │
│      OnFacialIdentifyComplete?.Invoke(descriptor);  // BROADCASTS!  │
│  }                                                                   │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                  │
              ▼                                  ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│      KIOSK A            │      │      KIOSK B            │
│  OnIdentifyComplete()   │      │  OnIdentifyComplete()   │
│  _employee = Alice      │      │  _employee = Alice (!)  │
│                         │      │  (Should be Bob!)       │
└─────────────────────────┘      └─────────────────────────┘
```

## The Solution: Instance-Isolated Callbacks

Instead of broadcasting to all subscribers, route events to the specific component instance that initiated the action.

### Pattern Overview

```
1. Component generates unique instanceId (Guid)
2. Component registers its callback with the helper using instanceId
3. Component passes instanceId to JavaScript when starting capture
4. JavaScript includes instanceId when calling back to .NET
5. Helper routes callback ONLY to the registered instance
6. Component unregisters in Dispose()
```

### Implementation

#### 1. Static Helper with Instance Registry

```csharp
public static class FacialRecognitionHelper
{
    // Instance-specific callbacks (thread-safe)
    private static readonly ConcurrentDictionary<string, Action<string>> _identifyCallbacks = new();

    // Register instance callback
    public static void RegisterInstance(string instanceId, Action<string> onIdentify)
    {
        _identifyCallbacks[instanceId] = onIdentify;
    }

    // Unregister on dispose
    public static void UnregisterInstance(string instanceId)
    {
        _identifyCallbacks.TryRemove(instanceId, out _);
    }

    // Instance-specific callback (NEW - routes to specific instance)
    [JSInvokable]
    public static void NotifyFacialIdentifyCompleteForInstance(string instanceId, string descriptor)
    {
        if (_identifyCallbacks.TryGetValue(instanceId, out var callback))
        {
            callback.Invoke(descriptor);
        }
    }
}
```

#### 2. Component with Instance ID

```csharp
@code {
    private readonly string _instanceId = Guid.NewGuid().ToString();

    protected override void OnInitialized()
    {
        // Register this instance's callback
        FacialRecognitionHelper.RegisterInstance(_instanceId, HandleIdentifyComplete);
    }

    private async Task StartCapture()
    {
        // Pass instanceId to JavaScript
        await JS.InvokeVoidAsync("facialRecognition.startIdentify",
            _videoElementId, _canvasContainerId, _instanceId);
    }

    public void Dispose()
    {
        FacialRecognitionHelper.UnregisterInstance(_instanceId);
    }
}
```

#### 3. JavaScript with Instance Routing

```javascript
let currentInstanceId = null;

async function startFacialAttendance(videoElementId, canvasContainerId, mode, instanceId) {
    currentInstanceId = instanceId;

    // ... face detection code ...

    // When face is detected, call back with instanceId
    if (currentInstanceId) {
        await DotNet.invokeMethodAsync('HRModule',
            'NotifyFacialIdentifyCompleteForInstance',
            currentInstanceId,
            descriptorJson);
    }
}
```

### Diagram: Instance-Isolated Solution

```
┌─────────────────────────────────────────────────────────────────────┐
│                        JAVASCRIPT (face-api.js)                      │
│                                                                       │
│  startIdentify(videoId, canvasId, instanceId="abc-123")             │
│  ↓                                                                   │
│  Face Detected → NotifyFacialIdentifyCompleteForInstance(           │
│                      "abc-123",    ← Instance ID                     │
│                      descriptor)                                      │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STATIC HELPER (C#)                                │
│                                                                       │
│  _identifyCallbacks = {                                              │
│      "abc-123": KioskA.HandleIdentify,                               │
│      "def-456": KioskB.HandleIdentify                                │
│  }                                                                   │
│                                                                       │
│  NotifyFacialIdentifyCompleteForInstance("abc-123", descriptor)      │
│  → Routes ONLY to Kiosk A's callback                                 │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│      KIOSK A            │      │      KIOSK B            │
│  instanceId = "abc-123" │      │  instanceId = "def-456" │
│  HandleIdentify() ✓     │      │  (not called)          │
│  _employee = Alice      │      │  _employee = Bob        │
└─────────────────────────┘      └─────────────────────────┘
```

## When to Use Each Pattern

### Static Events (Broadcast) - OK When:
- Only ONE component instance will ever exist
- All components should receive all events (rare)
- The callback is truly global (app-level notifications)

### Instance-Isolated Callbacks - Required When:
- Multiple component instances may be active simultaneously
- Each instance should only receive its own events
- User data must be isolated between sessions
- Security/privacy is important

## Key Takeaways

1. **Static events are shared** - All subscribers receive all events
2. **Instance IDs provide isolation** - Each component gets only its events
3. **ConcurrentDictionary is thread-safe** - Multiple registrations are safe
4. **Always unregister in Dispose()** - Prevent memory leaks
5. **JavaScript must track the instanceId** - Pass it through the entire flow

## Related Files

- [FacialRecognitionHelper.cs](../../Services/FacialRecognition/FacialRecognitionHelper.cs)
- [FacialAttendanceComponent.razor](../../Pages/HR/Attendances/Facial/Components/FacialAttendanceComponent.razor)
- [script.js](../../wwwroot/js/face/script.js)
