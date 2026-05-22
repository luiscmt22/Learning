using System.Text.Json;

namespace LearningWebbook.Maui.Services;

public class ProgressService
{
    private const string PrefsKey = "wb-progress";
    private HashSet<string> _readTopics = [];

    public ProgressService()
    {
        Load();
    }

    private void Load()
    {
        var json = Preferences.Default.Get(PrefsKey, "[]");
        try
        {
            var list = JsonSerializer.Deserialize<List<string>>(json) ?? [];
            _readTopics = [.. list];
        }
        catch
        {
            _readTopics = [];
        }
    }

    private void Save()
    {
        var json = JsonSerializer.Serialize(_readTopics.ToList());
        Preferences.Default.Set(PrefsKey, json);
    }

    public bool IsRead(string topicId) => _readTopics.Contains(topicId);

    public void MarkRead(string topicId)
    {
        if (_readTopics.Add(topicId))
        {
            Save();
            OnProgressChanged?.Invoke();
        }
    }

    public int ReadCount => _readTopics.Count;

    public double GetPercentage(int totalTopics)
        => totalTopics > 0 ? Math.Round((double)_readTopics.Count / totalTopics * 100) : 0;

    public int GetPhaseReadCount(IEnumerable<Models.Topic> topics)
        => topics.Count(t => _readTopics.Contains(t.Id));

    public event Action? OnProgressChanged;
}
