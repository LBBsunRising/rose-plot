using System.Globalization;
using System.Windows;
using System.Windows.Media;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Rendering;

/// <summary>Hex color helpers with a small parse cache.</summary>
public static class ColorUtil
{
    private static readonly Dictionary<string, Color> Cache = new(StringComparer.OrdinalIgnoreCase);

    public static Color ToColor(string? hex, Color fallback)
    {
        if (string.IsNullOrWhiteSpace(hex))
        {
            return fallback;
        }
        var text = hex.Trim();
        if (Cache.TryGetValue(text, out var cached))
        {
            return cached;
        }
        try
        {
            if (!text.StartsWith('#'))
            {
                text = "#" + text;
            }
            if (text.Length == 4)
            {
                text = $"#{text[1]}{text[1]}{text[2]}{text[2]}{text[3]}{text[3]}";
            }
            if (text.Length == 7)
            {
                var color = Color.FromRgb(
                    byte.Parse(text.AsSpan(1, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture),
                    byte.Parse(text.AsSpan(3, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture),
                    byte.Parse(text.AsSpan(5, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture));
                Cache[text] = color;
                return color;
            }
        }
        catch
        {
            // fall through to the fallback color
        }
        return fallback;
    }

    public static SolidColorBrush Brush(string? hex, Color fallback) =>
        new(ToColor(hex, fallback));

    public static SolidColorBrush Brush(string? hex) =>
        Brush(hex, Colors.Black);

    public static string ToHex(Color color) => $"#{color.R:X2}{color.G:X2}{color.B:X2}";
}

/// <summary>
/// Maps chart data coordinates to the virtual 100-DPI figure canvas (1200×800
/// for the default 12×8 in figure). This mirrors the matplotlib axes setup
/// (position [0.02,0.04,0.96,0.82], equal aspect) so the WPF preview matches v2.
/// </summary>
public sealed class SceneMapper
{
    public const double DataLeft = -1.72;
    public const double DataRight = 1.72;
    public const double DataBottom = -1.22;
    public const double DataTop = 1.18;
    public const double DataWidth = 3.44;
    public const double DataHeight = 2.40;
    public const double VirtualPerPoint = 100.0 / 72.0;

    public SceneMapper(ChartStyle style)
    {
        VirtualWidth = Math.Max(1.0, style.FigureWidth * 100.0);
        VirtualHeight = Math.Max(1.0, style.FigureHeight * 100.0);
        var axesLeft = 0.02 * VirtualWidth;
        var axesBottom = 0.04 * VirtualHeight;
        var axesWidth = 0.96 * VirtualWidth;
        var axesHeight = 0.82 * VirtualHeight;
        Scale = Math.Min(axesWidth / DataWidth, axesHeight / DataHeight);
        var boxWidth = DataWidth * Scale;
        var boxHeight = DataHeight * Scale;
        BoxLeft = axesLeft + (axesWidth - boxWidth) / 2.0;
        BoxBottom = axesBottom + (axesHeight - boxHeight) / 2.0;
    }

    public double VirtualWidth { get; }
    public double VirtualHeight { get; }
    public double Scale { get; }
    public double BoxLeft { get; }
    public double BoxBottom { get; }

    public Point ToVirtual(PointD point) => new(
        BoxLeft + (point.X - DataLeft) * Scale,
        VirtualHeight - (BoxBottom + (point.Y - DataBottom) * Scale));

    public PointD ToData(Point point) => new(
        DataLeft + (point.X - BoxLeft) / Scale,
        DataBottom + ((VirtualHeight - point.Y) - BoxBottom) / Scale);

    public double PointsToVirtual(double points) => points * VirtualPerPoint;

    /// <summary>Convert a label's data-space text gap to virtual units.</summary>
    public double DataToVirtual(double length) => length * Scale;
}
