using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace RoseChartStudio.App;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        ConfigureWritableTempDirectory();
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += (_, args) =>
        {
            TryLog(args.ExceptionObject as Exception);
        };
    }

    /// <summary>
    /// ClosedXML / DocumentFormat.OpenXml can create temporary files while opening a
    /// workbook. In restricted environments %TEMP% may be read-only, which surfaces as
    /// "Access to the path '...tmp' is denied". Redirect TMP/TEMP to a writable folder
    /// next to the executable (or LocalAppData) before the first Excel read.
    /// </summary>
    private static void ConfigureWritableTempDirectory()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, ".tmp"),
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "RoseChartStudio",
                "temp"),
        };
        foreach (var candidate in candidates)
        {
            try
            {
                Directory.CreateDirectory(candidate);
                var probe = Path.Combine(candidate, $".probe-{Guid.NewGuid():N}");
                File.WriteAllText(probe, "ok");
                File.Delete(probe);
                Environment.SetEnvironmentVariable("TMP", candidate);
                Environment.SetEnvironmentVariable("TEMP", candidate);
                Environment.SetEnvironmentVariable("TMPDIR", candidate);
                return;
            }
            catch
            {
                // Try the next location; never prevent the app from starting.
            }
        }
    }

    private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        TryLog(e.Exception);
        MessageBox.Show(
            e.Exception?.Message ?? "发生未知错误。",
            "玫瑰图工坊",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        e.Handled = true;
    }

    private static void TryLog(Exception? exception)
    {
        if (exception is null)
        {
            return;
        }
        try
        {
            var path = Path.Combine(AppContext.BaseDirectory, "rosechart_error.log");
            File.AppendAllText(
                path,
                $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {exception}{Environment.NewLine}{Environment.NewLine}");
        }
        catch
        {
            // logging must never take the app down
        }
    }
}
