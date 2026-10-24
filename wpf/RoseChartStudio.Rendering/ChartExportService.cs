using System.Globalization;
using System.IO;
using System.Text;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using RoseChartStudio.Core.Models;
using SkiaSharp;

namespace RoseChartStudio.Rendering;

/// <summary>Renders a <see cref="ChartScene"/> to PNG/SVG/PDF for export and clipboard.</summary>
public static class ChartExportService
{
    public sealed class ExportOptions
    {
        public int Width { get; init; } = 1200;
        public int Height { get; init; } = 800;
        public int Dpi { get; init; } = 100;
        public bool Transparent { get; init; } = true;
    }

    public static BitmapSource CreatePngBitmap(ChartScene scene, ExportOptions options)
    {
        var width = Math.Max(1, options.Width);
        var height = Math.Max(1, options.Height);
        var visual = new DrawingVisual();
        using (var dc = visual.RenderOpen())
        {
            dc.PushTransform(new ScaleTransform(width / scene.VirtualWidth, height / scene.VirtualHeight));
            if (!options.Transparent)
            {
                dc.DrawRectangle(Brushes.White, null, new Rect(0, 0, scene.VirtualWidth, scene.VirtualHeight));
            }
            var mapper = new SceneMapper(scene.Style);
            ChartDrawing.DrawBase(dc, scene, mapper);
            foreach (var label in scene.Labels)
            {
                ChartDrawing.DrawLabel(dc, scene, label, mapper);
            }
            dc.Pop();
        }
        var bitmap = new RenderTargetBitmap(width, height, options.Dpi, options.Dpi, PixelFormats.Pbgra32);
        bitmap.Render(visual);
        bitmap.Freeze();
        return bitmap;
    }

    public static string ExportPng(ChartScene scene, ExportOptions options, string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? AppContext.BaseDirectory);
        var bitmap = CreatePngBitmap(scene, options);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
        return path;
    }

    public static string ExportSvg(ChartScene scene, ExportOptions options, string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? AppContext.BaseDirectory);
        var mapper = new SceneMapper(scene.Style);
        var builder = new StringBuilder(16 * 1024);
        var width = Math.Max(1, options.Width);
        var height = Math.Max(1, options.Height);
        builder.AppendLine("<?xml version=\"1.0\" encoding=\"UTF-8\"?>");
        builder.AppendLine($"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">");
        if (!options.Transparent)
        {
            builder.AppendLine($"<rect width=\"100%\" height=\"100%\" fill=\"#FFFFFF\"/>");
        }
        builder.AppendLine($"<g transform=\"scale({(width / scene.VirtualWidth).ToString(CultureInfo.InvariantCulture)},{((height / scene.VirtualHeight).ToString(CultureInfo.InvariantCulture))})\">");

        var edgeWidth = scene.Style.EdgeWidth * SceneMapper.VirtualPerPoint;
        foreach (var sector in scene.Sectors)
        {
            var points = sector.Points.Select(mapper.ToVirtual).ToList();
            if (points.Count == 0)
            {
                continue;
            }
            var d = new StringBuilder();
            d.Append('M').Append(F(points[0].X)).Append(' ').Append(F(points[0].Y));
            for (var index = 1; index < points.Count; index++)
            {
                d.Append(" L").Append(F(points[index].X)).Append(' ').Append(F(points[index].Y));
            }
            d.Append(" Z");
            builder.AppendLine($"<path d=\"{d}\" fill=\"{Escape(sector.FillColor)}\" stroke=\"{Escape(scene.Style.EdgeColor)}\" stroke-width=\"{F(edgeWidth)}\" stroke-linejoin=\"round\"/>");
        }

        var style = scene.Style;
        if (!string.IsNullOrWhiteSpace(style.Title))
        {
            var fontSize = style.TitleFontSize * SceneMapper.VirtualPerPoint;
            builder.AppendLine($"<text x=\"{F(mapper.VirtualWidth / 2)}\" y=\"{F(mapper.VirtualHeight * 0.06 + fontSize * 0.38)}\" text-anchor=\"middle\" font-family=\"Microsoft YaHei, Microsoft YaHei UI, sans-serif\" font-size=\"{F(fontSize)}\" font-weight=\"bold\" fill=\"{Escape(style.TitleColor)}\">{Escape(style.Title)}</text>");
        }
        if (!string.IsNullOrWhiteSpace(style.Subtitle))
        {
            var fontSize = style.SubtitleFontSize * SceneMapper.VirtualPerPoint;
            builder.AppendLine($"<text x=\"{F(mapper.VirtualWidth / 2)}\" y=\"{F(mapper.VirtualHeight * 0.125 + fontSize * 0.38)}\" text-anchor=\"middle\" font-family=\"Microsoft YaHei, Microsoft YaHei UI, sans-serif\" font-size=\"{F(fontSize)}\" fill=\"{Escape(style.SubtitleColor)}\">{Escape(style.Subtitle)}</text>");
        }
        if (!string.IsNullOrWhiteSpace(scene.CenterText))
        {
            var center = mapper.ToVirtual(ChartScene.ChartCenter);
            var fontSize = style.CenterFontSize * SceneMapper.VirtualPerPoint;
            builder.AppendLine($"<text x=\"{F(center.X)}\" y=\"{F(center.Y + fontSize * 0.38)}\" text-anchor=\"middle\" font-family=\"Microsoft YaHei, Microsoft YaHei UI, sans-serif\" font-size=\"{F(fontSize)}\" font-weight=\"bold\" fill=\"{Escape(style.CenterColor)}\">{Escape(scene.CenterText)}</text>");
        }

        var labelFont = style.LabelFontSize * SceneMapper.VirtualPerPoint;
        var lineStep = labelFont * 1.104;
        foreach (var label in scene.Labels)
        {
            var points = label.LeaderPoints.Select(mapper.ToVirtual).ToList();
            var pts = string.Join(" ", points.Select(point => $"{F(point.X)},{F(point.Y)}"));
            builder.AppendLine($"<polyline points=\"{pts}\" fill=\"none\" stroke=\"#FFFFFF\" stroke-width=\"{F(style.LabelLineWidth * SceneMapper.VirtualPerPoint + 1.6 * SceneMapper.VirtualPerPoint)}\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>");
            builder.AppendLine($"<polyline points=\"{pts}\" fill=\"none\" stroke=\"{Escape(label.Color)}\" stroke-width=\"{F(style.LabelLineWidth * SceneMapper.VirtualPerPoint)}\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>");

            var bounds = ChartDrawing.MeasureLabel(scene, label, mapper);
            if (ChartDrawing.LabelOverSector(scene, bounds.AngleRect, mapper))
            {
                builder.AppendLine($"<rect x=\"{F(bounds.AngleRect.X - 4)}\" y=\"{F(bounds.AngleRect.Y - 4)}\" width=\"{F(bounds.AngleRect.Width + 8)}\" height=\"{F(bounds.AngleRect.Height + 8)}\" rx=\"6\" fill=\"#FFFFFF\" fill-opacity=\"0.82\"/>");
            }
            var anchor = label.Side > 0 ? "start" : "end";
            var x = label.Side > 0 ? bounds.TextLeft : bounds.TextLeft + bounds.Width;
            for (var index = 0; index < label.Lines.Count; index++)
            {
                builder.AppendLine($"<text x=\"{F(x)}\" y=\"{F(bounds.TextTop + index * lineStep + labelFont * 0.95)}\" text-anchor=\"{anchor}\" font-family=\"Microsoft YaHei, Microsoft YaHei UI, sans-serif\" font-size=\"{F(labelFont)}\" font-weight=\"bold\" fill=\"{Escape(label.Color)}\">{Escape(label.Lines[index])}</text>");
            }
        }
        builder.AppendLine("</g>");
        builder.AppendLine("</svg>");
        File.WriteAllText(path, builder.ToString(), new UTF8Encoding(false));
        return path;
    }

    public static string ExportPdf(ChartScene scene, ExportOptions options, string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? AppContext.BaseDirectory);
        var width = Math.Max(1, options.Width);
        var height = Math.Max(1, options.Height);
        var mapper = new SceneMapper(scene.Style);
        var style = scene.Style;
        using var document = SKDocument.CreatePdf(path);
        var canvas = document.BeginPage(width, height);
        canvas.Scale(width / (float)scene.VirtualWidth, height / (float)scene.VirtualHeight);
        if (!options.Transparent)
        {
            canvas.Clear(SKColors.White);
        }
        using var typeface = SKTypeface.FromFamilyName(style.FontFamily) ?? SKTypeface.Default;
        using var paint = new SKPaint { IsAntialias = true };
        using var font = new SKFont(typeface);
        var edgeWidth = (float)(style.EdgeWidth * SceneMapper.VirtualPerPoint);
        foreach (var sector in scene.Sectors)
        {
            using var sectorPath = new SKPath();
            var points = sector.Points.Select(mapper.ToVirtual).ToList();
            if (points.Count < 3)
            {
                continue;
            }
            sectorPath.MoveTo((float)points[0].X, (float)points[0].Y);
            for (var index = 1; index < points.Count; index++)
            {
                sectorPath.LineTo((float)points[index].X, (float)points[index].Y);
            }
            sectorPath.Close();
            paint.Style = SKPaintStyle.Fill;
            paint.Color = ToSkColor(sector.FillColor, SKColors.LightGray);
            canvas.DrawPath(sectorPath, paint);
            if (edgeWidth > 0)
            {
                paint.Style = SKPaintStyle.Stroke;
                paint.StrokeWidth = edgeWidth;
                paint.Color = ToSkColor(style.EdgeColor, SKColors.White);
                canvas.DrawPath(sectorPath, paint);
            }
        }

        void DrawCentered(string text, double points, string color, double cx, double cy, bool bold)
        {
            DrawOutlinedText(canvas, style, text, points, color, cx, cy, bold, OutlinedTextAlign.Center, true);
        }

        if (!string.IsNullOrWhiteSpace(style.Title))
        {
            DrawCentered(style.Title, style.TitleFontSize, style.TitleColor,
                mapper.VirtualWidth / 2, mapper.VirtualHeight * 0.06 + style.TitleFontSize * SceneMapper.VirtualPerPoint * 0.36, true);
        }
        if (!string.IsNullOrWhiteSpace(style.Subtitle))
        {
            DrawCentered(style.Subtitle, style.SubtitleFontSize, style.SubtitleColor,
                mapper.VirtualWidth / 2, mapper.VirtualHeight * 0.125 + style.SubtitleFontSize * SceneMapper.VirtualPerPoint * 0.36, false);
        }
        if (!string.IsNullOrWhiteSpace(scene.CenterText))
        {
            var center = mapper.ToVirtual(ChartScene.ChartCenter);
            DrawCentered(scene.CenterText, style.CenterFontSize, style.CenterColor, center.X, center.Y + style.CenterFontSize * SceneMapper.VirtualPerPoint * 0.36, true);
        }

        var lineWidth = (float)(style.LabelLineWidth * SceneMapper.VirtualPerPoint);
        var labelPoints = (float)(style.LabelFontSize * SceneMapper.VirtualPerPoint);
        foreach (var label in scene.Labels)
        {
            var points = label.LeaderPoints.Select(mapper.ToVirtual).ToList();
            using var linePath = new SKPath();
            linePath.MoveTo((float)points[0].X, (float)points[0].Y);
            for (var index = 1; index < points.Count; index++)
            {
                linePath.LineTo((float)points[index].X, (float)points[index].Y);
            }
            paint.Style = SKPaintStyle.Stroke;
            paint.StrokeWidth = lineWidth + (float)(1.6 * SceneMapper.VirtualPerPoint);
            paint.Color = SKColors.White;
            canvas.DrawPath(linePath, paint);
            paint.StrokeWidth = lineWidth;
            paint.Color = ToSkColor(label.Color, SKColors.DimGray);
            canvas.DrawPath(linePath, paint);

            var bounds = ChartDrawing.MeasureLabel(scene, label, mapper);
            if (ChartDrawing.LabelOverSector(scene, bounds.AngleRect, mapper))
            {
                paint.Style = SKPaintStyle.Fill;
                paint.Color = new SKColor(255, 255, 255, 210);
                canvas.DrawRoundRect(new SKRect(
                    (float)bounds.AngleRect.X - 4, (float)bounds.AngleRect.Y - 4,
                    (float)(bounds.AngleRect.X + bounds.AngleRect.Width) + 4,
                    (float)(bounds.AngleRect.Y + bounds.AngleRect.Height) + 4), 6, 6, paint);
            }
            var lineStep = labelPoints * 1.104;
            var x = label.Side > 0 ? bounds.TextLeft : bounds.TextLeft + bounds.Width;
            var textAlign = label.Side > 0 ? OutlinedTextAlign.Left : OutlinedTextAlign.Right;
            for (var index = 0; index < label.Lines.Count; index++)
            {
                var y = bounds.TextTop + index * lineStep;
                DrawOutlinedText(canvas, style, label.Lines[index], style.LabelFontSize, label.Color, x, y, true, textAlign);
            }
        }
        document.EndPage();
        document.Close();
        return path;
    }

    private enum OutlinedTextAlign { Left, Center, Right }

    private static void DrawOutlinedText(
        SKCanvas canvas, ChartStyle style, string text, double points, string color,
        double x, double y, bool bold, OutlinedTextAlign align, bool verticalCenter = false)
    {
        if (string.IsNullOrEmpty(text))
        {
            return;
        }
        var formatted = ChartDrawing.Text(style, text, points, ColorUtil.ToColor(color, Colors.DimGray), bold);
        var left = align switch
        {
            OutlinedTextAlign.Center => x - formatted.Width / 2.0,
            OutlinedTextAlign.Right => x - formatted.Width,
            _ => x,
        };
        var top = verticalCenter ? y - formatted.Height / 2.0 : y;
        var geometry = formatted.BuildGeometry(new Point(left, top));
        if (geometry is null)
        {
            return;
        }
        var flattened = geometry.GetFlattenedPathGeometry(0.05, ToleranceType.Absolute);
        using var paint = new SKPaint
        {
            Style = SKPaintStyle.Fill,
            IsAntialias = true,
            Color = ToSkColor(color, SKColors.DimGray),
        };
        using var path = new SKPath
        {
            FillType = flattened.FillRule == FillRule.EvenOdd
                ? SKPathFillType.EvenOdd
                : SKPathFillType.Winding,
        };
        foreach (var figure in flattened.Figures)
        {
            path.MoveTo((float)figure.StartPoint.X, (float)figure.StartPoint.Y);
            foreach (var segment in figure.Segments)
            {
                switch (segment)
                {
                    case PolyLineSegment polyLine:
                        foreach (var point in polyLine.Points)
                        {
                            path.LineTo((float)point.X, (float)point.Y);
                        }
                        break;
                    case LineSegment line:
                        path.LineTo((float)line.Point.X, (float)line.Point.Y);
                        break;
                    case BezierSegment bezier:
                        path.CubicTo(
                            (float)bezier.Point1.X, (float)bezier.Point1.Y,
                            (float)bezier.Point2.X, (float)bezier.Point2.Y,
                            (float)bezier.Point3.X, (float)bezier.Point3.Y);
                        break;
                    case QuadraticBezierSegment quadratic:
                        path.QuadTo(
                            (float)quadratic.Point1.X, (float)quadratic.Point1.Y,
                            (float)quadratic.Point2.X, (float)quadratic.Point2.Y);
                        break;
                }
            }
            if (figure.IsClosed)
            {
                path.Close();
            }
        }
        canvas.DrawPath(path, paint);
    }
    private static string F(double value) => value.ToString("0.###", CultureInfo.InvariantCulture);

    private static string Escape(string text) => System.Security.SecurityElement.Escape(text) ?? text;

    private static SKColor ToSkColor(string hex, SKColor fallback)
    {
        var color = ColorUtil.ToColor(hex, Colors.Transparent);
        return color == Colors.Transparent && !string.Equals(hex, "#000000", StringComparison.OrdinalIgnoreCase)
            ? fallback
            : new SKColor(color.R, color.G, color.B, color.A);
    }
}
