# WPF/.NET 10 迁移 · 可行性探针记录

> 全部在本机离线执行；没有修改现有 Tkinter 应用代码。探针工程已删除，仅保留结论与命令记录。

## 1. 运行时与 SDK
- `dotnet --list-sdks`：10.0.204、10.0.302（`C:\Program Files\dotnet\sdk`）
- `Microsoft.WindowsDesktop.App`：6.0.36 / 9.0.19 / 10.0.8 / 10.0.10 已安装
- WPF 模板：`dotnet new list wpf` 可见 `wpf` / `wpfusercontrollib` / `wpflib` / `wpfcustomcontrollib`
- 目标框架：`net10.0-windows`

## 2. 构建 / 发布
```powershell
dotnet new wpf -n Probe
dotnet build -c Release
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=false
dotnet publish -c Release -r win-x64 --self-contained true `
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true `
  -p:EnableCompressionInSingleFile=true -o .\publish_single
```
结果：
- 离线 `build` 成功（0 警告 0 错误；首次 25s）
- 自包含目录发布成功：**约 139MB**
- 自包含单文件成功：空 WPF 壳 **64,798,722 B（≈64.8MB）**
- NuGet 在线源不可达时只有 `NU1900` 警告，不阻塞已缓存包的还原

## 3. NuGet 本地缓存（可用于离线）
| 包 | 版本 |
| --- | --- |
| ClosedXML | 0.105.0 |
| DocumentFormat.OpenXml | 3.1.1（传递依赖） |
| CommunityToolkit.Mvvm | 8.2.2 / 8.3.2 / 8.4.0 / 8.4.1 / 8.4.2 |
| xunit | 2.7.0 / 2.9.3 |
| xunit.runner.visualstudio | 2.5.7 / 3.1.4 |
| Microsoft.NET.Test.Sdk | 17.9.0 / 17.14.1 |
| SkiaSharp | 3.119.0（另有 3.119.4-preview.1.1） |
| SkiaSharp.Views.WPF | 3.119.0 |
| Microsoft.NETCore.App.Runtime.win-x64 | 10.0.1 / 10.0.7 / 10.0.8 / 10.0.10 |
| Microsoft.WindowsDesktop.App.Runtime.win-x64 | 10.0.1 / 10.0.7 / 10.0.8 / 10.0.10 |

**注意**：nuget.org 与 pypi.org 当前均不可达；只能使用缓存包。正式项目应在 `vendor/nuget/` 中固化所需 `.nupkg` 并配置离线源。

## 4. Excel 读取（ClosedXML）
离线控制台探针，读取 `rose/examples/project_test_data.xlsx`：

```csharp
using var workbook = new XLWorkbook(path);
// 项目数据 / 统计检查 两个 sheet 均读取成功
```
结果：
- `项目数据`：25 行（含表头）、11 列，表头与 Python 读取一致
- `开发类别` 计数：软件开发 12 / MES改造 7 / 视觉改造 5
- `统计检查` 也正确读取
- 仅支持 `.xlsx/.xlsm`；`.xls`（BIFF）不在 ClosedXML 支持范围

## 5. SkiaSharp 导出探针
- `SKDocument` 静态方法：`CreatePdf`, `CreateXps`（无直接 `CreateSvg` 静态方法）
- 程序集内存在 **`SkiaSharp.SKSvgCanvas`**，可用于 SVG 输出
- `SKTypeface.FromFamilyName("Microsoft YaHei")` 成功
- PNG：600×300，含中文文字，6,284 B ✔
- PDF：600×300，含中文文字，**12,460,038 B（≈12.4MB）** ⚠ 字库嵌入体积大
  - 需要后续评估：文字转路径、字体子集化，或 PDF 放 P1

## 6. 现有性能数据（对照，详见 `../perf/`）
- TkAgg 整幅重绘 35ms/帧；棋盘格 22ms；12 标签 55–59ms
- 标签拖动 38.9ms/帧（约 26fps）；12 标签 63ms（约 16fps）
- 滑杆一步 82–89ms 渲染，含 idle 二次重绘约 168ms/步（约 6–11fps）
- 窗口缩放期间被 90ms 防抖压住，画面冻结
- 关闭棋盘格后拖标签 16.6ms/帧（60fps）；快速通道 6.6ms/帧
- TkAgg `blit` 屏幕不刷新；TkAgg 透明背景不支持 → 只能分层/增量重绘

## 7. 结论
- WPF/.NET 10 在本机**可离线构建、可自包含单文件发布**，无需目标机安装 .NET。
- Excel 数据链路（ClosedXML）与导出链路（SkiaSharp）均有可行实现。
- 唯一需要先证明的是 **WPF 自绘分层能否稳定 60fps**（M0 原型门禁）；PDF 字库体积需要单独决策。
