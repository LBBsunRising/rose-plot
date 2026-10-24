namespace RoseChartStudio.Core.Models;

/// <summary>Device-independent point in chart data coordinates.</summary>
public readonly record struct PointD(double X, double Y)
{
    public static PointD operator +(PointD a, PointD b) => new(a.X + b.X, a.Y + b.Y);
    public static PointD operator -(PointD a, PointD b) => new(a.X - b.X, a.Y - b.Y);
    public static PointD operator *(PointD a, double factor) => new(a.X * factor, a.Y * factor);
    public double DistanceTo(PointD other) =>
        Math.Sqrt((X - other.X) * (X - other.X) + (Y - other.Y) * (Y - other.Y));
}

/// <summary>Axis-aligned rectangle in data coordinates.</summary>
public readonly record struct RectD(double X, double Y, double Width, double Height)
{
    public double Right => X + Width;
    public double Bottom => Y + Height;
    public bool Contains(PointD point) =>
        point.X >= X && point.X <= Right && point.Y >= Y && point.Y <= Bottom;
    public bool IntersectsWith(RectD other) =>
        other.X <= Right && other.Right >= X && other.Y <= Bottom && other.Bottom >= Y;
    public bool Contains(RectD other) =>
        other.X >= X && other.Right <= Right && other.Y >= Y && other.Bottom <= Bottom;
}
