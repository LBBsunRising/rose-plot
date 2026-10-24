using System.Globalization;
using System.Windows;
using System.Windows.Media;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Rendering;

/// <summary>Text/geometry measurements for one label in virtual coordinates.</summary>
public readonly record struct LabelBounds(Rect AngleRect, double TextLeft, double TextTop, double Width, double Height);

/// <summary>
/// Pure WPF drawing of a <see cref="ChartScene"/> in virtual figure coordinates.
/// The same methods paint the screen, PNG export and (through a scene adapter)
/// SVG/PDF export, so all renderers stay visually identical.
/// </summary>
public static class ChartDrawing
{
    public static readonly Color LabelFallback = Color.FromRgb(0x33, 0x41, 0x55);
    public static readonly Color TitleFallback = Color.FromRgb(0x33, 0x33, 0x33);

    public static Typeface Typeface(ChartStyle style, bool bold = false) =>
        new(
            new FontFamily(string.IsNullOrWhiteSpace(style.FontFamily) ? "Microsoft YaHei" : style.FontFamily),
            FontStyles.Normal,
            bold ? FontWeights.Bold : FontWeights.Normal,
            FontStretches.Normal);

    public static FormattedText Text(
        ChartStyle style, string text, double fontSizePoints, Color color, bool bold,
        double maxWidth = double.PositiveInfinity)
    {
        var formatted = new FormattedText(
            text,
            CultureInfo.CurrentUICulture,
            FlowDirection.LeftToRight,
            Typeface(style, bold),
            fontSizePoints * SceneMapper.VirtualPerPoint,
            new SolidColorBrush(color),
            pixelsPerDip: 1.0);
        if (!double.IsNaN(maxWidth) && !double.IsInfinity(maxWidth) && maxWidth > 0)
        {
            formatted.MaxTextWidth = maxWidth;
            formatted.Trimming = TextTrimming.None;
        }
        return formatted;
    }

    public static StreamGeometry SectorGeometry(ChartScene scene, SectorShape sector, SceneMapper mapper)
    {
        var geometry = new StreamGeometry();
        using (var context = geometry.Open())
        {
            var first = mapper.ToVirtual(sector.Points[0]);
            context.BeginFigure(first, isFilled: true, isClosed: true);
            var rest = new List<Point>(sector.Points.Count);
            for (var index = 1; index < sector.Points.Count; index++)
            {
                rest.Add(mapper.ToVirtual(sector.Points[index]));
            }
            context.PolyLineTo(rest, isStroked: true, isSmoothJoin: false);
        }
        geometry.Freeze();
        return geometry;
    }

    public static void DrawBackground(DrawingContext dc, ChartScene scene, SceneMapper mapper)
    {
        if (!string.Equals(scene.Style.Background, ChartStyle.Transparent, StringComparison.OrdinalIgnoreCase))
        {
            var color = ColorUtil.ToColor(scene.Style.Background, Colors.White);
            dc.DrawRectangle(new SolidColorBrush(color), null,
                new Rect(0, 0, mapper.VirtualWidth, mapper.VirtualHeight));
        }
    }

    public static void DrawBase(DrawingContext dc, ChartScene scene, SceneMapper mapper)
    {
        DrawBackground(dc, scene, mapper);
        var edgeBrush = ColorUtil.Brush(scene.Style.EdgeColor, Colors.White);
        var edgeThickness = Math.Max(0.0, mapper.PointsToVirtual(scene.Style.EdgeWidth));
        var edgePen = edgeThickness > 0
            ? new Pen(edgeBrush, edgeThickness) { LineJoin = PenLineJoin.Round, StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round }
            : null;

        foreach (var sector in scene.Sectors)
        {
            var geometry = SectorGeometry(scene, sector, mapper);
            var fill = ColorUtil.Brush(sector.FillColor, Colors.LightGray);
            dc.DrawGeometry(fill, edgePen, geometry);
        }

        DrawTitle(dc, scene, mapper);
        DrawCenterText(dc, scene, mapper);
    }

    private static void DrawTitle(DrawingContext dc, ChartScene scene, SceneMapper mapper)
    {
        var style = scene.Style;
        if (!string.IsNullOrWhiteSpace(style.Title))
        {
            DrawCenteredText(
                dc, style, style.Title, style.TitleFontSize, style.TitleColor,
                mapper.VirtualWidth / 2.0, mapper.VirtualHeight * 0.06, bold: true);
        }
        if (!string.IsNullOrWhiteSpace(style.Subtitle))
        {
            DrawCenteredText(
                dc, style, style.Subtitle, style.SubtitleFontSize, style.SubtitleColor,
                mapper.VirtualWidth / 2.0, mapper.VirtualHeight * 0.125, bold: false);
        }
    }

    private static void DrawCenterText(DrawingContext dc, ChartScene scene, SceneMapper mapper)
    {
        if (string.IsNullOrWhiteSpace(scene.CenterText))
        {
            return;
        }
        var point = mapper.ToVirtual(ChartScene.ChartCenter);
        DrawCenteredText(
            dc, scene.Style, scene.CenterText, scene.Style.CenterFontSize,
            scene.Style.CenterColor, point.X, point.Y, bold: true);
    }

    private static void DrawCenteredText(
        DrawingContext dc, ChartStyle style, string text, double sizePoints,
        string colorHex, double centerX, double centerY, bool bold)
    {
        var formatted = Text(style, text, sizePoints, ColorUtil.ToColor(colorHex, Colors.DimGray), bold);
        dc.DrawText(formatted, new Point(centerX - formatted.Width / 2.0, centerY - formatted.Height / 2.0));
    }

    public static LabelBounds MeasureLabel(
        ChartScene scene, LabelShape label, SceneMapper mapper, bool hover = false)
    {
        var style = scene.Style;
        var fontSize = style.LabelFontSize + (hover ? 1.5 : 0.0);
        var lineStep = fontSize * SceneMapper.VirtualPerPoint * 1.104;
        var maxWidth = 0.0;
        var maxHeight = 0.0;
        foreach (var line in label.Lines)
        {
            var formatted = Text(style, line, fontSize, LabelFallback, bold: true);
            maxWidth = Math.Max(maxWidth, formatted.Width);
            maxHeight = Math.Max(maxHeight, formatted.Height);
        }
        var blockHeight = maxHeight + Math.Max(0, label.Lines.Count - 1) * lineStep;
        var center = mapper.ToVirtual(new PointD(label.TextX, label.Y));
        var textLeft = label.Side > 0 ? center.X : center.X - maxWidth;
        var textTop = center.Y - blockHeight / 2.0;
        var rect = new Rect(textLeft, textTop, Math.Max(1, maxWidth), Math.Max(1, blockHeight));
        return new LabelBounds(rect, textLeft, textTop, maxWidth, blockHeight);
    }

    public static void DrawLabel(
        DrawingContext dc, ChartScene scene, LabelShape label, SceneMapper mapper,
        bool hover = false, bool highlight = false)
    {
        var style = scene.Style;
        var color = ColorUtil.ToColor(label.Color, LabelFallback);
        var lineWidth = Math.Max(0.6, mapper.PointsToVirtual(style.LabelLineWidth));
        var points = label.LeaderPoints.Select(mapper.ToVirtual).ToArray();

        // 1) white underlay so the leader remains visible over a dark sector
        var underlay = new Pen(Brushes.White, lineWidth + 1.6 * SceneMapper.VirtualPerPoint)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round,
            LineJoin = PenLineJoin.Round,
        };
        dc.DrawGeometry(null, underlay, Polyline(points));

        var pen = new Pen(new SolidColorBrush(color), hover ? lineWidth + 0.9 : lineWidth)
        {
            StartLineCap = PenLineCap.Round,
            EndLineCap = PenLineCap.Round,
            LineJoin = PenLineJoin.Round,
        };
        dc.DrawGeometry(null, pen, Polyline(points));

        var bounds = MeasureLabel(scene, label, mapper, hover);
        if (highlight)
        {
            dc.DrawRoundedRectangle(
                new SolidColorBrush(Color.FromArgb(32, 0x0F, 0x76, 0x6E)), null,
                Inflate(bounds.AngleRect, 6), 7, 7);
        }
        else if (LabelOverSector(scene, bounds.AngleRect, mapper))
        {
            dc.PushOpacity(0.82);
            dc.DrawRoundedRectangle(Brushes.White, null, Inflate(bounds.AngleRect, 4), 6, 6);
            dc.Pop();
        }

        var fontSize = style.LabelFontSize + (hover ? 1.5 : 0.0);
        var lineStep = fontSize * SceneMapper.VirtualPerPoint * 1.104;
        for (var index = 0; index < label.Lines.Count; index++)
        {
            var formatted = Text(style, label.Lines[index], fontSize, color, bold: true);
            var x = label.Side > 0
                ? bounds.TextLeft
                : bounds.TextLeft + bounds.Width - formatted.Width;
            var y = bounds.TextTop + index * lineStep;
            dc.DrawText(formatted, new Point(x, y));
        }
    }

    private static Rect Inflate(Rect rect, double amount) =>
        new(rect.X - amount, rect.Y - amount, rect.Width + amount * 2, rect.Height + amount * 2);

    private static StreamGeometry Polyline(IReadOnlyList<Point> points)
    {
        var geometry = new StreamGeometry();
        using (var context = geometry.Open())
        {
            context.BeginFigure(points[0], isFilled: false, isClosed: false);
            context.PolyLineTo(points.Skip(1).ToArray(), isStroked: true, isSmoothJoin: false);
        }
        geometry.Freeze();
        return geometry;
    }

    public static bool LabelOverSector(ChartScene scene, Rect labelRect, SceneMapper mapper)
    {
        foreach (var sector in scene.Sectors)
        {
            var polygon = new List<PointD>(sector.Points.Count);
            foreach (var point in sector.Points)
            {
                var virtualPoint = mapper.ToVirtual(point);
                polygon.Add(new PointD(virtualPoint.X, virtualPoint.Y));
            }
            var rect = new RectD(labelRect.X, labelRect.Y, labelRect.Width, labelRect.Height);
            if (RoseGeometry.PolygonIntersectsRect(polygon, rect))
            {
                return true;
            }
        }
        return false;
    }
}
