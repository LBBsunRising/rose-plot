# RoseChart Studio 测试脚本
# 用法:  pwsh -File .\run_tests.ps1            # 全部测试（含 GUI 截图测试，需要桌面会话）
#        pwsh -File .\run_tests.ps1 -SkipGui   # 只跑无界面测试
param(
    [switch]$SkipGui
)

$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "缺少便携运行时: $python" -ForegroundColor Red
    exit 1
}

$failures = 0
function Invoke-Step {
    param([string]$Name, [string]$Script)
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    & $python -B $Script
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name (exit $LASTEXITCODE)" -ForegroundColor Red
        $script:failures++
    }
    else {
        Write-Host "PASSED: $Name" -ForegroundColor Green
    }
}

Invoke-Step '色板模块单元测试' 'tests\test_palettes.py'
Invoke-Step '图表边界用例 + 联系表' '_qa\edge_cases.py'
Invoke-Step '命令行渲染' 'render_charts.py'

if (-not $SkipGui) {
    Invoke-Step 'GUI 冒烟 / 拖拽 / 导出一体化测试' '_qa\gui_smoke.py'
    Invoke-Step 'GUI 交互 / 缩放 / 矢量导出测试' '_qa\gui_interactions.py'
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "ALL TEST SUITES PASSED" -ForegroundColor Green
    exit 0
}
Write-Host "$failures test suite(s) failed" -ForegroundColor Red
exit 1
