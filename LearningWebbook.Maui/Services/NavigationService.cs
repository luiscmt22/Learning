namespace LearningWebbook.Maui.Services;

public class NavigationService
{
    public event Action<string>? OnTopicRequested;

    public void RequestTopic(string topicId)
    {
        OnTopicRequested?.Invoke(topicId);
    }
}
