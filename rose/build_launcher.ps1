# RoseChart.exe launcher build script
#
# Compiles the tiny C# launcher (winexe, no console window) that starts the
# portable Python runtime shipped next to it:  .venv\pythonw.exe -B app.py
# The application icon (assets\icon.ico) is embedded as the exe icon.
#
# Usage:   pwsh -File .\build_launcher.ps1
#          powershell -ExecutionPolicy Bypass -File .\build_launcher.ps1
#
# The script is idempotent: re-running it regenerates the sources only when
# they changed and rebuilds RoseChart.exe in place.

[CmdletBinding()]
param(
    [string]$OutFile = (Join-Path $PSScriptRoot 'RoseChart.exe'),
    [switch]$NoIcon
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }

$iconPath = Join-Path $root 'assets\icon.ico'
if (-not $NoIcon -and -not (Test-Path -LiteralPath $iconPath)) {
    throw "Missing icon: $iconPath`nGenerate it first with:  .venv\python.exe _qa\packaging\make_icon.py"
}

# ---------------------------------------------------------------- locate csc.exe
$cscCandidates = @(
    (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
    (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
)
$csc = $cscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $csc) {
    $csc = Get-ChildItem -Path (Join-Path $env:WINDIR 'Microsoft.NET\Framework*\v4.*\csc.exe') `
        -ErrorAction SilentlyContinue | Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $csc) {
    throw 'csc.exe (.NET Framework 4.x C# compiler) was not found. Install .NET Framework 4.x or build on a machine that has it.'
}
Write-Host "[build] csc      : $csc"

# ------------------------------------------------------------- write C# source
$srcDir = Join-Path $root '_qa\packaging\build'
New-Item -ItemType Directory -Force -Path $srcDir | Out-Null
$srcPath = Join-Path $srcDir 'RoseChartLauncher.cs'

$source = @'
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
'@

$encoding = New-Object System.Text.UTF8Encoding($true)   # UTF-8 with BOM: csc reads Chinese strings correctly
$existing = if (Test-Path -LiteralPath $srcPath) { [System.IO.File]::ReadAllText($srcPath) } else { $null }
if ($existing -ne $source) {
    [System.IO.File]::WriteAllText($srcPath, $source, $encoding)
    Write-Host "[build] source   : written $srcPath"
} else {
    Write-Host "[build] source   : unchanged $srcPath"
}

# ------------------------------------------------------------------- compile
$outFull = [System.IO.Path]::GetFullPath($OutFile)
$args = @(
    '/nologo',
    '/target:winexe',
    '/platform:anycpu',
    '/optimize+',
    '/reference:System.dll',
    '/reference:System.Drawing.dll',
    '/reference:System.Windows.Forms.dll'
)
if (-not $NoIcon) { $args += "/win32icon:$iconPath" }
$args += "/out:$outFull"
$args += $srcPath

Write-Host "[build] compiling: RoseChart.exe"
& $csc @args
if ($LASTEXITCODE -ne 0) {
    throw "csc.exe failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $outFull)) {
    throw "Launcher was not produced: $outFull"
}

$info = Get-Item -LiteralPath $outFull
Write-Host ("[build] output   : {0} ({1:N0} bytes)" -f $info.FullName, $info.Length)
Write-Host ("[build] icon     : {0}" -f $(if ($NoIcon) { '(skipped)' } else { $iconPath }))
Write-Host '[build] OK'
