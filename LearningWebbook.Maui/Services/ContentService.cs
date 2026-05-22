using System.Reflection;
using System.Text.Json;
using LearningWebbook.Maui.Models;

namespace LearningWebbook.Maui.Services;

public class ContentService
{
    private WebookData? _data;

    public async Task<WebookData> GetDataAsync()
    {
        if (_data is not null)
            return _data;

        var assembly = Assembly.GetExecutingAssembly();
        var resourceName = "LearningWebbook.Maui.Content.topics.json";

        using var stream = assembly.GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException($"Could not find embedded resource: {resourceName}");

        _data = await JsonSerializer.DeserializeAsync<WebookData>(stream)
            ?? throw new InvalidOperationException("Failed to deserialize topics.json");

        return _data;
    }

    public async Task<List<Phase>> GetPhasesAsync()
    {
        var data = await GetDataAsync();
        return data.Phases;
    }

    public async Task<Topic?> GetTopicAsync(string topicId)
    {
        var data = await GetDataAsync();
        return data.Phases
            .SelectMany(p => p.Topics)
            .FirstOrDefault(t => t.Id == topicId);
    }

    public async Task<int> GetTotalTopicsAsync()
    {
        var data = await GetDataAsync();
        return data.TotalTopics;
    }
}
