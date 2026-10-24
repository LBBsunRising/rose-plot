using System.Text.RegularExpressions;
using RoseChartStudio.Core.Models;
using RoseChartStudio.Core.Palettes;

namespace RoseChartStudio.Tests;

/// <summary>
/// Regression tests for the v2 palette library port.  The expected values in this file were
/// produced by running <c>rose\rosechart\palettes.py</c> with the bundled Python 3.11
/// (<c>rose\.venv\python.exe</c>), so a green run proves the C# port reproduces the Python
/// behaviour (including its exact HSL / LAB / banker-rounding results).
/// </summary>
public sealed class PaletteLibraryTests
{
    private static readonly string[] ExpectedIds =
    {
        "legacy_project",
        "legacy_status",
        "business_steel",
        "business_forest",
        "tech_neon",
        "tech_deep",
        "morandi_dusk",
        "macaron_pastel",
        "macaron_berry",
        "nature_forest",
        "nature_ocean",
        "high_contrast",
        "minimal_graphite",
        "vibrant_candy",
        "chinese_vermilion",
        "chinese_ink",
    };

    private static readonly string[] ExpectedGroups =
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

    private static readonly Regex HexPattern = new("^#[0-9A-F]{6}$", RegexOptions.CultureInvariant);
    private static readonly Regex IdPattern = new("^[a-z][a-z0-9_]*$", RegexOptions.CultureInvariant);

    private static readonly IReadOnlyDictionary<string, int> ExpectedGroupCounts = new Dictionary<string, int>
    {
        ["原版"] = 2,
        ["商务"] = 2,
        ["科技"] = 2,
        ["莫兰迪"] = 1,
        ["马卡龙"] = 2,
        ["自然"] = 2,
        ["高对比"] = 1,
        ["极简"] = 1,
        ["活力"] = 1,
        ["中国风"] = 2,
    };

    /// <summary>Python: label_color(color, "auto", background="#FFFFFF") for every palette color.</summary>
    private static readonly IReadOnlyDictionary<string, string[]> ExpectedAutoLabelOnWhite = new Dictionary<string, string[]>
    {
        ["legacy_project"] = new[] { "#009F9F", "#CB6AD3", "#9E9019", "#8F8F8F" },
        ["legacy_status"] = new[] { "#9B9100", "#9B8C89", "#D54660", "#DA435C" },
        ["business_steel"] = new[] { "#17324D", "#24547E", "#3B7DB3", "#5095C9", "#5095CA", "#4F96C9", "#7C8B99" },
        ["business_forest"] = new[] { "#173B35", "#245C50", "#3C8576", "#579C8B", "#579C8B", "#569C83", "#8C7A5B" },
        ["tech_neon"] = new[] { "#0B1F3A", "#1B6CFF", "#009BCC", "#00A288", "#8B5CF6", "#FF4D8D", "#BE8500" },
        ["tech_deep"] = new[] { "#101A33", "#1E3A5F", "#2E5F8A", "#3F8FC4", "#1F9ACA", "#1D9BC3", "#4B4E6D" },
        ["morandi_dusk"] = new[] { "#6F6A66", "#8E8A85", "#958E84", "#9F8B81", "#7F9399", "#84919E", "#9E8C7D" },
        ["macaron_pastel"] = new[] { "#ED5D81", "#D8760B", "#B38A0A", "#37A25B", "#349CA2", "#6390DB", "#A57ADD" },
        ["macaron_berry"] = new[] { "#E36A8C", "#EC6082", "#EC663F", "#BF8318", "#499E8D", "#7C8CCE", "#A082C3" },
        ["nature_forest"] = new[] { "#2F5D3A", "#4E7C49", "#769957", "#759B49", "#839836", "#AB8A4D", "#6B5B4B" },
        ["nature_ocean"] = new[] { "#1F6F78", "#2E9CA6", "#359EA1", "#3C9D9C", "#589C89", "#B78736", "#5C8374" },
        ["high_contrast"] = new[] { "#D7263D", "#F46036", "#CF7B0E", "#2E86AB", "#1B998B", "#3D348B", "#111111" },
        ["minimal_graphite"] = new[] { "#111827", "#374151", "#6B7280", "#88909F", "#8590A0", "#8590A4", "#0F766E" },
        ["vibrant_candy"] = new[] { "#EF476F", "#D27900", "#BE8500", "#05A279", "#118AB2", "#7B2CBF", "#3A86FF" },
        ["chinese_vermilion"] = new[] { "#9D2933", "#C3272B", "#C68017", "#2A8E7F", "#177CB0", "#425066", "#3F9AAB" },
        ["chinese_ink"] = new[] { "#1C1C1C", "#3D3D3D", "#5F6F65", "#7A8B8F", "#83957A", "#A68A6F", "#8B2F2F" },
    };

    /// <summary>Python: recommend_palettes(n, limit=4) — palette ids, best first.</summary>
    private static readonly IReadOnlyDictionary<int, string[]> ExpectedRecommendTop4 = new Dictionary<int, string[]>
    {
        [1] = new[] { "business_forest", "business_steel", "chinese_ink", "chinese_vermilion" },
        [2] = new[] { "tech_neon", "vibrant_candy", "high_contrast", "chinese_vermilion" },
        [3] = new[] { "chinese_vermilion", "tech_neon", "high_contrast", "minimal_graphite" },
        [4] = new[] { "chinese_vermilion", "high_contrast", "minimal_graphite", "tech_neon" },
        [5] = new[] { "chinese_vermilion", "high_contrast", "minimal_graphite", "tech_neon" },
        [6] = new[] { "chinese_vermilion", "high_contrast", "tech_neon", "vibrant_candy" },
        [7] = new[] { "high_contrast", "chinese_vermilion", "vibrant_candy", "tech_neon" },
        [8] = new[] { "high_contrast", "chinese_ink", "tech_deep", "chinese_vermilion" },
        [9] = new[] { "high_contrast", "chinese_ink", "tech_deep", "chinese_vermilion" },
        [10] = new[] { "high_contrast", "chinese_ink", "tech_deep", "business_forest" },
    };

    /// <summary>Python: [p.id for p, s in palette_scores(3)].</summary>
    private static readonly string[] ExpectedScoresOrderForThreeLabels =
    {
        "chinese_vermilion", "tech_neon", "high_contrast", "minimal_graphite", "vibrant_candy",
        "business_steel", "chinese_ink", "legacy_status", "tech_deep", "business_forest",
        "nature_forest", "macaron_pastel", "nature_ocean", "legacy_project", "macaron_berry",
        "morandi_dusk",
    };

    // ---------------------------------------------------------------------
    // Library contents
    // ---------------------------------------------------------------------

    [Fact]
    public void AllPalettesLoadedInCanonicalOrder()
    {
        Assert.Equal(16, PaletteLibrary.All.Count);
        Assert.Equal(ExpectedIds, PaletteLibrary.All.Select(palette => palette.Id));
        Assert.Equal(16, PaletteLibrary.All.Select(palette => palette.Id).Distinct().Count());

        Assert.Equal(10, PaletteLibrary.GroupOrder.Count);
        Assert.Equal(ExpectedGroups, PaletteLibrary.GroupOrder);
        Assert.Equal(10, PaletteLibrary.GroupOrder.Distinct().Count());

        var groupSet = new HashSet<string>(ExpectedGroups);
        Assert.All(PaletteLibrary.All, palette => Assert.Contains(palette.Group, groupSet));
        Assert.All(PaletteLibrary.All, palette => Assert.Contains(palette.Group, PaletteLibrary.GroupOrder));

        var resourceNames = typeof(PaletteLibrary).Assembly.GetManifestResourceNames();
        Assert.Contains(resourceNames, name => name.EndsWith("palettes.json", StringComparison.Ordinal));
    }

    [Fact]
    public void EveryPaletteHasValidData()
    {
        var colorCount = 0;
        foreach (var palette in PaletteLibrary.All)
        {
            Assert.Matches(IdPattern, palette.Id);
            Assert.False(string.IsNullOrWhiteSpace(palette.Name));
            Assert.False(string.IsNullOrWhiteSpace(palette.Group));
            Assert.False(string.IsNullOrWhiteSpace(palette.Description));
            Assert.NotEmpty(palette.Tags);
            Assert.InRange(palette.Colors.Count, 4, 8);

            foreach (var color in palette.Colors)
            {
                Assert.Matches(HexPattern, color);
                Assert.Equal(color, PaletteLibrary.NormalizeHex(color));
                colorCount++;
            }

            if (palette.NamedColors is not null)
            {
                foreach (var pair in palette.NamedColors)
                {
                    Assert.False(string.IsNullOrEmpty(pair.Key));
                    Assert.Matches(HexPattern, pair.Value);
                    Assert.Equal(pair.Value, PaletteLibrary.NormalizeHex(pair.Value));
                }
            }
        }

        Assert.Equal(106, colorCount);
        Assert.Equal(2, PaletteLibrary.All.Count(palette => palette.NamedColors is not null));
    }

    [Fact]
    public void LegacyPaletteMappingsAreExact()
    {
        var project = PaletteLibrary.ById("legacy_project");
        Assert.Equal("原版 · 项目类别", project.Name);
        Assert.Equal("原版", project.Group);
        Assert.Equal(new[] { "#6AFFFF", "#E0A6E5", "#EBE082", "#CCCCCC" }, project.Colors);
        Assert.NotNull(project.NamedColors);
        Assert.Equal(7, project.NamedColors!.Count);
        Assert.Equal("#6AFFFF", project.NamedColors["软件开发"]);
        Assert.Equal("#E0A6E5", project.NamedColors["MES改造"]);
        Assert.Equal("#EBE082", project.NamedColors["视觉改造"]);
        Assert.Equal("#CCCCCC", project.NamedColors["方案review"]);
        Assert.Equal("#CCCCCC", project.NamedColors["方案Review"]);
        Assert.Equal("#CCCCCC", project.NamedColors["iPhone扫码"]);
        Assert.Equal("#CCCCCC", project.NamedColors["运控改造"]);

        var status = PaletteLibrary.ById("legacy_status");
        Assert.Equal("原版 · 项目状态", status.Name);
        Assert.Equal("原版", status.Group);
        Assert.Equal(new[] { "#FFF45C", "#C2B9B7", "#D54660", "#DA435C" }, status.Colors);
        Assert.NotNull(status.NamedColors);
        Assert.Equal(4, status.NamedColors!.Count);
        Assert.Equal("#FFF45C", status.NamedColors["On-going"]);
        Assert.Equal("#C2B9B7", status.NamedColors["Done"]);
        Assert.Equal("#D54660", status.NamedColors["Pause"]);
        Assert.Equal("#DA435C", status.NamedColors["Delay"]);

        Assert.Null(PaletteLibrary.ById("business_steel").NamedColors);
        Assert.Null(PaletteLibrary.ById("high_contrast").NamedColors);
    }

    [Fact]
    public void ByIdIgnoresCaseAndWhitespace()
    {
        var expected = PaletteLibrary.ById("legacy_project");
        Assert.Same(expected, PaletteLibrary.ById(" LEGACY_PROJECT "));
        Assert.Same(expected, PaletteLibrary.ById("Legacy_Project"));
        Assert.Equal("原版 · 项目类别", expected.Name);
    }

    [Fact]
    public void ByIdThrowsForUnknownId()
    {
        var exception = Assert.Throws<KeyNotFoundException>(() => PaletteLibrary.ById("does_not_exist"));
        Assert.Contains("does_not_exist", exception.Message, StringComparison.Ordinal);
        Assert.Throws<ArgumentNullException>(() => PaletteLibrary.ById(null!));
    }

    [Fact]
    public void ByGroupReturnsPalettesInCanonicalOrder()
    {
        Assert.Equal(16, PaletteLibrary.ByGroup(null).Count);
        Assert.Equal(ExpectedIds, PaletteLibrary.ByGroup(null).Select(palette => palette.Id));

        foreach (var (group, count) in ExpectedGroupCounts)
        {
            var palettes = PaletteLibrary.ByGroup(group);
            Assert.Equal(count, palettes.Count);
            Assert.All(palettes, palette => Assert.Equal(group, palette.Group));
            Assert.Equal(
                ExpectedIds.Where(id => PaletteLibrary.ById(id).Group == group),
                palettes.Select(palette => palette.Id));
        }

        Assert.Empty(PaletteLibrary.ByGroup("不存在的分组"));

        var grouped = PaletteLibrary.ByGroupMap();
        Assert.Equal(PaletteLibrary.GroupOrder, grouped.Keys);
        Assert.Equal(16, grouped.Values.Sum(list => list.Count));
    }

    // ---------------------------------------------------------------------
    // assign_colors
    // ---------------------------------------------------------------------

    [Fact]
    public void AssignColorsCyclesThroughPaletteColors()
    {
        var palette = PaletteLibrary.ById("business_steel");
        var labels = Enumerable.Range(0, 10).Select(index => $"L{index}").ToArray();
        var assignment = PaletteLibrary.AssignColors(palette, labels);

        Assert.Equal(10, assignment.Count);
        Assert.Equal(labels, assignment.Keys);

        var expected = new[]
        {
            "#17324D", "#24547E", "#3B7DB3", "#6FA8D3", "#A9CBE5",
            "#D5E6F2", "#7C8B99", "#17324D", "#24547E", "#3B7DB3",
        };
        for (var index = 0; index < labels.Length; index++)
        {
            Assert.Equal(expected[index], assignment[labels[index]]);
        }
    }

    [Fact]
    public void AssignColorsUsesLegacyNamedColorsWithoutConsumingCycle()
    {
        var palette = PaletteLibrary.ById("legacy_project");
        var labels = new[]
        {
            "软件开发", "MES改造", "视觉改造", "方案review", "方案Review",
            "iPhone扫码", "运控改造", "新增1", "新增2", "软件开发",
        };
        var assignment = PaletteLibrary.AssignColors(palette, labels);

        Assert.Equal(9, assignment.Count);
        Assert.Equal("#6AFFFF", assignment["软件开发"]);
        Assert.Equal("#E0A6E5", assignment["MES改造"]);
        Assert.Equal("#EBE082", assignment["视觉改造"]);
        Assert.Equal("#CCCCCC", assignment["方案review"]);
        Assert.Equal("#CCCCCC", assignment["方案Review"]);
        Assert.Equal("#CCCCCC", assignment["iPhone扫码"]);
        Assert.Equal("#CCCCCC", assignment["运控改造"]);
        // Named labels do not consume the colour cycle, so unknown labels start at index 0.
        Assert.Equal("#6AFFFF", assignment["新增1"]);
        Assert.Equal("#E0A6E5", assignment["新增2"]);
    }

    [Fact]
    public void AssignColorsOverridesTakePriorityAndDoNotConsumeCycle()
    {
        var palette = PaletteLibrary.ById("business_steel");
        var overrides = new Dictionary<string, string>
        {
            ["A"] = "#ABC",
            ["C"] = "#112233",
            ["Z"] = "#000000",
        };
        var assignment = PaletteLibrary.AssignColors(palette, new[] { "A", "B", "C" }, overrides);

        Assert.Equal(3, assignment.Count);
        Assert.False(assignment.ContainsKey("Z"));
        Assert.Equal("#AABBCC", assignment["A"]);
        Assert.Equal("#17324D", assignment["B"]);
        Assert.Equal("#112233", assignment["C"]);

        var namedOverride = PaletteLibrary.AssignColors(
            PaletteLibrary.ById("legacy_project"),
            new[] { "软件开发", "Other" },
            new Dictionary<string, string> { ["软件开发"] = "#fff" });
        Assert.Equal("#FFFFFF", namedOverride["软件开发"]);
        Assert.Equal("#6AFFFF", namedOverride["Other"]);
    }

    [Fact]
    public void AssignColorsHandlesEmptyAndDuplicateLabels()
    {
        var palette = PaletteLibrary.ById("legacy_status");
        Assert.Empty(PaletteLibrary.AssignColors(palette, Array.Empty<string>()));

        var assignment = PaletteLibrary.AssignColors(palette, new[] { "a", "a", "b" });
        Assert.Equal(2, assignment.Count);
        Assert.Equal("#FFF45C", assignment["a"]);
        Assert.Equal("#C2B9B7", assignment["b"]);

        Assert.Throws<ArgumentNullException>(
            () => PaletteLibrary.AssignColors(null!, new[] { "a" }));
        Assert.Throws<ArgumentNullException>(
            () => PaletteLibrary.AssignColors(palette, null!));
    }

    // ---------------------------------------------------------------------
    // label_color — modes
    // ---------------------------------------------------------------------

    [Fact]
    public void LabelColorMatchModeReturnsFillColor()
    {
        Assert.Equal("#AABBCC", PaletteLibrary.LabelColor("#abc", "match"));
        Assert.Equal("#6AFFFF", PaletteLibrary.LabelColor("#6AFFFF", "match"));
        Assert.Equal("#FFFFFF", PaletteLibrary.LabelColor("#FFFFFF", "MATCH"));
        Assert.Equal("#17324D", PaletteLibrary.LabelColor("#17324D", " match "));
    }

    [Fact]
    public void LabelColorSingleModeReturnsSingleColor()
    {
        Assert.Equal("#334155", PaletteLibrary.LabelColor("#6AFFFF", "single"));
        Assert.Equal("#AABBCC", PaletteLibrary.LabelColor("#6AFFFF", "single", "#abc"));
        Assert.Equal("#FFFFFF", PaletteLibrary.LabelColor("#111111", "SINGLE", "#FFFFFF"));
        // The mode string is trimmed/lower-cased like Python's str(mode).strip().lower().
        Assert.Equal("#000000", PaletteLibrary.LabelColor("#6AFFFF", " Single ", "#000"));
    }

    [Fact]
    public void LabelColorRejectsInvalidModeAndColors()
    {
        Assert.Throws<ArgumentException>(() => PaletteLibrary.LabelColor("#6AFFFF", "fill"));
        Assert.Throws<ArgumentException>(() => PaletteLibrary.LabelColor("#6AFFFF", ""));
        Assert.Throws<ArgumentException>(() => PaletteLibrary.LabelColor("not-a-color", "auto"));
        Assert.Throws<ArgumentNullException>(() => PaletteLibrary.LabelColor(null!, "auto"));
        Assert.Throws<ArgumentException>(() => PaletteLibrary.LabelColor("#6AFFFF", "auto", "#334155", "nope"));
    }

    // ---------------------------------------------------------------------
    // label_color — auto mode (Python values)
    // ---------------------------------------------------------------------

    [Theory]
    [InlineData("#6AFFFF", "#009F9F")]
    [InlineData("#E0A6E5", "#CB6AD3")]
    [InlineData("#EBE082", "#9E9019")]
    [InlineData("#CCCCCC", "#8F8F8F")]
    [InlineData("#FFF45C", "#9B9100")]
    [InlineData("#C2B9B7", "#9B8C89")]
    [InlineData("#D54660", "#D54660")]
    [InlineData("#DA435C", "#DA435C")]
    [InlineData("#F7D774", "#B38A0A")]
    [InlineData("#D6ECF0", "#3F9AAB")]
    [InlineData("#F3F4F6", "#8590A4")]
    [InlineData("#D1D5DB", "#8590A0")]
    [InlineData("#F49AB0", "#ED5D81")]
    [InlineData("#A8C686", "#759B49")]
    [InlineData("#111827", "#111827")]
    [InlineData("#17324D", "#17324D")]
    [InlineData("#FFFFFF", "#8F8F8F")]
    [InlineData("#000000", "#000000")]
    [InlineData("#808080", "#808080")]
    [InlineData("#334155", "#334155")]
    public void LabelColorAutoMatchesPythonOnWhite(string fill, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.LabelColor(fill, "auto", background: "#FFFFFF"));
    }

    [Fact]
    public void LabelColorAutoMatchesPythonForEveryPaletteColor()
    {
        var checkedColors = 0;
        foreach (var palette in PaletteLibrary.All)
        {
            var expected = ExpectedAutoLabelOnWhite[palette.Id];
            var actual = palette.Colors
                .Select(color => PaletteLibrary.LabelColor(color, "auto", background: "#FFFFFF"))
                .ToArray();

            Assert.Equal(expected, actual);
            Assert.Equal(palette.Colors.Count, actual.Length);

            foreach (var labelColor in actual)
            {
                Assert.Matches(HexPattern, labelColor);
                Assert.True(
                    PaletteLibrary.ContrastRatio(labelColor, "#FFFFFF") >= 3.0,
                    $"auto label colour {labelColor} must reach WCAG 3.0 on white");
                checkedColors++;
            }
        }

        Assert.Equal(106, checkedColors);
    }

    [Theory]
    [InlineData("#111827", "#4663A1")]
    [InlineData("#17324D", "#2F679F")]
    [InlineData("#000000", "#656565")]
    [InlineData("#334155", "#506685")]
    [InlineData("#6AFFFF", "#6AFFFF")]
    [InlineData("#FFFFFF", "#FFFFFF")]
    public void LabelColorAutoMatchesPythonOnDarkBackground(string fill, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.LabelColor(fill, "auto", background: "#111111"));
    }

    [Theory]
    [InlineData("#D54660", "#DE6C81")]
    [InlineData("#DA435C", "#E26A7E")]
    [InlineData("#111827", "#7790C4")]
    [InlineData("#17324D", "#5A94CE")]
    [InlineData("#000000", "#8F8F8F")]
    [InlineData("#808080", "#8F8F8F")]
    [InlineData("#334155", "#7B91B0")]
    public void LabelColorAutoMatchesPythonOnSlateBackground(string fill, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.LabelColor(fill, "auto", background: "#334155"));
    }

    // ---------------------------------------------------------------------
    // WCAG / luminance
    // ---------------------------------------------------------------------

    [Theory]
    [InlineData("#000000", "#FFFFFF", 21.0)]
    [InlineData("#FFFFFF", "#FFFFFF", 1.0)]
    [InlineData("#777777", "#FFFFFF", 4.478089453577214)]
    [InlineData("#767676", "#FFFFFF", 4.542224959605253)]
    [InlineData("#17324D", "#FFFFFF", 13.126337902439268)]
    [InlineData("#F7D774", "#FFFFFF", 1.4068280204465298)]
    [InlineData("#6AFFFF", "#FFFFFF", 1.2096192894771771)]
    [InlineData("#111827", "#111111", 1.0644510822950752)]
    [InlineData("#334155", "#FFFFFF", 10.35474573184942)]
    [InlineData("#D54660", "#FFFFFF", 4.308402866047346)]
    public void ContrastRatioMatchesPython(string colorA, string colorB, double expected)
    {
        Assert.Equal(expected, PaletteLibrary.ContrastRatio(colorA, colorB), 12);
        Assert.Equal(expected, PaletteLibrary.ContrastRatio(colorB, colorA), 12);
    }

    [Theory]
    [InlineData("#FFFFFF", 1.0)]
    [InlineData("#000000", 0.0)]
    [InlineData("#777777", 0.184474994500441)]
    [InlineData("#17324D", 0.029991845997266182)]
    [InlineData("#F7D774", 0.696359885316137)]
    [InlineData("#6AFFFF", 0.8180417129044231)]
    public void LuminanceMatchesPython(string color, double expected)
    {
        Assert.Equal(expected, PaletteLibrary.Luminance(color), 12);
    }

    [Fact]
    public void ContrastRatioRangeAndSymmetryHoldForAllPaletteColors()
    {
        foreach (var palette in PaletteLibrary.All)
        {
            foreach (var color in palette.Colors)
            {
                var ratio = PaletteLibrary.ContrastRatio(color, "#FFFFFF");
                Assert.InRange(ratio, 1.0, 21.0 + 1e-12);
                Assert.Equal(ratio, PaletteLibrary.ContrastRatio("#FFFFFF", color), 12);
            }
        }
    }

    // ---------------------------------------------------------------------
    // Delta E / colour maths
    // ---------------------------------------------------------------------

    [Theory]
    [InlineData("#000000", "#FFFFFF", 100.00000386666815)]
    [InlineData("#FF0000", "#00FF00", 170.56524200601007)]
    [InlineData("#6AFFFF", "#E0A6E5", 73.99705740749481)]
    [InlineData("#17324D", "#D5E6F2", 71.41509543303343)]
    [InlineData("#D7263D", "#3D348B", 90.5195276992617)]
    [InlineData("#111827", "#F3F4F6", 88.48402506563242)]
    public void DeltaEMatchesPython(string colorA, string colorB, double expected)
    {
        Assert.Equal(expected, PaletteLibrary.DeltaE(colorA, colorB), 9);
        Assert.Equal(expected, PaletteLibrary.DeltaE(colorB, colorA), 9);
    }

    [Fact]
    public void DeltaEOfSameColorIsZero()
    {
        foreach (var palette in PaletteLibrary.All)
        {
            foreach (var color in palette.Colors)
            {
                Assert.Equal(0.0, PaletteLibrary.DeltaE(color, color));
            }
        }
    }

    [Theory]
    [InlineData("#000000", "#FFFFFF", 0.5, "#BCBCBC")]
    [InlineData("#FF0000", "#0000FF", 0.5, "#BC00BC")]
    [InlineData("#6AFFFF", "#CCCCCC", 0.25, "#8BF4F4")]
    [InlineData("#17324D", "#FFFFFF", 0.75, "#E1E2E3")]
    public void MixColorsMatchesPython(string colorA, string colorB, double weight, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.MixColors(colorA, colorB, weight));
        // Default weight is 0.5, like Python.
        Assert.Equal(PaletteLibrary.MixColors(colorA, colorB, 0.5), PaletteLibrary.MixColors(colorA, colorB));
    }

    [Fact]
    public void MixColorsEndpointsAndValidation()
    {
        Assert.Equal("#6AFFFF", PaletteLibrary.MixColors("#6AFFFF", "#CCCCCC", 0.0));
        Assert.Equal("#CCCCCC", PaletteLibrary.MixColors("#6AFFFF", "#CCCCCC", 1.0));
        Assert.Throws<ArgumentOutOfRangeException>(
            () => PaletteLibrary.MixColors("#000000", "#FFFFFF", -0.1));
        Assert.Throws<ArgumentOutOfRangeException>(
            () => PaletteLibrary.MixColors("#000000", "#FFFFFF", 1.1));
    }

    [Theory]
    [InlineData("#6AFFFF", 0.15, "#34FFFF")]
    [InlineData("#F7D774", 0.3, "#F0B90E")]
    [InlineData("#334155", 0.5, "#1A202A")]
    [InlineData("#FF0000", 1.0, "#000000")]
    [InlineData("#00FF00", 0.0, "#00FF00")]
    public void DarkenMatchesPython(string color, double amount, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.Darken(color, amount));
    }

    [Theory]
    [InlineData("#6AFFFF", 0.15, "#80FFFF")]
    [InlineData("#17324D", 0.3, "#336FAC")]
    [InlineData("#334155", 0.5, "#8A9DB9")]
    [InlineData("#000000", 1.0, "#FFFFFF")]
    [InlineData("#FF0000", 0.0, "#FF0000")]
    public void LightenMatchesPython(string color, double amount, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.Lighten(color, amount));
    }

    [Fact]
    public void DarkenLightenDefaultAmountIsFifteenPercent()
    {
        Assert.Equal(PaletteLibrary.Darken("#6AFFFF", 0.15), PaletteLibrary.Darken("#6AFFFF"));
        Assert.Equal(PaletteLibrary.Lighten("#6AFFFF", 0.15), PaletteLibrary.Lighten("#6AFFFF"));
        Assert.Throws<ArgumentOutOfRangeException>(() => PaletteLibrary.Darken("#6AFFFF", 1.5));
        Assert.Throws<ArgumentOutOfRangeException>(() => PaletteLibrary.Lighten("#6AFFFF", -0.5));
    }

    [Theory]
    [InlineData("#FF0000", 0.0, 1.0, 0.5)]
    [InlineData("#00FF00", 120.0, 1.0, 0.5)]
    [InlineData("#0000FF", 240.0, 1.0, 0.5)]
    [InlineData("#6AFFFF", 180.0, 1.0, 0.707843137254902)]
    [InlineData("#17324D", 210.0, 0.5399999999999999, 0.19607843137254902)]
    [InlineData("#808080", 0.0, 0.0, 0.5019607843137255)]
    [InlineData("#FFFFFF", 0.0, 0.0, 1.0)]
    [InlineData("#000000", 0.0, 0.0, 0.0)]
    public void RgbToHslMatchesPython(string color, double hue, double saturation, double lightness)
    {
        var (actualHue, actualSaturation, actualLightness) = PaletteLibrary.RgbToHsl(color);
        Assert.Equal(hue, actualHue, 12);
        Assert.Equal(saturation, actualSaturation, 12);
        Assert.Equal(lightness, actualLightness, 12);
    }

    [Theory]
    [InlineData(0.0, 1.0, 0.5, "#FF0000")]
    [InlineData(120.0, 1.0, 0.5, "#00FF00")]
    [InlineData(240.0, 1.0, 0.5, "#0000FF")]
    [InlineData(360.0, 1.0, 0.5, "#FF0000")]
    [InlineData(-30.0, 0.6, 0.4, "#A32966")]
    [InlineData(37.5, 0.25, 0.75, "#CFC3AF")]
    [InlineData(0.0, 0.0, 0.5, "#808080")]
    [InlineData(720.0, 1.0, 0.5, "#FF0000")]
    public void HslToHexMatchesPython(double hue, double saturation, double lightness, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.HslToHex(hue, saturation, lightness));
    }

    [Fact]
    public void HslRoundTripReproducesEveryPaletteColor()
    {
        var checkedColors = 0;
        foreach (var palette in PaletteLibrary.All)
        {
            foreach (var color in palette.Colors)
            {
                var (hue, saturation, lightness) = PaletteLibrary.RgbToHsl(color);
                Assert.Equal(color, PaletteLibrary.HslToHex(hue, saturation, lightness));
                checkedColors++;
            }
        }

        Assert.Equal(106, checkedColors);
    }

    // ---------------------------------------------------------------------
    // normalize_hex
    // ---------------------------------------------------------------------

    [Theory]
    [InlineData("#abc", "#AABBCC")]
    [InlineData("abc", "#AABBCC")]
    [InlineData(" #AbC ", "#AABBCC")]
    [InlineData("#aabbcc", "#AABBCC")]
    [InlineData("AABBCC", "#AABBCC")]
    [InlineData("#000000", "#000000")]
    [InlineData(" #FFFFFF ", "#FFFFFF")]
    public void NormalizeHexAcceptsPythonForms(string input, string expected)
    {
        Assert.Equal(expected, PaletteLibrary.NormalizeHex(input));
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("#abcd")]
    [InlineData("#GGGGGG")]
    [InlineData("red")]
    [InlineData("##abc")]
    [InlineData("#12345")]
    public void NormalizeHexRejectsInvalidColors(string input)
    {
        Assert.Throws<ArgumentException>(() => PaletteLibrary.NormalizeHex(input));
    }

    [Fact]
    public void NormalizeHexRejectsNull()
    {
        Assert.Throws<ArgumentNullException>(() => PaletteLibrary.NormalizeHex(null!));
    }

    // ---------------------------------------------------------------------
    // recommend_palettes
    // ---------------------------------------------------------------------

    [Fact]
    public void RecommendMatchesPythonOrdering()
    {
        foreach (var (labelCount, expectedIds) in ExpectedRecommendTop4)
        {
            var actual = PaletteLibrary.Recommend(labelCount)
                .Select(palette => palette.Id)
                .ToArray();
            Assert.Equal(expectedIds, actual);
        }
    }

    [Fact]
    public void RecommendScoresOrderMatchesPython()
    {
        var scored = PaletteLibrary.PaletteScores(3);
        Assert.Equal(16, scored.Count);
        Assert.Equal(ExpectedScoresOrderForThreeLabels, scored.Select(item => item.Palette.Id));

        // Python: palette_scores(3) scores, rounded to 8 decimals.
        var expectedScores = new[] { 0.96813929, 0.96474516, 0.96418731, 0.93629558 };
        for (var index = 0; index < expectedScores.Length; index++)
        {
            Assert.Equal(expectedScores[index], scored[index].Score, 6);
        }
    }

    [Fact]
    public void RecommendIsDeterministic()
    {
        var first = PaletteLibrary.Recommend(5).Select(palette => palette.Id).ToArray();
        var second = PaletteLibrary.Recommend(5).Select(palette => palette.Id).ToArray();
        var third = PaletteLibrary.Recommend(5).Select(palette => palette.Id).ToArray();
        Assert.Equal(first, second);
        Assert.Equal(first, third);

        var firstPalette = PaletteLibrary.Recommend(3).First();
        var secondPalette = PaletteLibrary.Recommend(3).First();
        Assert.Same(firstPalette, secondPalette);

        // Only inputs influence the ranking: the global palette list is untouched.
        Assert.Equal(ExpectedIds, PaletteLibrary.All.Select(palette => palette.Id));
    }

    [Theory]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(6)]
    public void RecommendRespectsDarkBackgrounds(int labelCount)
    {
        var dark = PaletteLibrary.Recommend(labelCount, background: "#111111")
            .Select(palette => palette.Id)
            .ToArray();
        var light = PaletteLibrary.Recommend(labelCount, background: "#FFFFFF")
            .Select(palette => palette.Id)
            .ToArray();
        Assert.NotEqual(light, dark);

        // Python reference for background="#111111".
        var expectedDark = new Dictionary<int, string[]>
        {
            [2] = new[] { "legacy_project", "legacy_status", "macaron_pastel", "vibrant_candy" },
            [3] = new[] { "high_contrast", "legacy_project", "legacy_status", "macaron_pastel" },
            [4] = new[] { "high_contrast", "legacy_project", "macaron_pastel", "vibrant_candy" },
            [6] = new[] { "macaron_pastel", "vibrant_candy", "high_contrast", "chinese_vermilion" },
        };
        Assert.Equal(expectedDark[labelCount], dark);
    }

    [Fact]
    public void RecommendLimitsAndValidation()
    {
        Assert.Equal(4, PaletteLibrary.Recommend(3).Count);
        Assert.Equal(2, PaletteLibrary.Recommend(3, 2).Count);
        Assert.Equal(16, PaletteLibrary.Recommend(3, 100).Count);
        Assert.Empty(PaletteLibrary.Recommend(3, 0));
        Assert.Empty(PaletteLibrary.Recommend(3, -1));
        // Python checks limit before validating n_labels.
        Assert.Empty(PaletteLibrary.Recommend(0, 0));

        Assert.Throws<ArgumentOutOfRangeException>(() => PaletteLibrary.Recommend(0));
        Assert.Throws<ArgumentOutOfRangeException>(() => PaletteLibrary.Recommend(-3));
        Assert.Throws<ArgumentException>(() => PaletteLibrary.Recommend(3, 4, "not-a-color"));
    }

    [Fact]
    public void RecommendSingleLabelPrefersHighestVisibilityPalettes()
    {
        var recommended = PaletteLibrary.Recommend(1);
        Assert.Equal(4, recommended.Count);
        Assert.Equal("business_forest", recommended[0].Id);
        Assert.All(recommended, palette => Assert.InRange(palette.Colors.Count, 4, 8));
    }
}

/// <summary>Direct tests for the low-level colour maths helpers (the Python module's utility layer).</summary>
public sealed class ColorMathTests
{
    [Fact]
    public void DefaultsMatchPythonConstants()
    {
        Assert.Equal("#334155", ColorMath.DefaultLabelColor);
        Assert.Equal("#FFFFFF", ColorMath.DefaultBackground);
        Assert.Equal(3.0, ColorMath.LabelMinContrast);
        Assert.Equal(3.2, ColorMath.LabelTargetContrast);
        Assert.Equal(ColorMath.DefaultLabelColor, PaletteLibrary.DefaultLabelColor);
        Assert.Equal(ColorMath.DefaultBackground, PaletteLibrary.DefaultBackground);
        Assert.Equal(ColorMath.LabelMinContrast, PaletteLibrary.LabelMinContrast);
    }

    [Theory]
    [InlineData("#abc", true)]
    [InlineData("aabbcc", true)]
    [InlineData("#AABBCC", true)]
    [InlineData("", false)]
    [InlineData("red", false)]
    [InlineData("#abcd", false)]
    public void IsHexColorMatchesPython(string value, bool expected)
    {
        Assert.Equal(expected, ColorMath.IsHexColor(value));
    }

    [Fact]
    public void IsHexColorRejectsNull()
    {
        Assert.False(ColorMath.IsHexColor(null));
    }

    [Fact]
    public void HexToRgbAndBack()
    {
        Assert.Equal((0x12, 0x34, 0x56), ColorMath.HexToRgb("#123456"));
        Assert.Equal((255, 255, 255), ColorMath.HexToRgb("FFFFFF"));
        Assert.Equal("#123456", ColorMath.RgbToHex(0x12, 0x34, 0x56));
        Assert.Equal("#FFFFFF", ColorMath.RgbToHex(255.4, 255.6, 256.0));
        Assert.Equal("#FFFF00", ColorMath.RgbToHex(255.4, 256.0, -3.0));
        Assert.Equal("#808080", ColorMath.RgbToHex(127.5, 127.5, 127.5));
    }

    [Fact]
    public void PaletteLibraryDelegatesToColorMath()
    {
        foreach (var palette in PaletteLibrary.All)
        {
            foreach (var color in palette.Colors)
            {
                Assert.Equal(ColorMath.NormalizeHex(color), PaletteLibrary.NormalizeHex(color));
                Assert.Equal(ColorMath.Luminance(color), PaletteLibrary.Luminance(color));
                Assert.Equal(
                    ColorMath.ContrastRatio(color, "#FFFFFF"),
                    PaletteLibrary.ContrastRatio(color, "#FFFFFF"));
                Assert.Equal(ColorMath.DeltaE(color, "#FFFFFF"), PaletteLibrary.DeltaE(color, "#FFFFFF"));
            }
        }
    }
}
