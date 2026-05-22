using System.Text.RegularExpressions;
using LearningWebbook.Maui.Models;

namespace LearningWebbook.Maui.Services;

public partial class SearchService
{
    public List<Topic> Search(IEnumerable<Topic> allTopics, string query)
    {
        if (string.IsNullOrWhiteSpace(query))
            return allTopics.ToList();

        var q = query.Trim().ToLowerInvariant();

        return allTopics.Where(t =>
            t.Title.Contains(q, StringComparison.OrdinalIgnoreCase) ||
            t.Prerequisites.Contains(q, StringComparison.OrdinalIgnoreCase) ||
            StripHtml(t.ContentHtml).Contains(q, StringComparison.OrdinalIgnoreCase)
        ).ToList();
    }

    private static string StripHtml(string html)
    {
        if (string.IsNullOrEmpty(html)) return "";
        return HtmlTagRegex().Replace(html, " ");
    }

    [GeneratedRegex("<[^>]+>")]
    private static partial Regex HtmlTagRegex();
}
