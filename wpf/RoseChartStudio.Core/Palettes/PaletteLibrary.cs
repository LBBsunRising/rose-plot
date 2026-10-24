using System.Collections.ObjectModel;
using System.Text.Json;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Palettes;

/// <summary>
/// The built-in v2 palette library (16 palettes across 10 groups), ported from
/// <c>rose/rosechart/palettes.py</c>.
/// </summary>
/// <remarks>
/// <para>
/// The palette data lives in the embedded resource <c>Palettes/palettes.json</c> (generated
/// from the Python module).  This class reproduces the Python module's behaviour:
/// deterministic label -&gt; colour assignment, WCAG-safe label text colours, deterministic
/// palette recommendation and the supporting colour maths (delegated to <see cref="ColorMath"/>).
/// </para>
/// <para>All colours returned by this class are upper-case <c>#RRGGBB</c> strings.</para>
/// </remarks>
public static class PaletteLibrary
{
    /// <summary>Default colour for <c>mode = "single"</c> labels.</summary>
    public const string DefaultLabelColor = ColorMath.DefaultLabelColor;

    /// <summary>Default label background (white).</summary>
    public const string DefaultBackground = ColorMath.DefaultBackground;

    /// <summary>Minimum WCAG contrast a chart label must reach against its background.</summary>
    public const double LabelMinContrast = ColorMath.LabelMinContrast;

    /// <summary>Internal target contrast used when deriving label colours (3.2).</summary>
    public const double LabelTargetContrast = ColorMath.LabelTargetContrast;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = false,
        AllowTrailingCommas = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
    };

    private static readonly string[] GroupOrderArray =
    {
        "原版",
        "商务",
        "科技",
        "莫兰迪",
        "马卡龙",
        "自然",
        "高对比",
        "极简",
        "活力",
        "中国风",
    };

    private static readonly IReadOnlyList<string> GroupOrderReadOnly = Array.AsReadOnly(GroupOrderArray);

    private static readonly Palette[] PalettesArray;
    private static readonly Dictionary<string, Palette> PaletteIndex;

    /// <summary>All built-in palettes, in the canonical (Python <c>PALETTES</c>) order.</summary>
    public static IReadOnlyList<Palette> All { get; }

    /// <summary>Display order of the palette groups (Python <c>GROUP_ORDER</c>).</summary>
    public static IReadOnlyList<string> GroupOrder => GroupOrderReadOnly;

    static PaletteLibrary()
    {
        var palettes = LoadPalettes();
        PalettesArray = palettes.ToArray();
        PaletteIndex = new Dictionary<string, Palette>(StringComparer.Ordinal);
        foreach (var palette in PalettesArray)
        {
            PaletteIndex[palette.Id] = palette;
        }

        All = Array.AsReadOnly(PalettesArray);
    }

    // ---------------------------------------------------------------------
    // Lookup
    // ---------------------------------------------------------------------

    /// <summary>
    /// Looks a palette up by id (case-insensitive, surrounding whitespace ignored).
    /// </summary>
    /// <exception cref="KeyNotFoundException">No palette has that id.</exception>
    public static Palette ById(string id)
    {
        if (id is null)
        {
            throw new ArgumentNullException(nameof(id));
        }

        var key = id.Trim().ToLowerInvariant();
        if (!PaletteIndex.TryGetValue(key, out var palette))
        {
            var available = string.Join(", ", PalettesArray.Select(item => item.Id));
            throw new KeyNotFoundException($"未知色板 id：'{id}'；可用 id：{available}");
        }

        return palette;
    }

    /// <summary>
    /// Returns the palettes of one group (in canonical order), or <see cref="All"/> when
    /// <paramref name="group"/> is <see langword="null"/>.
    /// </summary>
    public static IReadOnlyList<Palette> ByGroup(string? group)
    {
        if (group is null)
        {
            return All;
        }

        var matches = new List<Palette>();
        foreach (var palette in PalettesArray)
        {
            if (string.Equals(palette.Group, group, StringComparison.Ordinal))
            {
                matches.Add(palette);
            }
        }

        return Array.AsReadOnly(matches.ToArray());
    }

    /// <summary>Groups and their palettes, ordered by <see cref="GroupOrder"/>.</summary>
    public static IReadOnlyDictionary<string, IReadOnlyList<Palette>> ByGroupMap()
    {
        var grouped = new Dictionary<string, List<Palette>>(StringComparer.Ordinal);
        foreach (var palette in PalettesArray)
        {
            if (!grouped.TryGetValue(palette.Group, out var list))
            {
                list = new List<Palette>();
                grouped[palette.Group] = list;
            }

            list.Add(palette);
        }

        var ordered = new Dictionary<string, IReadOnlyList<Palette>>(StringComparer.Ordinal);
        foreach (var group in GroupOrderArray)
        {
            if (grouped.Remove(group, out var list))
            {
                ordered[group] = Array.AsReadOnly(list.ToArray());
            }
        }

        // Unknown groups (not part of GROUP_ORDER) are appended in ordinal order,
        // mirroring Python's palettes_by_group().
        foreach (var group in grouped.Keys.OrderBy(item => item, StringComparer.Ordinal))
        {
            ordered[group] = Array.AsReadOnly(grouped[group].ToArray());
        }

        return new ReadOnlyDictionary<string, IReadOnlyList<Palette>>(ordered);
    }

    // ---------------------------------------------------------------------
    // Label -> colour assignment
    // ---------------------------------------------------------------------

    /// <summary>
    /// Deterministically maps <paramref name="labels"/> to palette colours.
    /// Priority: <paramref name="overrides"/> (only labels that occur) &gt;
    /// <c>palette.NamedColors</c> &gt; cycling through <c>palette.Colors</c> in order.
    /// Duplicate labels keep their first position; named/override labels do not consume
    /// a cycle index (this preserves the exact legacy mappings).
    /// </summary>
    public static Dictionary<string, string> AssignColors(
        Palette palette,
        IReadOnlyList<string> labels,
        IReadOnlyDictionary<string, string>? overrides = null)
    {
        if (palette is null)
        {
            throw new ArgumentNullException(nameof(palette));
        }

        if (labels is null)
        {
            throw new ArgumentNullException(nameof(labels));
        }

        var colors = palette.Colors;
        if (colors.Count == 0)
        {
            throw new ArgumentException($"色板 '{palette.Id}' 没有颜色", nameof(palette));
        }

        Dictionary<string, string>? normalizedOverrides = null;
        if (overrides is { Count: > 0 })
        {
            normalizedOverrides = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var pair in overrides)
            {
                normalizedOverrides[pair.Key] = ColorMath.NormalizeHex(pair.Value);
            }
        }

        var named = palette.NamedColors;
        var assignment = new Dictionary<string, string>(StringComparer.Ordinal);
        var cycleIndex = 0;
        foreach (var label in labels)
        {
            if (assignment.ContainsKey(label))
            {
                continue;
            }

            if (normalizedOverrides is not null && normalizedOverrides.TryGetValue(label, out var overrideColor))
            {
                assignment[label] = overrideColor;
                continue;
            }

            if (named is not null && named.TryGetValue(label, out var namedColor))
            {
                assignment[label] = namedColor;
                continue;
            }

            assignment[label] = colors[cycleIndex % colors.Count];
            cycleIndex++;
        }

        return assignment;
    }

    // ---------------------------------------------------------------------
    // Label text colour
    // ---------------------------------------------------------------------

    /// <summary>
    /// Returns the colour chart label text should use for a given sector fill.
    /// </summary>
    /// <param name="fillHex">Sector fill colour.</param>
    /// <param name="mode">"auto" (default), "match" (label = fill) or "single" (use <paramref name="singleColor"/>).</param>
    /// <param name="singleColor">Colour used when <paramref name="mode"/> is "single".</param>
    /// <param name="background">Background the label is drawn on (defaults to white).</param>
    /// <remarks>
    /// In "auto" mode the fill colour is kept when it already reaches a WCAG contrast of
    /// 3.0 against <paramref name="background"/>; otherwise the colour is nudged darker or
    /// lighter along its hue until it reaches the internal 3.2 target (minimum 3.0).
    /// </remarks>
    public static string LabelColor(
        string fillHex,
        string mode = "auto",
        string singleColor = DefaultLabelColor,
        string background = DefaultBackground)
    {
        var fill = ColorMath.NormalizeHex(fillHex);
        if (mode is null)
        {
            throw new ArgumentNullException(nameof(mode));
        }

        var normalizedMode = mode.Trim().ToLowerInvariant();

        if (normalizedMode == "match")
        {
            return fill;
        }

        if (normalizedMode == "single")
        {
            return ColorMath.NormalizeHex(singleColor);
        }

        if (normalizedMode != "auto")
        {
            throw new ArgumentException(
                $"不支持的标签颜色模式：'{mode}'（可选 auto / match / single）", nameof(mode));
        }

        var backgroundHex = ColorMath.NormalizeHex(background);
        if (ColorMath.ContrastRatio(fill, backgroundHex) >= LabelMinContrast)
        {
            return fill;
        }

        var (hue, saturation, lightness) = ColorMath.RgbToHsl(fill);
        var darker = FindLabelLightness(hue, saturation, lightness, -1.0, backgroundHex);
        var lighter = FindLabelLightness(hue, saturation, lightness, 1.0, backgroundHex);

        var candidates = new List<(double Delta, string Color)>(2);
        if (darker is { } darkerCandidate)
        {
            candidates.Add(darkerCandidate);
        }

        if (lighter is { } lighterCandidate)
        {
            candidates.Add(lighterCandidate);
        }

        if (candidates.Count > 0)
        {
            if (candidates.Count == 2
                && Math.Abs(candidates[0].Delta - candidates[1].Delta) < 1e-9
                && ColorMath.Luminance(backgroundHex) >= 0.5)
            {
                return candidates[0].Color;
            }

            var best = candidates[0];
            for (var index = 1; index < candidates.Count; index++)
            {
                if (candidates[index].Delta < best.Delta)
                {
                    best = candidates[index];
                }
            }

            return best.Color;
        }

        // Extreme background fallback: pick whichever of black/white contrasts more.
        var blackRatio = ColorMath.ContrastRatio("#000000", backgroundHex);
        var whiteRatio = ColorMath.ContrastRatio("#FFFFFF", backgroundHex);
        return blackRatio >= whiteRatio ? "#000000" : "#FFFFFF";
    }

    private static (double Delta, string Color)? FindLabelLightness(
        double hue,
        double saturation,
        double lightness,
        double direction,
        string background)
    {
        (double Delta, string Color)? fallback = null;
        for (var step = 1; step <= 250; step++)
        {
            var delta = step * (1.0 / 250.0);
            var target = lightness + direction * delta;
            if (target < 0.0 || target > 1.0)
            {
                break;
            }

            var candidate = ColorMath.HslToHex(hue, saturation, target);
            var ratio = ColorMath.ContrastRatio(candidate, background);
            if (ratio >= LabelTargetContrast)
            {
                return (delta, candidate);
            }

            if (ratio >= LabelMinContrast && fallback is null)
            {
                fallback = (delta, candidate);
            }
        }

        return fallback;
    }

    // ---------------------------------------------------------------------
    // Palette recommendation
    // ---------------------------------------------------------------------

    /// <summary>
    /// Recommends the <paramref name="limit"/> most suitable palettes for a chart with
    /// <paramref name="labelCount"/> labels.  The ranking is fully deterministic: distinctness
    /// (42%), visibility against the background (34%) and colour capacity (24%), rounded to
    /// 6 decimals and tie-broken by palette id.
    /// </summary>
    /// <exception cref="ArgumentOutOfRangeException"><paramref name="labelCount"/> is below 1 (when limit &gt;= 1).</exception>
    public static IReadOnlyList<Palette> Recommend(
        int labelCount,
        int limit = 4,
        string background = DefaultBackground)
    {
        if (limit < 1)
        {
            return Array.Empty<Palette>();
        }

        var scored = PaletteScores(labelCount, background);
        var take = Math.Min(limit, scored.Count);
        var result = new Palette[take];
        for (var index = 0; index < take; index++)
        {
            result[index] = scored[index].Palette;
        }

        return Array.AsReadOnly(result);
    }

    /// <summary>All palettes with their recommendation score for <paramref name="labelCount"/>, best first.</summary>
    public static IReadOnlyList<(Palette Palette, double Score)> PaletteScores(
        int labelCount,
        string background = DefaultBackground)
    {
        if (labelCount < 1)
        {
            throw new ArgumentOutOfRangeException(
                nameof(labelCount), labelCount, "标签数量必须 >= 1");
        }

        var backgroundHex = ColorMath.NormalizeHex(background);
        var scored = new List<(Palette Palette, double Score)>(PalettesArray.Length);
        foreach (var palette in PalettesArray)
        {
            scored.Add((palette, RecommendScore(palette, labelCount, backgroundHex)));
        }

        scored.Sort(static (left, right) =>
        {
            // Python: sort(key=lambda item: (-round(score, 6), palette.id))
            var leftScore = Math.Round(left.Score, 6, MidpointRounding.ToEven);
            var rightScore = Math.Round(right.Score, 6, MidpointRounding.ToEven);
            var byScore = rightScore.CompareTo(leftScore);
            return byScore != 0
                ? byScore
                : string.CompareOrdinal(left.Palette.Id, right.Palette.Id);
        });

        return Array.AsReadOnly(scored.ToArray());
    }

    private static double RecommendScore(Palette palette, int labelCount, string backgroundHex)
    {
        var colors = EffectiveColors(palette, labelCount);
        var uniqueCount = new HashSet<string>(colors, StringComparer.Ordinal).Count;

        double distinct;
        if (labelCount == 1)
        {
            distinct = 0.85;
        }
        else if (uniqueCount < labelCount)
        {
            // Not enough colours: distinctness is discounted by the shortfall ratio.
            distinct = 0.30 * ((double)uniqueCount / labelCount);
        }
        else
        {
            var minDistance = double.PositiveInfinity;
            double sumDistance = 0.0;
            var pairCount = 0;
            for (var first = 0; first < labelCount; first++)
            {
                for (var second = first + 1; second < labelCount; second++)
                {
                    var distance = ColorMath.DeltaE(colors[first], colors[second]);
                    if (distance < minDistance)
                    {
                        minDistance = distance;
                    }

                    sumDistance += distance;
                    pairCount++;
                }
            }

            var meanDistance = sumDistance / pairCount;
            distinct = 0.55 * Math.Min(minDistance / 18.0, 1.0)
                       + 0.45 * Math.Min(meanDistance / 40.0, 1.0);
        }

        var visibilitySum = 0.0;
        foreach (var color in colors)
        {
            visibilitySum += Math.Min(ColorMath.ContrastRatio(color, backgroundHex) / 3.0, 1.0);
        }

        var visibility = visibilitySum / colors.Count;

        var capacity = palette.Colors.Count;
        var sizeFit = capacity >= labelCount ? 1.0 : (double)capacity / labelCount;

        return 0.42 * distinct + 0.34 * visibility + 0.24 * sizeFit;
    }

    private static IReadOnlyList<string> EffectiveColors(Palette palette, int labelCount)
    {
        var colors = palette.Colors;
        var effective = new string[labelCount];
        for (var index = 0; index < labelCount; index++)
        {
            effective[index] = colors[index % colors.Count];
        }

        return effective;
    }

    // ---------------------------------------------------------------------
    // Colour maths (delegating to ColorMath; kept here as part of the v2 API contract)
    // ---------------------------------------------------------------------

    /// <summary>WCAG contrast ratio between two colours (1.0-21.0).</summary>
    public static double ContrastRatio(string colorA, string colorB) => ColorMath.ContrastRatio(colorA, colorB);

    /// <summary>WCAG relative luminance of a colour (0.0-1.0).</summary>
    public static double Luminance(string hex) => ColorMath.Luminance(hex);

    /// <summary>Normalises a colour to upper-case <c>#RRGGBB</c>.</summary>
    public static string NormalizeHex(string hex) => ColorMath.NormalizeHex(hex);

    /// <summary><c>#RRGGBB</c> -&gt; <c>(r, g, b)</c>, each channel 0-255.</summary>
    public static (int R, int G, int B) HexToRgb(string hex) => ColorMath.HexToRgb(hex);

    /// <summary><c>(r, g, b)</c> -&gt; <c>#RRGGBB</c>; channels rounded and clamped to 0-255.</summary>
    public static string RgbToHex(double red, double green, double blue) =>
        ColorMath.RgbToHex(red, green, blue);

    /// <summary>Mixes two colours in linear-light space (0 -&gt; a, 1 -&gt; b).</summary>
    public static string MixColors(string colorA, string colorB, double weight = 0.5) =>
        ColorMath.MixColors(colorA, colorB, weight);

    /// <summary>Darkens a colour by lowering its HSL lightness by <paramref name="amount"/>.</summary>
    public static string Darken(string hex, double amount = 0.15) => ColorMath.Darken(hex, amount);

    /// <summary>Lightens a colour by raising its HSL lightness towards 1.0 by <paramref name="amount"/>.</summary>
    public static string Lighten(string hex, double amount = 0.15) => ColorMath.Lighten(hex, amount);

    /// <summary><c>#RRGGBB</c> -&gt; <c>(hue degrees, saturation, lightness)</c>.</summary>
    public static (double Hue, double Saturation, double Lightness) RgbToHsl(string hex) =>
        ColorMath.RgbToHsl(hex);

    /// <summary><c>(hue degrees, saturation, lightness)</c> -&gt; <c>#RRGGBB</c>.</summary>
    public static string HslToHex(double hue, double saturation, double lightness) =>
        ColorMath.HslToHex(hue, saturation, lightness);

    /// <summary>CIELAB delta-E76 colour distance.</summary>
    public static double DeltaE(string colorA, string colorB) => ColorMath.DeltaE(colorA, colorB);

    // ---------------------------------------------------------------------
    // Embedded JSON loading
    // ---------------------------------------------------------------------

    private static List<Palette> LoadPalettes()
    {
        var assembly = typeof(PaletteLibrary).Assembly;
        string? resourceName = null;
        foreach (var name in assembly.GetManifestResourceNames())
        {
            if (name.EndsWith("palettes.json", StringComparison.Ordinal))
            {
                resourceName = name;
                break;
            }
        }

        if (resourceName is null)
        {
            throw new InvalidOperationException(
                "找不到内嵌资源 palettes.json（Core 项目应把 Palettes/palettes.json 标记为 EmbeddedResource）");
        }

        using var stream = assembly.GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException($"无法读取内嵌资源 {resourceName}");

        List<Dictionary<string, JsonElement>>? rows;
        try
        {
            rows = JsonSerializer.Deserialize<List<Dictionary<string, JsonElement>>>(stream, JsonOptions);
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException("内嵌资源 palettes.json 解析失败", exception);
        }

        if (rows is null || rows.Count == 0)
        {
            throw new InvalidOperationException("内嵌资源 palettes.json 为空");
        }

        var palettes = new List<Palette>(rows.Count);
        foreach (var row in rows)
        {
            palettes.Add(ToPalette(row));
        }

        return palettes;
    }

    private static Palette ToPalette(IReadOnlyDictionary<string, JsonElement> row)
    {
        var id = RequireText(ReadString(row, "id"), "id", null);
        var name = RequireText(ReadString(row, "name"), "name", id);
        var group = RequireText(ReadString(row, "group"), "group", id);

        if (!row.TryGetValue("colors", out var colorsElement) || colorsElement.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidDataException($"Palette('{id}').colors 必须是数组");
        }

        var colors = new List<string>();
        foreach (var colorElement in colorsElement.EnumerateArray())
        {
            var raw = colorElement.ValueKind == JsonValueKind.String ? colorElement.GetString() : null;
            if (raw is null)
            {
                throw new InvalidDataException($"Palette('{id}').colors 含有非字符串颜色");
            }

            colors.Add(NormalizeColorOrThrow(raw, id, "colors"));
        }

        if (colors.Count == 0)
        {
            throw new InvalidDataException($"Palette('{id}').colors 不能为空");
        }

        var tags = new List<string>();
        if (row.TryGetValue("tags", out var tagsElement) && tagsElement.ValueKind == JsonValueKind.Array)
        {
            foreach (var tagElement in tagsElement.EnumerateArray())
            {
                tags.Add(tagElement.ValueKind == JsonValueKind.String
                    ? tagElement.GetString() ?? string.Empty
                    : string.Empty);
            }
        }

        IReadOnlyDictionary<string, string>? namedColors = null;
        if (row.TryGetValue("namedColors", out var namedElement)
            && namedElement.ValueKind == JsonValueKind.Object)
        {
            var named = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var property in namedElement.EnumerateObject())
            {
                var raw = property.Value.ValueKind == JsonValueKind.String
                    ? property.Value.GetString()
                    : null;
                if (raw is null)
                {
                    throw new InvalidDataException($"Palette('{id}').namedColors 含有非法颜色");
                }

                named[property.Name] = NormalizeColorOrThrow(raw, id, "namedColors");
            }

            namedColors = new ReadOnlyDictionary<string, string>(named);
        }

        return new Palette
        {
            Id = id,
            Name = name,
            Group = group,
            Colors = Array.AsReadOnly(colors.ToArray()),
            Tags = Array.AsReadOnly(tags.ToArray()),
            Description = ReadString(row, "description") ?? string.Empty,
            NamedColors = namedColors,
        };
    }

    private static string? ReadString(IReadOnlyDictionary<string, JsonElement> row, string property)
    {
        if (!row.TryGetValue(property, out var element) || element.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        return element.ValueKind == JsonValueKind.String ? element.GetString() : null;
    }

    private static string RequireText(string? value, string field, string? paletteId)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidDataException(paletteId is null
                ? $"palettes.json 的 {field} 必须是非空字符串"
                : $"Palette('{paletteId}').{field} 必须是非空字符串");
        }

        return value;
    }

    private static string NormalizeColorOrThrow(string? value, string paletteId, string field)
    {
        try
        {
            return ColorMath.NormalizeHex(value!);
        }
        catch (ArgumentException exception)
        {
            throw new InvalidDataException(
                $"Palette('{paletteId}').{field} 含有非法颜色：'{value}'", exception);
        }
    }
}
