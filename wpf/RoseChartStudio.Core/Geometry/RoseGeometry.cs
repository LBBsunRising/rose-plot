using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Geometry;

/// <summary>Rose geometry helpers: annular sectors, polar math and polygon tests.</summary>
public static class RoseGeometry
{
    public const double CenterX = 0.0;
    public const double CenterY = -0.05;

    public static PointD PolarPoint(double cx, double cy, double radius, double angleDegrees)
    {
        var radians = angleDegrees * Math.PI / 180.0;
        return new PointD(cx + radius * Math.Cos(radians), cy + radius * Math.Sin(radians));
    }

    /// <summary>
    /// Sampled outline of a softly rounded annular sector. The sampling mirrors the
    /// v2 matplotlib path (outer arc, quadratic corners, inner arc) closely enough
    /// that both renderers and exports share identical geometry.
    /// </summary>
    public static List<PointD> RoundedAnnularSector(
        double cx,
        double cy,
        double innerRadius,
        double outerRadius,
        double theta1,
        double theta2,
        double cornerRadiusMax)
    {
        var points = new List<PointD>(96);
        var spanRadians = (theta2 - theta1) * Math.PI / 180.0;
        var thickness = outerRadius - innerRadius;
        var cornerRadius = Math.Min(
            Math.Max(0.0, cornerRadiusMax),
            Math.Min(thickness * 0.46, Math.Min(
                innerRadius * Math.Abs(spanRadians) * 0.25,
                outerRadius * Math.Abs(spanRadians) * 0.25)));

        var outerInset = outerRadius > 0 ? cornerRadius / outerRadius * 180.0 / Math.PI : 0.0;
        var innerInset = innerRadius > 0 ? cornerRadius / innerRadius * 180.0 / Math.PI : 0.0;

        var outerStart = theta1 + outerInset;
        var outerEnd = theta2 - outerInset;
        var innerStart = theta2 - innerInset;
        var innerEnd = theta1 + innerInset;

        var outerSteps = Math.Max(6, (int)(Math.Abs(outerEnd - outerStart) / 3.0) + 1);
        for (var index = 0; index < outerSteps; index++)
        {
            var angle = outerStart + (outerEnd - outerStart) * index / (outerSteps - 1.0);
            points.Add(PolarPoint(cx, cy, outerRadius, angle));
        }

        // Corner at theta2 (outer -> inner), quadratic curve.
        AppendQuadratic(
            points,
            PolarPoint(cx, cy, outerRadius, theta2),
            PolarPoint(cx, cy, outerRadius - cornerRadius, theta2));
        points.Add(PolarPoint(cx, cy, innerRadius + cornerRadius, theta2));
        AppendQuadratic(
            points,
            PolarPoint(cx, cy, innerRadius, theta2),
            PolarPoint(cx, cy, innerRadius, innerStart));

        var innerSteps = Math.Max(6, (int)(Math.Abs(innerStart - innerEnd) / 3.0) + 1);
        for (var index = 1; index < innerSteps; index++)
        {
            var angle = innerStart + (innerEnd - innerStart) * index / (innerSteps - 1.0);
            points.Add(PolarPoint(cx, cy, innerRadius, angle));
        }

        AppendQuadratic(
            points,
            PolarPoint(cx, cy, innerRadius, theta1),
            PolarPoint(cx, cy, innerRadius + cornerRadius, theta1));
        points.Add(PolarPoint(cx, cy, outerRadius - cornerRadius, theta1));
        AppendQuadratic(
            points,
            PolarPoint(cx, cy, outerRadius, theta1),
            PolarPoint(cx, cy, outerRadius, theta1));
        if (points.Count > 0)
        {
            points.Add(points[0]);
        }
        return points;
    }

    private static void AppendQuadratic(
        List<PointD> target, PointD control, PointD end, int steps = 8)
    {
        if (target.Count == 0)
        {
            target.Add(control);
        }
        var start = target[^1];
        for (var index = 1; index <= steps; index++)
        {
            var t = index / (double)steps;
            var mt = 1.0 - t;
            target.Add(new PointD(
                mt * mt * start.X + 2 * mt * t * control.X + t * t * end.X,
                mt * mt * start.Y + 2 * mt * t * control.Y + t * t * end.Y));
        }
    }

    /// <summary>Even-odd polygon containment (sector hit-testing, label plates).</summary>
    public static bool PointInPolygon(IReadOnlyList<PointD> polygon, PointD point)
    {
        if (polygon.Count < 3)
        {
            return false;
        }
        var inside = false;
        for (int i = 0, j = polygon.Count - 1; i < polygon.Count; j = i++)
        {
            var pi = polygon[i];
            var pj = polygon[j];
            if ((pi.Y > point.Y) != (pj.Y > point.Y) &&
                point.X < (pj.X - pi.X) * (point.Y - pi.Y) / (pj.Y - pi.Y + 1e-12) + pi.X)
            {
                inside = !inside;
            }
        }
        return inside;
    }

    public static bool PolygonIntersectsRect(IReadOnlyList<PointD> polygon, RectD rect)
    {
        if (polygon.Count == 0)
        {
            return false;
        }
        foreach (var point in polygon)
        {
            if (rect.Contains(point))
            {
                return true;
            }
        }
        var corners = new[]
        {
            new PointD(rect.X, rect.Y),
            new PointD(rect.Right, rect.Y),
            new PointD(rect.Right, rect.Bottom),
            new PointD(rect.X, rect.Bottom),
        };
        foreach (var corner in corners)
        {
            if (PointInPolygon(polygon, corner))
            {
                return true;
            }
        }
        return false;
    }
}
