namespace RoseChartStudio.Core.Models;

/// <summary>A rendered sector polygon in chart data coordinates.</summary>
public sealed class SectorShape
{
    public required string Label { get; init; }
    public int Value { get; init; }
    public double Percent { get; init; }
    public required string FillColor { get; init; }
    public double OuterRadius { get; init; }
    public double Theta1 { get; init; }
    public double Theta2 { get; init; }
    public double MidAngle { get; init; }
    public double DirectionX { get; init; }
    public double DirectionY { get; init; }
    public PointD Anchor { get; init; }
    public required IReadOnlyList<PointD> Points { get; init; }
}

/// <summary>A draggable data label and its three-segment leader line.</summary>
public sealed class LabelShape
{
    public required string Label { get; init; }
    public int Value { get; init; }
    public double Percent { get; init; }
    public int Side { get; init; } // +1 right, -1 left
    public double DirectionX { get; init; }
    public double DirectionY { get; init; }
    public double AnchorX { get; init; }
    public double AnchorY { get; init; }
    public double AutoY { get; init; }
    public double AutoLineEndX { get; init; }
    public double Y { get; set; }
    public double LineEndX { get; set; }
    public double ElbowX { get; set; }
    public required string Color { get; set; }
    public required IReadOnlyList<string> Lines { get; init; }
    public double TextGap { get; init; }

    public string Text => string.Join("\n", Lines);
    public double TextX => LineEndX + Side * TextGap;

    public IReadOnlyList<PointD> LeaderPoints => new[]
    {
        new PointD(AnchorX, AnchorY),
        new PointD(ElbowX, Y),
        new PointD(LineEndX, Y),
    };

    public LayoutOffset Offset => new(LineEndX - AutoLineEndX, Y - AutoY);
}

/// <summary>Everything needed to paint one rose chart, in data coordinates.</summary>
public sealed class ChartScene
{
    public required ChartStyle Style { get; init; }
    public required IReadOnlyList<SectorShape> Sectors { get; init; }
    public required IReadOnlyList<LabelShape> Labels { get; init; }
    public int Total { get; init; }
    public int Maximum { get; init; }
    public string? CenterText { get; init; }
    public string Background => Style.Background;

    /// <summary>Matplotlib v2 axis extent (data coordinates).</summary>
    public static readonly RectD DataBounds = new(-1.72, -1.22, 3.44, 2.40);
    public static readonly PointD ChartCenter = new(0.0, -0.05);

    /// <summary>Virtual 100-DPI canvas used by all renderers for layout parity.</summary>
    public double VirtualWidth => Math.Max(1.0, Style.FigureWidth * 100.0);
    public double VirtualHeight => Math.Max(1.0, Style.FigureHeight * 100.0);

    public LabelShape? FindLabel(string label)
    {
        foreach (var shape in Labels)
        {
            if (string.Equals(shape.Label, label, StringComparison.Ordinal))
            {
                return shape;
            }
        }
        return null;
    }
}
