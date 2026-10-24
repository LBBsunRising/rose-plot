@echo off
rem RoseChart Studio 启动脚本（便携版）
rem 优先使用已编译的 RoseChart.exe；如果没有，则直接用 .venv\pythonw.exe 启动。
setlocal
cd /d "%~dp0"

rem 清掉可能干扰便携运行时的 Conda / Python 环境变量
set CONDA_PREFIX=
set CONDA_DEFAULT_ENV=
set CONDA_PROMPT_MODIFIER=
set CONDA_SHLVL=
set _CE_CONDA=
set _CE_M=
set PYTHONHOME=
set PYTHONPATH=

if exist "RoseChart.exe" (
    start "" "%~dp0RoseChart.exe"
    exit /b 0
)

if not exist ".venv\pythonw.exe" goto missing_runtime
if not exist "app.py" goto missing_runtime

rem 用固定的工作目录启动，避免输入法/第三方程序在程序目录里写日志
set "WORKDIR=%LOCALAPPDATA%\RoseChartStudio"
if not exist "%WORKDIR%" mkdir "%WORKDIR%" >nul 2>nul
if exist "%WORKDIR%" (
    start "" /D "%WORKDIR%" "%~dp0.venv\pythonw.exe" -B "%~dp0app.py"
) else (
    start "" "%~dp0.venv\pythonw.exe" -B "%~dp0app.py"
)
exit /b 0

:missing_runtime
echo.
echo   RoseChart Studio 无法启动：缺少便携运行环境或程序文件。
echo   请把整个 rose 文件夹（包含 .venv、app.py、RoseChart.exe）完整复制后再运行。
echo.
pause
exit /b 1
