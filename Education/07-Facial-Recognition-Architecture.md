# Facial Recognition Architecture

> **Level**: Intermediate
> **Topic**: Facial Recognition System for Attendance

## Overview

The HRModule facial recognition system enables employees to check-in/out using their face instead of passwords or cards. It uses a hybrid client-server architecture where:

- **Client (Browser)**: Detects faces and extracts facial descriptors using face-api.js
- **Server (C#)**: Matches descriptors against the database and records attendance

## Why Client-Side Detection?

Face detection is computationally intensive. By running it in the browser:

1. **Reduced Server Load**: Processing happens on user's device
2. **Better Performance**: No video streaming to server required
3. **Privacy**: Raw images never leave the device

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            BROWSER (Client)                                │
│                                                                            │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────────────┐  │
│  │   Webcam     │───▶│  face-api.js │───▶│  128-dimensional vector   │  │
│  │   (Video)    │    │  (ML Model)  │    │  "Face Descriptor"         │  │
│  └──────────────┘    └──────────────┘    └─────────────┬──────────────┘  │
│                                                         │                  │
│                                                         │ JSON             │
│                                                         ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                          script.js                                   │  │
│  │  - Starts camera                                                     │  │
│  │  - Runs face detection loop                                          │  │
│  │  - Requires 10 consecutive face detections (anti-spoofing)          │  │
│  │  - Calls DotNet.invokeMethodAsync() when ready                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────┬───────────────────────────────────┘
                                        │
                                        │ JSInvokable
                                        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                            SERVER (C# Blazor)                              │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    FacialRecognitionHelper (Static)                  │  │
│  │  - Receives JS callbacks                                             │  │
│  │  - Routes to specific component via instanceId                       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                        │                                   │
│                                        ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    FacialAttendanceComponent                         │  │
│  │  - UI for camera preview and status                                  │  │
│  │  - Handles mode: Identify, CheckIn, CheckOut, Break                 │  │
│  │  - Calls orchestrator for processing                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                        │                                   │
│                                        ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    FacialAttendanceOrchestrator                      │  │
│  │  - Coordinates between services                                      │  │
│  │  - Discovers employee's company database                            │  │
│  │  - Calls FacialRecognitionService for matching                      │  │
│  │  - Calls AttendanceService for recording                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                        │                                   │
│                     ┌──────────────────┴──────────────────┐               │
│                     ▼                                      ▼               │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────┐  │
│  │  FacialRecognitionService   │    │     AttendanceService           │  │
│  │  - Loads all user biomarkers│    │     - CheckIn/CheckOut          │  │
│  │  - Compares descriptors     │    │     - Start/End Break           │  │
│  │  - Returns best match       │    │     - Records GPS, timestamps   │  │
│  └─────────────────────────────┘    └─────────────────────────────────┘  │
│                     │                                      │               │
│                     └──────────────────┬──────────────────┘               │
│                                        ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                           DATABASE                                   │  │
│  │  CRM_UTILIZADOR.Biomarkers    │    Attendance (records)             │  │
│  │  (JSON array of floats)       │    (CheckIn/Out times, GPS, etc)   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. face-api.js (Client)

JavaScript library that runs ML models in the browser:

- **TinyFaceDetector**: Fast face detection
- **FaceLandmark68Net**: Facial landmarks (eyes, nose, mouth)
- **FaceRecognitionNet**: Extracts 128-dimensional descriptor

Location: `wwwroot/js/face/face-api.min.js`

### 2. script.js (Client)

Custom JavaScript that orchestrates the detection flow:

```javascript
// Detection loop
processingInterval = setInterval(async () => {
    const detection = await faceapi
        .detectSingleFace(video)
        .withFaceLandmarks()
        .withFaceDescriptor();

    if (detection && detection.detection.score >= 0.5) {
        consecutiveMatches++;
        if (consecutiveMatches >= 10) {
            // Send descriptor to server
            await invokeHelper('NotifyFacialIdentifyCompleteForInstance',
                instanceId, JSON.stringify(descriptor));
        }
    }
}, 100);
```

Location: `wwwroot/js/face/script.js`

### 3. FacialRecognitionHelper (Server)

Static class that bridges JavaScript and Blazor:

```csharp
[JSInvokable]
public static void NotifyFacialIdentifyCompleteForInstance(string instanceId, string descriptor)
{
    // Route to specific component instance
    if (_identifyCallbacks.TryGetValue(instanceId, out var callback))
    {
        callback.Invoke(descriptor);
    }
}
```

Location: `Services/FacialRecognition/FacialRecognitionHelper.cs`

### 4. FacialAttendanceComponent (Server)

Blazor component for the camera UI:

```razor
<video id="@_videoElementId" autoplay muted></video>
<MudProgressLinear Value="@_progressPercentage" />
<MudAlert>@_statusMessage</MudAlert>
```

Location: `Pages/HR/Attendances/Facial/Components/FacialAttendanceComponent.razor`

### 5. FacialRecognitionService (Server)

Matches descriptors against the database:

```csharp
public async Task<FacialMatchResult> IdentifyForAttendanceAsync(byte[] descriptor)
{
    // Load all users with biomarkers
    var users = await context.CrmUtilizadors
        .Where(u => u.Biomarkers != null)
        .ToListAsync();

    // Find best match using Euclidean distance
    foreach (var user in users)
    {
        float distance = CalculateEuclideanDistance(descriptor, user.Biomarkers);
        if (distance < bestDistance)
        {
            bestDistance = distance;
            bestMatch = user;
        }
    }

    // Return match if below threshold
    return bestDistance < 0.5f
        ? new FacialMatchResult { IsMatch = true, UserId = bestMatch.Id }
        : new FacialMatchResult { IsMatch = false };
}
```

Location: `Services/FacialRecognition/FacialRecognitionService.cs`

## Data Flow: Check-In Example

```
1. User clicks "Identificar-me" button
   ↓
2. FacialAttendanceComponent.StartFacialCapture()
   - Calls JS: facialRecognition.startIdentify(videoId, canvasId, instanceId)
   ↓
3. script.js starts camera and detection loop
   - Detects face, extracts 128D descriptor
   - Requires 10 consecutive detections
   ↓
4. JS calls DotNet.invokeMethodAsync('NotifyFacialIdentifyCompleteForInstance', instanceId, descriptor)
   ↓
5. FacialRecognitionHelper routes to component's callback
   ↓
6. FacialAttendanceComponent.HandleIdentifyComplete(descriptor)
   - Calls FacialAttendanceOrchestrator.IdentifyUserForAttendanceAsync()
   ↓
7. Orchestrator discovers user's company database
   - Calls FacialRecognitionService.IdentifyForAttendanceAsync()
   ↓
8. FacialRecognitionService compares descriptor against all users
   - Finds best match with Euclidean distance
   - Returns UserId and EmployeeId
   ↓
9. Component displays employee info and action buttons
   ↓
10. User clicks "Fazer Check-In"
    - AttendanceService.CheckInAsync() records the attendance
```

## Security Model

### What Happens Client-Side
- Camera access
- Face detection (ML)
- Descriptor extraction
- **NO** authentication decisions

### What Happens Server-Side
- Descriptor comparison
- User identification
- Attendance recording
- **ALL** authentication decisions

### Why This is Secure
1. Client only sends mathematical descriptors, not images
2. Server validates all operations
3. Descriptors cannot be reversed to images
4. 10 consecutive matches required (anti-spoofing)

## Face Descriptor Explained

A face descriptor is a 128-dimensional vector of floats:

```json
[0.12, -0.45, 0.78, 0.23, -0.11, ... (128 values)]
```

Properties:
- **Unique to each person**: Like a fingerprint
- **Consistent**: Same face produces similar descriptors
- **Compact**: Only ~512 bytes per face
- **Irreversible**: Cannot recreate face from descriptor

### Matching Algorithm

```csharp
float CalculateEuclideanDistance(float[] desc1, float[] desc2)
{
    float sum = 0;
    for (int i = 0; i < 128; i++)
    {
        float diff = desc1[i] - desc2[i];
        sum += diff * diff;
    }
    return Math.Sqrt(sum);
}

// Distance < 0.5 = Same person
// Distance > 0.5 = Different people
```

## Kiosk Mode

The `FacialAttendanceKiosk.razor` page provides a simplified UI for shared devices:

```
┌─────────────────────────────────────┐
│         ATTENDANCE KIOSK            │
│                                     │
│  ┌─────────────────────────────┐   │
│  │                             │   │
│  │        [Camera View]        │   │
│  │                             │   │
│  └─────────────────────────────┘   │
│                                     │
│  [==========] 8/10 matches         │
│                                     │
│  "Rosto detetado! A verificar..."  │
│                                     │
└─────────────────────────────────────┘
```

After identification:
```
┌─────────────────────────────────────┐
│           Bem-vindo!                │
│                                     │
│       [Avatar] João Silva          │
│       Check-in: 08:45              │
│       Status: A trabalhar          │
│                                     │
│  ┌──────────┐  ┌──────────────┐   │
│  │  Pausa   │  │  Check-Out   │   │
│  └──────────┘  └──────────────┘   │
│                                     │
│       [Nova Identificação]          │
└─────────────────────────────────────┘
```

## Related Files

| File | Purpose |
|------|---------|
| [FacialRecognitionHelper.cs](../../Services/FacialRecognition/FacialRecognitionHelper.cs) | JS/Blazor bridge |
| [FacialRecognitionService.cs](../../Services/FacialRecognition/FacialRecognitionService.cs) | Matching logic |
| [FacialAttendanceOrchestrator.cs](../../Services/Orchestration/FacialAttendanceOrchestrator.cs) | Coordination |
| [FacialAttendanceComponent.razor](../../Pages/HR/Attendances/Facial/Components/FacialAttendanceComponent.razor) | Camera UI |
| [FacialAttendanceKiosk.razor](../../Pages/HR/Attendances/Facial/FacialAttendanceKiosk.razor) | Kiosk page |
| [script.js](../../wwwroot/js/face/script.js) | JS detection |
| [face-api.min.js](../../wwwroot/js/face/face-api.min.js) | ML library |

## Configuration

In `appsettings.json`:

```json
{
  "FacialRecognition": {
    "MatchingThreshold": 0.5
  }
}
```

- **MatchingThreshold**: Euclidean distance threshold (lower = stricter)
  - 0.4 = Very strict (fewer false positives, more false negatives)
  - 0.5 = Balanced (recommended)
  - 0.6 = Lenient (more false positives, fewer false negatives)
