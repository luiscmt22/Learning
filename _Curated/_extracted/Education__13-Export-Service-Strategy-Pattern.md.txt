# Strategy Pattern in Export Services

## Overview

The Attendance Export Service demonstrates a real-world implementation of the **Strategy Pattern** - one of the most powerful behavioral design patterns. This document explains the pattern, why it's used, and how it follows SOLID principles.

## The Problem Without Strategy Pattern

Imagine implementing exports like this:

```csharp
// BAD: Violates Open/Closed Principle
public byte[] GenerateReport(ReportType type, ExportFormat format, Data data)
{
    // Build report data
    switch (type)
    {
        case ReportType.AttendanceSummary:
            // 50 lines of summary logic...
            break;
        case ReportType.LeaveMap:
            // 50 lines of leave logic...
            break;
        // ... 6 more cases
    }

    // Generate output
    switch (format)
    {
        case ExportFormat.Excel:
            // 100 lines of Excel generation...
            break;
        case ExportFormat.Pdf:
            // 100 lines of PDF generation...
            break;
        // ... more cases
    }
}
```

### Problems with This Approach

1. **Massive method**: Hundreds of lines in one method
2. **Hard to test**: Can't test Excel generation in isolation
3. **Hard to extend**: Adding a new format requires modifying this class
4. **Violates SRP**: One class handles ALL report types AND ALL formats
5. **Violates OCP**: Must modify existing code to add features

## The Strategy Pattern Solution

The Strategy Pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AttendanceExportService                          │
│                       (Orchestrator)                                │
│                                                                     │
│   ┌─────────────────┐                    ┌─────────────────┐        │
│   │  IEnumerable    │                    │  IEnumerable    │        │
│   │ <IReportBuilder>│                    │<IExportGenerator>│       │
│   └────────┬────────┘                    └────────┬────────┘        │
└────────────┼─────────────────────────────────────┼──────────────────┘
             │                                      │
    ┌────────┴────────┐                   ┌────────┴────────┐
    │   STRATEGIES    │                   │   STRATEGIES    │
    └─────────────────┘                   └─────────────────┘

    ┌─────────────────┐                   ┌─────────────────┐
    │AttendanceSummary│                   │  ExcelGenerator │
    │    Builder      │                   │                 │
    ├─────────────────┤                   ├─────────────────┤
    │   LeaveMap      │                   │   CsvGenerator  │
    │    Builder      │                   │                 │
    ├─────────────────┤                   ├─────────────────┤
    │ ScheduledVsActual                   │   PdfGenerator  │
    │    Builder      │                   │                 │
    ├─────────────────┤                   └─────────────────┘
    │EmployeeDetails  │
    │    Builder      │
    ├─────────────────┤
    │   JobReport     │
    │    Builder      │
    ├─────────────────┤
    │    Trends       │
    │    Builder      │
    └─────────────────┘
```

### Key Components

#### 1. Strategy Interfaces

```csharp
// Report building strategy
public interface IReportBuilder
{
    ReportType ReportType { get; }
    Task<ReportData> BuildAsync(ReportBuildContext context);
}

// Export generation strategy
public interface IExportGenerator
{
    ExportFormat Format { get; }
    string ContentType { get; }
    string FileExtension { get; }
    byte[] Generate(ReportData data, ExportOptions options);
}
```

Each interface defines:
- **Identity**: What type/format it handles
- **Contract**: The method signature for its operation

#### 2. Concrete Strategies

Each strategy implements exactly one thing:

```csharp
public class ExcelExportGenerator : IExportGenerator
{
    public ExportFormat Format => ExportFormat.Excel;
    public string ContentType => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
    public string FileExtension => ".xlsx";

    public byte[] Generate(ReportData data, ExportOptions options)
    {
        // ONLY Excel generation logic here
        using var workbook = new XLWorkbook();
        // ... Excel-specific code
        return stream.ToArray();
    }
}
```

#### 3. The Orchestrator (Context)

```csharp
public class AttendanceExportService : IAttendanceExportService
{
    private readonly Dictionary<ReportType, IReportBuilder> _builders;
    private readonly Dictionary<ExportFormat, IExportGenerator> _generators;

    public AttendanceExportService(
        IEnumerable<IReportBuilder> builders,
        IEnumerable<IExportGenerator> generators)
    {
        // Build lookup dictionaries from injected strategies
        _builders = builders.ToDictionary(b => b.ReportType);
        _generators = generators.ToDictionary(g => g.Format);
    }

    public async Task<ExportResult> GenerateReportAsync(ExportRequest request, string companyDatabase)
    {
        // 1. Select the right builder strategy
        if (!_builders.TryGetValue(request.ReportType, out var builder))
            return ExportResult.Failure("Unknown report type");

        // 2. Build the report data
        var reportData = await builder.BuildAsync(context);

        // 3. Select the right generator strategy
        if (!_generators.TryGetValue(request.Format, out var generator))
            return ExportResult.Failure("Unknown format");

        // 4. Generate the output
        var bytes = generator.Generate(reportData, request.Options);

        return new ExportResult(true, fileName, bytes, generator.ContentType, null);
    }
}
```

## SOLID Principles in Action

### Single Responsibility Principle (SRP)

Each class has ONE job:

| Class | Single Responsibility |
|-------|----------------------|
| `AttendanceSummaryBuilder` | Build attendance summary report data |
| `LeaveMapBuilder` | Build leave map report data |
| `ExcelExportGenerator` | Generate Excel files |
| `PdfExportGenerator` | Generate PDF files |
| `AttendanceExportService` | Orchestrate builders and generators |

### Open/Closed Principle (OCP)

**Adding a new report type** (e.g., OvertimeReport):

```csharp
// Just create a new class - NO changes to existing code
public class OvertimeReportBuilder : IReportBuilder
{
    public ReportType ReportType => ReportType.Overtime;

    public async Task<ReportData> BuildAsync(ReportBuildContext context)
    {
        // New report logic here
    }
}
```

Then register it in DI:
```csharp
builder.Services.AddTransient<IReportBuilder, OvertimeReportBuilder>();
```

The orchestrator automatically picks it up - **zero changes to AttendanceExportService**!

**Adding a new format** (e.g., JSON):

```csharp
public class JsonExportGenerator : IExportGenerator
{
    public ExportFormat Format => ExportFormat.Json;
    public string ContentType => "application/json";
    public string FileExtension => ".json";

    public byte[] Generate(ReportData data, ExportOptions options)
    {
        var json = JsonSerializer.Serialize(data);
        return Encoding.UTF8.GetBytes(json);
    }
}
```

### Dependency Inversion Principle (DIP)

The orchestrator depends on abstractions (interfaces), not concrete implementations:

```csharp
// Constructor depends on interfaces
public AttendanceExportService(
    IEnumerable<IReportBuilder> builders,      // Abstraction
    IEnumerable<IExportGenerator> generators   // Abstraction
)
```

This is injected by the DI container, which provides concrete implementations.

### Liskov Substitution Principle (LSP)

Any implementation of `IReportBuilder` can be substituted for another without breaking the system:

```csharp
// These are interchangeable - the orchestrator doesn't care which one it uses
IReportBuilder builder = new AttendanceSummaryBuilder(...);
IReportBuilder builder = new LeaveMapBuilder(...);
IReportBuilder builder = new JobReportBuilder(...);
```

### Interface Segregation Principle (ISP)

Interfaces are small and focused:

```csharp
// IReportBuilder only has what builders need
public interface IReportBuilder
{
    ReportType ReportType { get; }
    Task<ReportData> BuildAsync(ReportBuildContext context);
}

// IExportGenerator only has what generators need
public interface IExportGenerator
{
    ExportFormat Format { get; }
    string ContentType { get; }
    string FileExtension { get; }
    byte[] Generate(ReportData data, ExportOptions options);
}
```

No class is forced to implement methods it doesn't need.

## DI Registration Pattern

```csharp
// Register all strategies
builder.Services.AddTransient<IReportBuilder, AttendanceSummaryBuilder>();
builder.Services.AddTransient<IReportBuilder, LeaveMapBuilder>();
builder.Services.AddTransient<IReportBuilder, ScheduledVsActualBuilder>();
builder.Services.AddTransient<IReportBuilder, EmployeeDetailsBuilder>();
builder.Services.AddTransient<IReportBuilder, JobReportBuilder>();
builder.Services.AddTransient<IReportBuilder, TrendsBuilder>();

builder.Services.AddTransient<IExportGenerator, ExcelExportGenerator>();
builder.Services.AddTransient<IExportGenerator, CsvExportGenerator>();
builder.Services.AddTransient<IExportGenerator, PdfExportGenerator>();

// The orchestrator receives ALL of them via IEnumerable
builder.Services.AddScoped<IAttendanceExportService, AttendanceExportService>();
```

When you register multiple implementations of the same interface, ASP.NET Core's DI container can inject them all as `IEnumerable<T>`.

## Testing Benefits

Each strategy can be tested in complete isolation:

```csharp
[Fact]
public async Task AttendanceSummaryBuilder_Returns_Correct_Sections()
{
    // Arrange
    var mockQueryService = new Mock<IAttendanceQueryService>();
    mockQueryService.Setup(x => x.GetAttendanceStatisticsAsync(...))
        .ReturnsAsync(testStats);

    var builder = new AttendanceSummaryBuilder(mockQueryService.Object);

    // Act
    var result = await builder.BuildAsync(context);

    // Assert
    Assert.Equal("Resumo de Presencas", result.Title);
    Assert.Equal(2, result.Sections.Count);
}

[Fact]
public void ExcelGenerator_Creates_Valid_Workbook()
{
    // Arrange
    var generator = new ExcelExportGenerator();
    var testData = CreateTestReportData();

    // Act
    var bytes = generator.Generate(testData, new ExportOptions(false, false, false));

    // Assert
    using var stream = new MemoryStream(bytes);
    using var workbook = new XLWorkbook(stream);
    Assert.Single(workbook.Worksheets);
}
```

## Common Pattern: Two-Dimensional Strategy

This implementation uses a **two-dimensional strategy pattern**:

1. **First dimension**: Report type (WHAT data to build)
2. **Second dimension**: Export format (HOW to output it)

This creates a matrix of possibilities:

|              | Excel | CSV | PDF |
|--------------|-------|-----|-----|
| Attendance   |   X   |  X  |  X  |
| Leave Map    |   X   |  X  |  X  |
| Scheduled    |   X   |  X  |  X  |
| Employee     |   X   |  X  |  X  |
| Job Report   |   X   |  X  |  X  |
| Trends       |   X   |  X  |  X  |

**6 report types x 3 formats = 18 combinations**, but only **9 classes** (6 builders + 3 generators).

Without the pattern, you'd need 18 separate methods or one massive switch statement.

## Key Takeaways

1. **Strategy Pattern** separates WHAT to do from HOW to do it
2. **DI + IEnumerable** allows automatic strategy discovery
3. **Dictionary lookup** by type/format gives O(1) strategy selection
4. **New features = new classes**, not modifications to existing code
5. **Testing is easy** because each strategy is isolated
6. **SOLID principles** emerge naturally from good pattern use

## Further Reading

- [Refactoring Guru: Strategy Pattern](https://refactoring.guru/design-patterns/strategy)
- [Microsoft DI Documentation](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection)
- CLAUDE.md in this project for service patterns
