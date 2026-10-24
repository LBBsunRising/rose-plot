# RoseChart packaging QA

Portable Windows launcher + application icon for the RoseChart project.

## Deliverables

| File | Size | Notes |
|---|---|---|
| `../RoseChart.exe` | ~69 KB | C# winexe launcher, embeds `assets\icon.ico`, no console window |
| `../../assets/icon_1024.png` | ~230 KB | 1024x1024 RGBA, transparent background |
| `../../assets/icon_256.png` | ~37 KB | 256x256 RGBA |
| `../../assets/icon.ico` | ~63 KB | 16/24/32/48/64/128/256 multi-size |
| `../build_launcher.ps1` | - | idempotent build script (csc detection + icon embedding) |

Launcher behaviour: resolves its own folder, requires `.venv\pythonw.exe` and
`app.py` next to it, then starts `pythonw.exe -B app.py` with
`UseShellExecute=false`, `CreateNoWindow=true`, working directory = exe folder.
If the runtime is missing it shows a Chinese MessageBox:
“未找到便携运行环境…请连同 .venv 文件夹一起复制整个程序目录后再运行。”

## Rebuild

```powershell
cd rose
pwsh -NoProfile -ExecutionPolicy Bypass -File .\build_launcher.ps1
```

The script finds `csc.exe` under `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319`,
rewrites `_qa\packaging\build\RoseChartLauncher.cs` only when the embedded source
changed, and compiles `/target:winexe` with `/win32icon:assets\icon.ico`.
Repeated runs are safe (same input -> same behaviour, same size); the exact
SHA-256 may differ because the native csc writes a fresh PE timestamp.

## Regenerate the icon

`oil_ui_image` is not installed in this offline environment, so the icon is
generated programmatically with Pillow + NumPy (supersampled 4x, LANCZOS
downscaled):

```powershell
cd rose
.\.venv\python.exe _qa\packaging\make_icon.py
```

Design: flat Nightingale-rose-chart / petal-ring disc, 10 rounded slices with
varied radii, concentric deep-teal -> cyan bands, thin radial chart separations,
small core dot, transparent background, no text.

Icon QA sheets: `icon_variants.png` (iteration history), `icon_final_candidates.png`,
`icon_ico_sizes.png`, `icon_small_sizes.png`, `exe_embedded_icon.png`.

## Verify

```powershell
cd rose
pwsh -NoProfile -ExecutionPolicy Bypass -File .\_qa\packaging\verify_launcher.ps1
```

Checks: PE subsystem == WINDOWS_GUI, icon embedded, launcher starts
`.venv\pythonw.exe` which opens the app window, window screenshot, only that
pythonw PID is stopped, missing-runtime MessageBox path (isolated copy) shows the
Chinese dialog. Result is written to `verify.log`.

Last run: **ALL CHECKS PASSED** (see `verify.log`), app window title
`玫瑰图工坊 · RoseChart Studio`. Re-run this script after the Lead updates
`app.py` / `rosechart/**` to re-confirm the launcher still opens the new UI.

Screenshots: `window_pythonw.png`, `screen_pythonw.png`,
`window_missing_runtime.png`.
