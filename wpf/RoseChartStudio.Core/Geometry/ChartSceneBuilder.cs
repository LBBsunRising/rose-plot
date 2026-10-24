using RoseChartStudio.Core.Formatting;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Geometry;

/// <summary>
/// Builds the renderer-agnostic chart scene: sector polygons, label positions
/// and formatted label text. All values are in v2 chart data coordinates, so
/// every renderer (screen, PNG, SVG, PDF) draws the exact same geometry.
/// </summary>
public static class ChartSceneBuilder
{
    private sealed class PendingLabel
    {
        public required string Label { get; init; }
        public int Value { get; init; }
        public double OuterRadius { get; init; }
        public double DirectionX { get; init; }
        public double DirectionY { get; init; }
        public double AnchorX { get; init; }
        public double AnchorY { get; init; }
        public int Side { get; init; }
        public double DesiredY { get; set; }
        public double LabelY { get; set; }
    }

    public static ChartScene Build(ChartSpec spec)
    {
        var style = spec.Style;
        var pairs = spec.ResolvePairs();
        if (pairs.Count == 0)
        {
            return new ChartScene
            {
                Style = style,
                Sectors = Array.Empty<SectorShape>(),
                Labels = Array.Empty<LabelShape>(),
                Total = 0,
                Maximum = 0,
                CenterText = null,
            };
        }

        var total = pairs.Sum(pair => pair.Value);
        var maximum = pairs.Max(pair => pair.Value);
        var sectors = new List<SectorShape>(pairs.Count);
        var pending = new List<PendingLabel>(pairs.Count);
        var startAngle = style.StartAngle;

        foreach (var pair in pairs)
        {
            var span = pair.Value / (double)total * 360.0;
            var endAngle = startAngle - span;
            var gap = Math.Min(style.GapMaxDegrees, span * style.GapRatio);
            double theta1, theta2;
            if (span > gap)
            {
                theta1 = endAngle + gap / 2.0;
                theta2 = startAngle - gap / 2.0;
            }
            else
            {
                theta1 = endAngle;
                theta2 = startAngle;
            }

            var outerRadius = style.InnerRadius +
                (style.OuterRadius - style.InnerRadius) * (pair.Value / (double)maximum);
            var fill = spec.FillColors.TryGetValue(pair.Label, out var fillColor)
                ? fillColor
                : "#CCCCCC";
            var points = RoseGeometry.RoundedAnnularSector(
                0.0, -0.05, style.InnerRadius, outerRadius, theta1, theta2, style.CornerRadius);

            var middle = (startAngle + endAngle) / 2.0;
            var radians = middle * Math.PI / 180.0;
            var directionX = Math.Cos(radians);
            var directionY = Math.Sin(radians);
            var anchorRadius = outerRadius + 0.012;
            var anchorX = directionX * anchorRadius;
            var anchorY = -0.05 + directionY * anchorRadius;
            var side = directionX >= 0.0 ? 1 : -1;

            sectors.Add(new SectorShape
            {
                Label = pair.Label,
                Value = pair.Value,
                Percent = pair.Value / (double)total * 100.0,
                FillColor = fill,
                OuterRadius = outerRadius,
                Theta1 = theta1,
                Theta2 = theta2,
                MidAngle = middle,
                DirectionX = directionX,
                DirectionY = directionY,
                Anchor = new PointD(anchorX, anchorY),
                Points = points,
            });

            pending.Add(new PendingLabel
            {
                Label = pair.Label,
                Value = pair.Value,
                OuterRadius = outerRadius,
                DirectionX = directionX,
                DirectionY = directionY,
                AnchorX = anchorX,
                AnchorY = anchorY,
                Side = side,
            });

            startAngle = endAngle;
        }

        SpreadLabels(pending, MinimumGap(style));

        var labels = new List<LabelShape>(pending.Count);
        foreach (var item in pending)
        {
            var extension = (item.Side > 0 ? 0.15 : 0.65) * style.LabelWireScale;
            var elbowX = item.AnchorX + item.DirectionX * extension;
            var lineEndX = elbowX + item.Side * 0.35 * style.LabelWireScale;
            lineEndX = item.Side > 0 ? Math.Min(1.42, lineEndX) : Math.Max(-1.42, lineEndX);
            var fill = spec.FillColors.TryGetValue(item.Label, out var fillColor)
                ? fillColor
                : "#CCCCCC";
            var color = spec.LabelColors.TryGetValue(item.Label, out var labelColor)
                ? labelColor
                : fill;
            var percent = item.Value / (double)total * 100.0;

            var label = new LabelShape
            {
                Label = item.Label,
                Value = item.Value,
                Percent = percent,
                Side = item.Side,
                DirectionX = item.DirectionX,
                DirectionY = item.DirectionY,
                AnchorX = item.AnchorX,
                AnchorY = item.AnchorY,
                AutoY = item.LabelY,
                AutoLineEndX = lineEndX,
                Y = item.LabelY,
                LineEndX = lineEndX,
                ElbowX = elbowX,
                Color = color,
                Lines = ChartText.LabelLines(style, item.Label, item.Value, percent),
                TextGap = style.LabelTextGap,
            };
            labels.Add(label);
        }

        var scene = new ChartScene
        {
            Style = style,
            Sectors = sectors,
            Labels = labels,
            Total = total,
            Maximum = maximum,
            CenterText = ChartText.CenterText(style, total, pairs.Count, maximum),
        };
        ApplyOffsets(scene, spec.LayoutOffsets);
        return scene;
    }

    private static double MinimumGap(ChartStyle style)
    {
        var lines = 1 + (style.ShowPercent ? 1 : 0);
        var dataPerPoint = 2.40 / (style.FigureHeight * 0.82 * 72.0);
        var gap = (lines * 1.28 - 0.18) * style.LabelFontSize * dataPerPoint;
        return Math.Max(0.10, Math.Min(0.42, gap));
    }

    private static void SpreadLabels(List<PendingLabel> pending, double minGap)
    {
        foreach (var side in new[] { -1, 1 })
        {
            var items = pending.Where(item => item.Side == side).ToList();
            if (items.Count == 0)
            {
                continue;
            }
            foreach (var item in items)
            {
                item.DesiredY = -0.05 + item.DirectionY * (item.OuterRadius + 0.10);
            }
            items.Sort((left, right) => left.DesiredY.CompareTo(right.DesiredY));
            var positions = new List<double>(items.Count);
            foreach (var item in items)
            {
                positions.Add(positions.Count == 0
                    ? item.DesiredY
                    : Math.Max(item.DesiredY, positions[^1] + minGap));
            }
            const double lower = -1.06;
            const double upper = 1.02;
            if (positions[^1] > upper)
            {
                var shift = positions[^1] - upper;
                for (var index = 0; index < positions.Count; index++)
                {
                    positions[index] -= shift;
                }
            }
            for (var index = positions.Count - 2; index >= 0; index--)
            {
                positions[index] = Math.Min(positions[index], positions[index + 1] - minGap);
            }
            if (positions[0] < lower)
            {
                var shift = lower - positions[0];
                for (var index = 0; index < positions.Count; index++)
                {
                    positions[index] += shift;
                }
                var overflow = positions[^1] - upper;
                if (overflow > 0)
                {
                    for (var index = 0; index < positions.Count; index++)
                    {
                        positions[index] -= overflow;
                    }
                }
            }
            for (var index = 0; index < items.Count; index++)
            {
                items[index].LabelY = positions[index];
            }
        }
    }

    public static void MoveLabel(ChartScene scene, string label, double y, double lineEndX)
    {
        var shape = scene.FindLabel(label);
        if (shape is null)
        {
            return;
        }
        shape.Y = Math.Clamp(y, -1.16, 1.14);
        shape.LineEndX = Math.Clamp(lineEndX, -1.46, 1.46);
    }

    public static void ResetLabel(ChartScene scene, string label)
    {
        var shape = scene.FindLabel(label);
        if (shape is null)
        {
            return;
        }
        shape.Y = shape.AutoY;
        shape.LineEndX = shape.AutoLineEndX;
    }

    public static void ResetAllLabels(ChartScene scene)
    {
        foreach (var shape in scene.Labels)
        {
            shape.Y = shape.AutoY;
            shape.LineEndX = shape.AutoLineEndX;
        }
    }

    public static void ApplyOffsets(ChartScene scene, IReadOnlyDictionary<string, LayoutOffset> offsets)
    {
        foreach (var shape in scene.Labels)
        {
            if (offsets.TryGetValue(shape.Label, out var offset))
            {
                shape.Y = Math.Clamp(shape.AutoY + offset.Dy, -1.16, 1.14);
                shape.LineEndX = Math.Clamp(shape.AutoLineEndX + offset.Dx, -1.46, 1.46);
            }
        }
    }

    public static Dictionary<string, LayoutOffset> CollectOffsets(ChartScene scene)
    {
        var result = new Dictionary<string, LayoutOffset>(StringComparer.Ordinal);
        foreach (var shape in scene.Labels)
        {
            var offset = shape.Offset;
            if (Math.Abs(offset.Dx) > 1e-4 || Math.Abs(offset.Dy) > 1e-4)
            {
                result[shape.Label] = offset;
            }
        }
        return result;
    }
}
