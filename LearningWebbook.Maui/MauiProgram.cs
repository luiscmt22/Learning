using LearningWebbook.Maui.Services;
using Microsoft.Extensions.Logging;

namespace LearningWebbook.Maui;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        builder
            .UseMauiApp<App>()
            .ConfigureFonts(fonts =>
            {
                fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
            });

        builder.Services.AddMauiBlazorWebView();

        // Services
        builder.Services.AddSingleton<ContentService>();
        builder.Services.AddSingleton<ProgressService>();
        builder.Services.AddScoped<ThemeService>();
        builder.Services.AddSingleton<SearchService>();
        builder.Services.AddSingleton<NavigationService>();

#if DEBUG
        builder.Services.AddBlazorWebViewDeveloperTools();
        builder.Logging.AddDebug();
#endif

        return builder.Build();
    }
}
