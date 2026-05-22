using System.Text.Json.Serialization;

namespace LearningWebbook.Maui.Models;

public class WebookData
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("subtitle")]
    public string Subtitle { get; set; } = "";

    [JsonPropertyName("totalTopics")]
    public int TotalTopics { get; set; }

    [JsonPropertyName("totalPhases")]
    public int TotalPhases { get; set; }

    [JsonPropertyName("phases")]
    public List<Phase> Phases { get; set; } = [];
}

public class Phase
{
    [JsonPropertyName("number")]
    public int Number { get; set; }

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("subtitle")]
    public string Subtitle { get; set; } = "";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";

    [JsonPropertyName("topics")]
    public List<Topic> Topics { get; set; } = [];
}

public class Topic
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("phase")]
    public int Phase { get; set; }

    [JsonPropertyName("level")]
    public string Level { get; set; } = "";

    [JsonPropertyName("prereqs")]
    public string Prerequisites { get; set; } = "";

    [JsonPropertyName("contentHtml")]
    public string ContentHtml { get; set; } = "";

    [JsonPropertyName("forDummiesHtml")]
    public string? ForDummiesHtml { get; set; }

    [JsonPropertyName("nextTopicId")]
    public string? NextTopicId { get; set; }

    [JsonPropertyName("nextTopicTitle")]
    public string? NextTopicTitle { get; set; }
}

public enum ThemeOption
{
    Dark,
    Light,
    Warm
}
