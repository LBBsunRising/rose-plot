namespace RoseChartStudio.Core.Models;

/// <summary>A named chart palette (16 built-in palettes ported from the v2 engine).</summary>
public sealed class Palette
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Group { get; init; }
    public required IReadOnlyList<string> Colors { get; init; }
    public IReadOnlyList<string> Tags { get; init; } = Array.Empty<string>();
    public string Description { get; init; } = "";
    /// <summary>Optional fixed label -> color mapping (used by the legacy palettes).</summary>
    public IReadOnlyDictionary<string, string>? NamedColors { get; init; }

    public override string ToString() => $"{Id} ({Name})";
}
