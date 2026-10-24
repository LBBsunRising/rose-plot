using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace RoseChart
{
    internal static class Program
    {
        private const string RuntimeDir = ".venv";
        private const string RuntimeExe = "pythonw.exe";
        private const string AppEntry = "app.py";

        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            if (string.IsNullOrEmpty(baseDir))
            {
                baseDir = Path.GetDirectoryName(Application.ExecutablePath);
            }
            baseDir = baseDir.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (string.IsNullOrEmpty(baseDir))
            {
                baseDir = Path.GetPathRoot(Application.ExecutablePath);
            }

            string pythonw = Path.Combine(Path.Combine(baseDir, RuntimeDir), RuntimeExe);
            string appPy = Path.Combine(baseDir, AppEntry);

            bool hasPython = File.Exists(pythonw);
            bool hasApp = File.Exists(appPy);
            if (!hasPython || !hasApp)
            {
                string missing = string.Empty;
                if (!hasPython) { missing += "\n  - .venv\\pythonw.exe"; }
                if (!hasApp) { missing += "\n  - app.py"; }
                MessageBox.Show(
                    "未找到便携运行环境，无法启动。\n\n请连同 .venv 文件夹一起复制整个程序目录后再运行。"
                    + "\n\n缺少文件：" + missing,
                    "RoseChart 启动失败",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return;
            }

            // Keep third-party logs (IME debug logs etc.) out of the portable folder.
            string workDir = baseDir;
            try
            {
                string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if (!string.IsNullOrEmpty(localApp))
                {
                    string appDataDir = Path.Combine(localApp, "RoseChartStudio");
                    Directory.CreateDirectory(appDataDir);
                    workDir = appDataDir;
                }
            }
            catch { workDir = baseDir; }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonw;
                psi.Arguments = "-B \"" + appPy + "\"";
                psi.WorkingDirectory = workDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;

                // Portable runtime: ignore conda / python environment leaked from the host.
                RemoveEnv(psi, "CONDA_PREFIX");
                RemoveEnv(psi, "CONDA_DEFAULT_ENV");
                RemoveEnv(psi, "CONDA_PROMPT_MODIFIER");
                RemoveEnv(psi, "CONDA_SHLVL");
                RemoveEnv(psi, "_CE_CONDA");
                RemoveEnv(psi, "_CE_M");
                RemoveEnv(psi, "PYTHONHOME");
                RemoveEnv(psi, "PYTHONPATH");

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "启动 Python 运行时失败。\n\n" + ex.Message
                    + "\n\n请确认已复制完整的 .venv 文件夹，或改用 start.bat 启动。",
                    "RoseChart 启动失败",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
            }
        }

        private static void RemoveEnv(ProcessStartInfo psi, string name)
        {
            try
            {
                if (psi.EnvironmentVariables.ContainsKey(name))
                {
                    psi.EnvironmentVariables.Remove(name);
                }
            }
            catch (Exception)
            {
            }
        }
    }
}