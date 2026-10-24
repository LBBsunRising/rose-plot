using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using RoseChartStudio.App.Models;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.App.Services;

/// <summary>Portable persisted state (settings + last project), mirroring v2 prefs.</summary>
public sealed class AppSettingsDocument
{
    public int Version { get; set; } = 4;
    public string? File { get; set; }
    public string? Sheet { get; set; }
    public string? ActiveChartColumn { get; set; }
    public List<ChartStateDto> Charts { get; set; } = new();
    public WindowSettings Window { get; set; } = new();
    public ChartStyle Style { get; set; } = new();
    public ExportSettings Export { get; set; } = new();
    public List<string> RecentFiles { get; set; } = new();

    // v3 compatibility (read-only migration): the old fixed project/status charts.
    public string? CategoryColumn { get; set; }
    public string? StatusColumn { get; set; }
    public ChartStateDto? Chart1 { get; set; }
    public ChartStateDto? Chart2 { get; set; }
    public string? ActiveChart { get; set; }
}

public sealed class WindowSettings
{
    public double Width { get; set; } = 1520;
    public double Height { get; set; } = 940;
    public bool Maximized { get; set; }
}

public sealed class ChartStateDto
{
    public string Column { get; set; } = "";
    public string Name { get; set; } = "";
    public string Title { get; set; } = "";
    public string Subtitle { get; set; } = "";
    public string PaletteId { get; set; } = "legacy_project";
    public string LabelMode { get; set; } = "auto";
    public string LabelSingleColor { get; set; } = "#334155";
    public string SortMode { get; set; } = "count_desc";
    public Dictionary<string, string> Overrides { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string, LayoutOffset> Layout { get; set; } = new(StringComparer.Ordinal);
}

public sealed class SettingsService
{
    private const string FileName = "rosechart_settings.json";
    private readonly JsonSerializerOptions _options = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };

    public string SettingsPath { get; private set; } = "";

    public AppSettingsDocument Load()
    {
        foreach (var candidate in CandidatePaths())
        {
            try
            {
                if (!File.Exists(candidate))
                {
                    continue;
                }
                var json = File.ReadAllText(candidate);
                var document = JsonSerializer.Deserialize<AppSettingsDocument>(json, _options);
                if (document is not null)
                {
                    SettingsPath = candidate;
                    return document;
                }
            }
            catch
            {
                // A broken settings file must never prevent the app from starting.
            }
        }
        SettingsPath = ResolveWritablePath();
        return new AppSettingsDocument();
    }

    public void Save(AppSettingsDocument document)
    {
        try
        {
            SettingsPath = ResolveWritablePath();
            Directory.CreateDirectory(Path.GetDirectoryName(SettingsPath) ?? AppContext.BaseDirectory);
            var json = JsonSerializer.Serialize(document, _options);
            File.WriteAllText(SettingsPath, json);
        }
        catch
        {
            // Persistence is best-effort; never crash the app on close.
        }
    }

    private static string ResolveWritablePath()
    {
        var portable = Path.Combine(AppContext.BaseDirectory, FileName);
        try
        {
            var probe = portable + ".probe";
            File.WriteAllText(probe, "probe");
            File.Delete(probe);
            return portable;
        }
        catch
        {
            var local = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "RoseChartStudio");
            Directory.CreateDirectory(local);
            return Path.Combine(local, FileName);
        }
    }

    private static IEnumerable<string> CandidatePaths()
    {
        yield return Path.Combine(AppContext.BaseDirectory, FileName);
        yield return Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "RoseChartStudio",
            FileName);
    }
}
