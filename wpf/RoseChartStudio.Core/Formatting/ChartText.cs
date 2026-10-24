using System.Globalization;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Formatting;

/// <summary>Text formatting shared by screen and export renderers.</summary>
public static class ChartText
{
    public static IReadOnlyList<string> LabelLines(
        ChartStyle style, string label, int value, double percent)
    {
        var parts = new List<string>();
        if (style.ShowName && !string.IsNullOrEmpty(label))
        {
            parts.Add(label);
        }
        if (style.ShowValue)
        {
            parts.Add(value.ToString(CultureInfo.InvariantCulture) + style.ValueSuffix);
        }
        var header = string.Join(" ", parts).Trim();
        var lines = new List<string>(2);
        if (header.Length > 0)
        {
            lines.Add(header);
        }
        if (style.ShowPercent)
        {
            var digits = Math.Clamp(style.PercentDecimals, 0, 6);
            lines.Add(percent.ToString("F" + digits, CultureInfo.InvariantCulture) + "%");
        }
        return lines;
    }

    public static string CenterText(ChartStyle style, int total, int count, int maximum)
    {
        var template = style.CenterText.Trim();
        if (template.Length == 0)
        {
            return "";
        }
        return template
            .Replace("{total}", total.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
            .Replace("{n}", count.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal)
            .Replace("{max}", maximum.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal);
    }
}
