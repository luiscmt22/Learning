using LearningWebbook.Maui.Models;
using Microsoft.JSInterop;

namespace LearningWebbook.Maui.Services;

public class ThemeService
{
    private readonly IJSRuntime _js;
    private const string PrefsKey = "wb-theme";

    public ThemeOption CurrentTheme { get; private set; }

    public ThemeService(IJSRuntime js)
    {
        _js = js;
        var saved = Preferences.Default.Get(PrefsKey, "dark");
        CurrentTheme = saved switch
        {
            "light" => ThemeOption.Light,
            "warm" => ThemeOption.Warm,
            _ => ThemeOption.Dark,
        };
    }

    public async Task SetThemeAsync(ThemeOption theme)
    {
        CurrentTheme = theme;
        var name = theme.ToString().ToLowerInvariant();
        Preferences.Default.Set(PrefsKey, name);
        await _js.InvokeVoidAsync("themeInterop.setTheme", name);
        OnThemeChanged?.Invoke();
    }

    public async Task ApplyCurrentThemeAsync()
    {
        var name = CurrentTheme.ToString().ToLowerInvariant();
        await _js.InvokeVoidAsync("themeInterop.setTheme", name);
    }

    public event Action? OnThemeChanged;
}
