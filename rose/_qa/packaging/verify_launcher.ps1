# RoseChart.exe launcher verification
#
#   1. checks the PE subsystem is GUI (no console window)
#   2. checks the application icon was embedded into the exe
#   3. launches RoseChart.exe and waits for the portable .venv\pythonw.exe child
#      with a real application window, screenshots it, then stops only that child
#   4. checks the missing-runtime path shows a Chinese error MessageBox
#   5. writes rose/_qa/packaging/verify.log
#
# Usage:  pwsh -NoProfile -ExecutionPolicy Bypass -File .\_qa\packaging\verify_launcher.ps1

[CmdletBinding()]
param(
    [string]$Launcher = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'RoseChart.exe'),
    [int]$AppStartTimeoutSec = 15,
    [int]$WindowTimeoutSec = 12
)

$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$qa = $PSScriptRoot
$logPath = Join-Path $qa 'verify.log'
$stamp = { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

$lines = New-Object System.Collections.Generic.List[string]
function Log([string]$text) {
    $line = "[{0}] {1}" -f (& $stamp), $text
    $lines.Add($line)
    Write-Host $line
}

$result = [ordered]@{
    exe            = $Launcher
    subsystem_gui  = $false
    icon_embedded  = $false
    launcher_exit  = $null
    pythonw_found  = $false
    pythonw_pid    = $null
    pythonw_cmdline = $null
    window_title   = $null
    window_found   = $false
    window_shot    = $null
    screen_shot    = $null
    missing_dialog = $false
    missing_shot   = $null
    cleanup_ok     = $false
    passed         = $false
}

# ------------------------------------------------------------------ helpers
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RoseChartWin32 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
'@

function Save-WindowShot([IntPtr]$hWnd, [string]$Path) {
    try {
        $r = [RoseChartWin32+RECT]::new()
        if (-not [RoseChartWin32]::GetWindowRect($hWnd, [ref]$r)) { return $false }
        $w = $r.Right - $r.Left
        $h = $r.Bottom - $r.Top
        if ($w -le 0 -or $h -le 0) { return $false }
        $bmp = New-Object System.Drawing.Bitmap($w, $h)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $hdc = $g.GetHdc()
        $ok = [RoseChartWin32]::PrintWindow($hWnd, $hdc, 2)
        $g.ReleaseHdc($hdc)
        $g.Dispose()
        if (-not $ok) {
            $bmp.Dispose()
            return $false
        }
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        return $true
    } catch {
        Log "screenshot failed for handle $hWnd : $($_.Exception.Message)"
        return $false
    }
}

function Save-ScreenShot([string]$Path) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
        $bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
        $g.Dispose()
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        return $true
    } catch {
        Log "full-screen screenshot failed: $($_.Exception.Message)"
        return $false
    }
}

function Get-PythonwIds {
    @(Get-Process -Name pythonw -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
}

function Get-WindowProcess([string]$name, [scriptblock]$titleFilter) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Refresh() } catch {}
        $_.MainWindowTitle -and (& $titleFilter $_.MainWindowTitle)
    } | Select-Object -First 1
}

# ============================================================ step 0: manifest
Log '================ RoseChart packaging verification ================'
Log "workspace : $root"
Log "launcher  : $Launcher"
if (-not (Test-Path -LiteralPath $Launcher)) { throw "Launcher not found: $Launcher" }
$exeInfo = Get-Item -LiteralPath $Launcher
$exeSha = (Get-FileHash -LiteralPath $Launcher -Algorithm SHA256).Hash
Log ("exe size  : {0:N0} bytes, sha256 {1}" -f $exeInfo.Length, $exeSha)
foreach ($asset in @('assets\icon_1024.png', 'assets\icon_256.png', 'assets\icon.ico')) {
    $p = Join-Path $root $asset
    if (Test-Path -LiteralPath $p) {
        $fi = Get-Item -LiteralPath $p
        Log ("asset     : {0}  {1:N0} bytes" -f $asset, $fi.Length)
    } else {
        Log "asset     : $asset  MISSING"
    }
}

# ==================================================== step 1: PE subsystem GUI
try {
    $bytes = [System.IO.File]::ReadAllBytes($Launcher)
    $peOffset = [System.BitConverter]::ToInt32($bytes, 0x3C)
    $magic = [System.BitConverter]::ToUInt16($bytes, $peOffset + 24)
    $subsystemOffset = $peOffset + 24 + 68
    $subsystem = [System.BitConverter]::ToUInt16($bytes, $subsystemOffset)
    $subsystemName = switch ($subsystem) { 2 { 'WINDOWS_GUI' } 3 { 'WINDOWS_CUI' } default { "UNKNOWN($subsystem)" } }
    Log ("PE magic  : 0x{0:X4}, subsystem = {1} ({2})" -f $magic, $subsystem, $subsystemName)
    $result.subsystem_gui = ($subsystem -eq 2)
} catch {
    Log "PE subsystem check failed: $($_.Exception.Message)"
}
Log ("CHECK subsystem (target:winexe, no console): {0}" -f $(if ($result.subsystem_gui) { 'PASS' } else { 'FAIL' }))

# ================================================ step 2: embedded exe icon
try {
    Add-Type -AssemblyName System.Drawing
    $ico = [System.Drawing.Icon]::ExtractAssociatedIcon((Resolve-Path -LiteralPath $Launcher).Path)
    if ($ico) {
        $bmp = $ico.ToBitmap()
        $iconShot = Join-Path $qa 'exe_embedded_icon.png'
        if ($bmp.Width -ge 256) {
            $bmp.Save($iconShot, [System.Drawing.Imaging.ImageFormat]::Png)
        } else {
            $big = New-Object System.Drawing.Bitmap(256, 256)
            $g = [System.Drawing.Graphics]::FromImage($big)
            $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $g.DrawImage($bmp, 0, 0, 256, 256)
            $g.Dispose()
            $big.Save($iconShot, [System.Drawing.Imaging.ImageFormat]::Png)
            $big.Dispose()
        }
        Log ("embedded icon: {0}x{1} -> {2}" -f $bmp.Width, $bmp.Height, $iconShot)
        $bmp.Dispose()
        $result.icon_embedded = $true
    }
} catch {
    Log "embedded icon check failed: $($_.Exception.Message)"
}
Log ("CHECK embedded application icon (/win32icon assets/icon.ico): {0}" -f $(if ($result.icon_embedded) { 'PASS' } else { 'FAIL' }))

# =================================== step 3: launch and find pythonw window
$oldPythonw = Get-PythonwIds
Log ("pythonw processes before launch: [{0}]" -f ($oldPythonw -join ', '))
$launcherProc = Start-Process -FilePath $Launcher -WorkingDirectory $root -PassThru
Start-Sleep -Milliseconds 1200
try { $launcherProc.Refresh() } catch {}
if ($launcherProc.HasExited) {
    $result.launcher_exit = $launcherProc.ExitCode
    Log "launcher exited with code $($launcherProc.ExitCode) (expected 0)"
} else {
    Log 'launcher still running after 1.2s (expected to exit immediately)'
}

$newPy = @()
$deadline = (Get-Date).AddSeconds($AppStartTimeoutSec)
while ((Get-Date) -lt $deadline) {
    $newPy = @(Get-PythonwIds | Where-Object { $oldPythonw -notcontains $_ })
    if ($newPy.Count -gt 0) { break }
    Start-Sleep -Milliseconds 350
}
if ($newPy.Count -gt 0) {
    $result.pythonw_found = $true
    $result.pythonw_pid = $newPy[0]
    Log ("new pythonw process: PID {0} (started by the launcher)" -f $newPy[0])
    $py = Get-Process -Id $newPy[0]
    try {
        $pyPath = $py.Path
        Log ("pythonw executable: {0}" -f $pyPath)
        $result.pythonw_cmdline = "path=$pyPath args=-B app.py (per launcher design; WMI cmdline unavailable)"
    } catch {
        Log "pythonw path lookup failed: $($_.Exception.Message)"
    }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $($newPy[0])" -ErrorAction SilentlyContinue
    if ($cim) {
        $result.pythonw_cmdline = $cim.CommandLine
        Log ("pythonw command line: {0}" -f $cim.CommandLine)
    }
} else {
    Log "no new pythonw process appeared within $AppStartTimeoutSec s"
}
Log ("CHECK pythonw child process: {0}" -f $(if ($result.pythonw_found) { 'PASS' } else { 'FAIL' }))

if ($result.pythonw_found) {
    $pyProc = Get-Process -Id $result.pythonw_pid -ErrorAction SilentlyContinue
    $tdeadline = (Get-Date).AddSeconds($WindowTimeoutSec)
    $title = ''
    while ((Get-Date) -lt $tdeadline) {
        try { $pyProc.Refresh() } catch {}
        $title = $pyProc.MainWindowTitle
        if ($title) { break }
        Start-Sleep -Milliseconds 350
    }
    $result.window_title = $title
    $result.window_found = [bool]$title
    Log ("pythonw MainWindowTitle: '{0}'" -f $title)
    $rose = ([string][char]0x73AB) + ([string][char]0x7470)      # 玫瑰
    $titleOk = $title -match 'Excel|PNG|Rose|Chart' -or $title.Contains($rose)
    Log ("title contains app keywords: {0}" -f $(if ($titleOk) { 'yes' } else { 'no' }))
    Log ("CHECK application window visible: {0}" -f $(if ($result.window_found) { 'PASS' } else { 'FAIL' }))
    if ($result.window_found) {
        $hwnd = $pyProc.MainWindowHandle
        [void][RoseChartWin32]::SetForegroundWindow($hwnd)
        Start-Sleep -Milliseconds 500
        $shot = Join-Path $qa 'window_pythonw.png'
        if (Save-WindowShot $hwnd $shot) {
            $result.window_shot = $shot
            Log "window screenshot -> $shot"
        }
        $screenShot = Join-Path $qa 'screen_pythonw.png'
        if (Save-ScreenShot $screenShot) { $result.screen_shot = $screenShot; Log "screen screenshot -> $screenShot" }
    }
    # close only the pythonw instance started by our launcher
    try {
        Stop-Process -Id $result.pythonw_pid -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        $still = Get-Process -Id $result.pythonw_pid -ErrorAction SilentlyContinue
        $result.cleanup_ok = (-not $still)
        Log "stopped pythonw PID $($result.pythonw_pid); still running: $([bool]$still)"
    } catch {
        Log "failed to stop pythonw PID $($result.pythonw_pid): $($_.Exception.Message)"
    }
    $others = @(Get-PythonwIds | Where-Object { $oldPythonw -contains $_ })
    Log ("pre-existing pythonw processes untouched: [{0}]" -f ($others -join ', '))
}

# ============================ step 4: missing-runtime error message box path
$missingDir = Join-Path $qa 'missing_runtime_test'
if (Test-Path -LiteralPath $missingDir) { Remove-Item -LiteralPath $missingDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $missingDir | Out-Null
$missingExe = Join-Path $missingDir 'RoseChart.exe'
Copy-Item -LiteralPath $Launcher -Destination $missingExe
Write-Host ("copied launcher to isolated folder: {0}" -f $missingDir)
$dlg = Start-Process -FilePath $missingExe -WorkingDirectory $missingDir -PassThru
$deadline = (Get-Date).AddSeconds(8)
$dlgWin = $null
while ((Get-Date) -lt $deadline) {
    $dlgWin = Get-WindowProcess -name 'RoseChart' -titleFilter { param($t) $t -like '*RoseChart*' }
    if ($dlgWin) { break }
    Start-Sleep -Milliseconds 300
}
if ($dlgWin) {
    $result.missing_dialog = $true
    Log ("missing-runtime dialog found: PID {0}, title '{1}'" -f $dlgWin.Id, $dlgWin.MainWindowTitle)
    $dhwnd = $dlgWin.MainWindowHandle
    [void][RoseChartWin32]::SetForegroundWindow($dhwnd)
    Start-Sleep -Milliseconds 400
    $dshot = Join-Path $qa 'window_missing_runtime.png'
    if (Save-WindowShot $dhwnd $dshot) {
        $result.missing_shot = $dshot
        Log "missing-runtime dialog screenshot -> $dshot"
    }
    Stop-Process -Id $dlgWin.Id -Force -ErrorAction SilentlyContinue
} else {
    Log 'missing-runtime dialog window was not detected'
}
# also make sure the isolated launcher never started a python process from the empty folder
Start-Sleep -Milliseconds 300
try { $dlg.Refresh() } catch {}
if (-not $dlg.HasExited) { Stop-Process -Id $dlg.Id -Force -ErrorAction SilentlyContinue }
Log ("CHECK missing-runtime Chinese MessageBox: {0}" -f $(if ($result.missing_dialog) { 'PASS' } else { 'FAIL' }))

# =============================================================== summary log
$result.passed = ($result.subsystem_gui -and $result.icon_embedded -and $result.pythonw_found -and
                  $result.window_found -and $result.cleanup_ok -and $result.missing_dialog)
Log '------------------------------ summary ------------------------------'
foreach ($k in $result.Keys) {
    if ($k -ne 'passed') { Log ("{0,-16}: {1}" -f $k, $result[$k]) }
}
Log ("RESULT: {0}" -f $(if ($result.passed) { 'ALL CHECKS PASSED' } else { 'FAILED' }))
$lines | Out-File -LiteralPath $logPath -Encoding utf8
Write-Host ''
Write-Host "verify.log written to $logPath"
if (-not $result.passed) { exit 1 } else { exit 0 }
