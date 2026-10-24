using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;
using RoseChartStudio.Core.Palettes;
using RoseChartStudio.Rendering;

namespace RoseChartStudio.PerfHarness;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
        var window = new HarnessWindow();
        window.Show();
        app.Run();
    }
}

internal sealed class HarnessWindow : Window
{
    private readonly RoseChartView _view = new();
    private readonly List<double> _frameTimes = new();
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private readonly ChartStyle _style = new() { FigureWidth = 12, FigureHeight = 8, Title = "12 类别性能测试" };
    private IReadOnlyList<string> _labels = Array.Empty<string>();
    private IReadOnlyList<int> _values = Array.Empty<int>();
    private Dictionary<string, string> _fills = new();
    private Dictionary<string, string> _labelColors = new();
    private ChartScene _scene = null!;
    private readonly string _outputDirectory =
        Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "_qa", "perf"));

    public HarnessWindow()
    {
        Title = "RoseChart Perf Harness";
        Width = 1600;
        Height = 1000;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Background = Brushes.White;
        var host = new Grid { Width = 1200, Height = 800, Background = Brushes.White };
        host.Children.Add(_view);
        Content = new Viewbox { Child = host, Stretch = Stretch.Uniform };
        BuildScene12();
        _view.SetScene(_scene);
        CompositionTarget.Rendering += (_, _) => _frameTimes.Add(_clock.Elapsed.TotalMilliseconds);
        Loaded += async (_, _) => await RunAsync();
    }

    private void BuildScene12()
    {
        _labels = new[]
        {
            "软件开发", "MES改造", "视觉改造", "数据平台", "运控改造", "方案review",
            "iPhone扫码", "测试工程", "接口联调", "算法优化", "产品设计", "运维支持",
        };
        _values = new[] { 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1 };
        var palette = PaletteLibrary.ById("tech_neon");
        _fills = PaletteLibrary.AssignColors(palette, _labels);
        _labelColors = _labels.ToDictionary(
            label => label,
            label => PaletteLibrary.LabelColor(_fills[label], "auto"));
        _scene = BuildCurrentScene(_style);
    }

    private ChartScene BuildCurrentScene(ChartStyle style) => ChartSceneBuilder.Build(new ChartSpec
    {
        Labels = _labels.ToList(),
        Values = _values.ToList(),
        Style = style,
        FillColors = new Dictionary<string, string>(_fills),
        LabelColors = new Dictionary<string, string>(_labelColors),
    });

    private async Task RunAsync()
    {
        await Task.Delay(700);
        var label = _scene.Labels[0];
        var baseY = label.Y;
        var baseX = label.LineEndX;
        _frameTimes.Clear();
        var updateTimes = new List<double>();
        var dragStart = _clock.Elapsed.TotalMilliseconds;
        var ticks = 0;
        var timer = new DispatcherTimer(DispatcherPriority.Render) { Interval = TimeSpan.FromMilliseconds(4) };
        var done = new TaskCompletionSource();
        timer.Tick += (_, _) =>
        {
            var phase = ticks / 6.0;
            var start = Stopwatch.GetTimestamp();
            _view.MoveLabelForPerf(
                label.Label,
                baseY + 0.10 * Math.Sin(phase),
                baseX + 0.06 * Math.Cos(phase));
            updateTimes.Add((Stopwatch.GetTimestamp() - start) * 1000.0 / Stopwatch.Frequency);
            ticks++;
            if (ticks >= 180)
            {
                timer.Stop();
                done.TrySetResult();
            }
        };
        timer.Start();
        await done.Task;
        var dragEnd = _clock.Elapsed.TotalMilliseconds;
        await Task.Delay(200);
        var dragFrames = _frameTimes.Where(time => time >= dragStart && time <= dragEnd).ToList();
        var drag = new
        {
            name = "label-drag-12",
            update_count = updateTimes.Count,
            update_p50_ms = Percentile(updateTimes, 0.50),
            update_p95_ms = Percentile(updateTimes, 0.95),
            update_max_ms = updateTimes.Max(),
            frame_count = dragFrames.Count,
            duration_ms = dragEnd - dragStart,
            fps = dragFrames.Count / ((dragEnd - dragStart) / 1000.0),
            frame_p95_ms = Percentile(Deltas(dragFrames), 0.95),
        };

        await Task.Delay(200);
        _frameTimes.Clear();
        var rebuildTimes = new List<double>();
        var styleStart = _clock.Elapsed.TotalMilliseconds;
        for (var index = 0; index < 60; index++)
        {
            var style = _style.Clone();
            style.InnerRadius = 0.20 + index * 0.004;
            var start = Stopwatch.GetTimestamp();
            _scene = BuildCurrentScene(style);
            _view.SetScene(_scene);
            rebuildTimes.Add((Stopwatch.GetTimestamp() - start) * 1000.0 / Stopwatch.Frequency);
            await Task.Delay(16);
        }
        var styleEnd = _clock.Elapsed.TotalMilliseconds;
        await Task.Delay(200);
        var styleFrames = _frameTimes.Where(time => time >= styleStart && time <= styleEnd).ToList();
        var rebuild = new
        {
            name = "style-rebuild-12",
            build_count = rebuildTimes.Count,
            build_p50_ms = Percentile(rebuildTimes, 0.50),
            build_p95_ms = Percentile(rebuildTimes, 0.95),
            build_max_ms = rebuildTimes.Max(),
            frame_count = styleFrames.Count,
            duration_ms = styleEnd - styleStart,
            fps = styleFrames.Count / ((styleEnd - styleStart) / 1000.0),
            frame_p95_ms = Percentile(Deltas(styleFrames), 0.95),
        };

        await Task.Delay(200);
        _frameTimes.Clear();
        var resizeStart = _clock.Elapsed.TotalMilliseconds;
        for (var index = 0; index < 40; index++)
        {
            Width = 1600 - (index % 20) * 8;
            Height = 1000 - (index % 20) * 6;
            await Task.Delay(25);
        }
        var resizeEnd = _clock.Elapsed.TotalMilliseconds;
        await Task.Delay(250);
        var resizeFrames = _frameTimes.Where(time => time >= resizeStart && time <= resizeEnd).ToList();
        var resize = new
        {
            name = "window-resize",
            step_count = 40,
            frame_count = resizeFrames.Count,
            duration_ms = resizeEnd - resizeStart,
            fps = resizeFrames.Count / ((resizeEnd - resizeStart) / 1000.0),
            frame_p95_ms = Percentile(Deltas(resizeFrames), 0.95),
        };

        var report = new
        {
            environment = "WPF net10.0-windows, 1600x1000 window, viewbox-scaled 1200x800 chart",
            drag,
            rebuild,
            resize,
        };
        var json = JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
        Directory.CreateDirectory(_outputDirectory);
        File.WriteAllText(Path.Combine(_outputDirectory, "wpf_perf.json"), json);
        Console.WriteLine(json);
        Close();
        Application.Current.Shutdown();
    }

    private static List<double> Deltas(List<double> times)
    {
        var result = new List<double>();
        for (var index = 1; index < times.Count; index++)
        {
            result.Add(times[index] - times[index - 1]);
        }
        return result;
    }

    private static double Percentile(List<double> values, double percentile)
    {
        if (values.Count == 0)
        {
            return double.NaN;
        }
        var ordered = values.OrderBy(value => value).ToList();
        var index = (int)Math.Ceiling(percentile * ordered.Count) - 1;
        return ordered[Math.Clamp(index, 0, ordered.Count - 1)];
    }
}
