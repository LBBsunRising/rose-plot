# RoseChart Studio · Material 3 通用玫瑰图工作台

Excel → 南丁格尔玫瑰图的桌面工作台，**.NET 10 + WPF**。
v3.1 起从「固定项目/状态两张图」升级为 **任意 Excel 列 → 任意数量动态图表**，并接入
**Material Design 3**（`MaterialDesignThemes 5.3.2`，WPF 社区标准实现；不是网页版 React MUI）。

> **生成说明**：本项目由 **DeepSeek v4.1flash 1017** 通过 **DSH vibe coding** 生成。

## 核心变化

### 1. 任意列、任意数量图表
- 左侧「数据预览」直接显示当前工作表的**真实小表格**：真实表头、Excel 行号、前 6 行数据；每个表头带勾选框，勾选该列即生成一张玫瑰图，可同时打开任意多张；水平滚动查看全部列。
- 图表标签页动态生成，支持添加、移除、切换；每张图独立保存配色、标题、排序、标签位置。
- 每个图表的**标签页名称**与**图表内大标题**可分别自定义：标签页名称可在左侧编辑或双击标签页改名；图表大标题可直接在预览画布上**点击标题**，或点标题右上角铅笔**内联编辑**（左侧/样式页字段仍同步），随设置持久化。
- 打开工作簿时只会**建议**检测到的类别/状态列（规则同 v2 `ColumnDetector`），不再硬编码任何业务列；后续可自由增删任意列。
- 右侧配色/样式/导出始终作用于当前图；「导出当前图 / 导出全部图表」完成后会自动在 Windows 资源管理器中打开输出文件夹。
- 统计方式目前为**按行数计数**（每个取值出现的行数）；数值求和/平均值等聚合作为后续扩展点。
- 设置 schema 升级为 v4（`Charts[]`），可迁移读取 v3 的固定 chart1/chart2 设置。

### 2. Material Design 3
- 离线引入 NuGet 缓存中的 `MaterialDesignThemes 5.3.2` + `MaterialDesignColors 5.3.2`。
- 使用 Material 3 light scheme（teal seed）、Roboto 字体（CJK 自动回退微软雅黑）、Material 按钮、outlined 文本框/下拉、复选框、滑杆、卡片阴影、图标（`PackIcon`）、Material 滚动条。
- 保留原有「图表是唯一主角」的自绘图表与三栏工作台骨架，控件全部 Material 化，不引入第二套视觉语言。
- 使用方式：`App.xaml` 合并 `BundledTheme` + `MaterialDesign3.Defaults.xaml`；`Themes/Tokens.xaml` 提供 Material 3 色角色，`Themes/Styles.xaml` 将原有命名按钮/卡片映射到 Material 控件。

## 当前状态

| 里程碑 | 状态 | 证据 |
| --- | --- | --- |
| M0 可行性 / 60fps 门禁 | ✅ | `_qa/perf/wpf_perf.json`：拖拽 p95 帧间隔 16.7ms，标签更新 p95 0.38ms，样式重建 p95 0.78ms |
| M1–M2 骨架 / 自绘玫瑰图 | ✅ | `_qa/shots/final/01_palette.png`、`04_dynamic_owner.png` |
| M3 交互 | ✅ | `06_drag.png`、`08_restored_layout.png`、perf 报告 |
| M4 Excel / 设置 | ✅ | ClosedXML；设置自动持久化；动态 schema v4 |
| M5 导出 | ✅ | `_qa/export/sample.png` / `.svg` / `.pdf`（透明 PNG、约 31KB 矢量 PDF） |
| M6 测试 / 性能 / 截图 | ✅ | `_qa/test_runner.txt`：**165/165 通过**；截图见 `_qa/shots/final` |
| v3.1 通用化 + Material 3 | ✅ | 本 README 与 `_qa/shots/final/contact_sheet.png` |

## 运行

```powershell
# 直接运行（本机已安装 .NET 10 Desktop Runtime）
wpf\RoseChartStudio.App\bin\Release\net10.0-windows\RoseChartStudio.exe

# 带示例数据
wpf\run.ps1 --sample

# 重新构建 / 测试
wpf\build.ps1
wpf\test.ps1
```

可选参数：
- `--sample [xlsx]`：打开示例或指定 Excel。
- `--file <xlsx>`：打开指定文件。
- `--tab palette|style|export`：启动后切右侧页面。
- `--export`：加载后导出当前图并关闭（QA 用）。
- `--qa drag|palette|status|min|follow|auto|undo|redo`：内部截图/验收场景（`status` 选择第二个动态图表）。

## 构建

前置：Windows 10 22H2+ / Windows 11 x64、.NET 10 SDK（本机 10.0.302）。当前离线环境使用本机 NuGet 缓存。

```powershell
cd wpf
$env:MSBUILDDISABLENODEREUSE='1'
$env:DOTNET_CLI_USE_MSBUILD_SERVER='0'
dotnet build .\RoseChartStudio.slnx -c Release -m:1 -nr:false
```

关键依赖（均已在本机缓存，离线可构建）：
- `ClosedXML 0.105.0`（Excel `.xlsx/.xlsm`）
- `MaterialDesignThemes 5.3.2` / `MaterialDesignColors 5.3.2`（Material 3）
- `SkiaSharp 3.119.0`（PDF 导出）
- xUnit / Microsoft.NET.Test.Sdk（测试）

## 架构

```
RoseChartStudio.App        WPF shell + Material 3 主题 + 动态图表工作台
RoseChartStudio.Rendering  RoseChartView 分层 DrawingVisual + PNG/SVG/PDF 导出
RoseChartStudio.Core       Excel 无关的色板/场景几何/标签布局/计数
RoseChartStudio.Tests      xUnit（165 个 Fact/InlineData）
RoseChartStudio.TestRunner 沙箱内 in-process xUnit 运行器
RoseChartStudio.PerfHarness 12 标签拖拽 / 样式重建 / 缩放帧时间
```

渲染：`ChartSceneBuilder` 生成统一场景；`RoseChartView` 在 `Viewbox` 中用分层 `DrawingVisual` 绘制，棋盘格是静态 `DrawingBrush`，拖标签只重绘一个 label visual；窗口缩放只改变 Viewbox 变换。屏幕与三种导出共用同一 `ChartScene`。

数据：`ExcelService` → `SheetTable` → 每个 `ChartState` 按自己的 `ColumnName` 调用 `ColumnCounter.Count`；`ChartState` 保存标题、配色、标签模式、排序、覆盖色、标签布局、撤销栈。`ObservableCollection<ChartState>` 驱动动态 tab 和左侧勾选列表。

## 测试与性能

```powershell
# 普通机器可直接 dotnet test；本会话沙箱 testhost 无法启动，使用 in-process runner
wpf\test.ps1
```

- 当前结果：**passed=165 failed=0 skipped=0**。
- 性能（12 标签，1600×1000，Viewbox 缩放 1200×800）：拖标签更新 p95 0.38ms，帧间隔 p95 **16.66ms**（60fps 门禁通过）；样式重建 p95 0.78ms；窗口缩放不重建图表。
- 证据：`_qa/perf/wpf_perf.json`、`_qa/test_runner.txt`。

## 已知限制

1. **聚合方式仅为按行数计数**；数值求和/平均/去重计数未实现（数据结构已支持后续扩展）。
2. **仅支持 `.xlsx/.xlsm`**（ClosedXML 不支持旧 `.xls`）。
3. **M7 未做**：还没有 self-contained 单文件 exe；需要时执行：
   ```powershell
   dotnet publish .\RoseChartStudio.App\RoseChartStudio.App.csproj -c Release -r win-x64 `
     --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true `
     -p:EnableCompressionInSingleFile=true -o .\publish
   ```
4. 项目文件 `.roseproj` 打开/保存 UI 未接入（设置自动持久化；v3 设置可迁移）。
5. PDF 文字为矢量轮廓（不可选中/搜索），以保证中文不依赖字体且文件约 31KB。
6. WPF 没有 Google 官方 Material UI；使用 MaterialDesignInXamlToolkit 的 Material 3 实现。若要求 React MUI 网页版，属于另一套技术栈（Tauri/Electron + Web），不在本次 WPF 迁移范围。
7. 无暗色模式、无页面级动画；控件反馈存在但未录屏验证。
8. 旧 Tkinter v2.1 应用保留在 `rose/`，可回退对照。

## 目录

- `_qa/shots/final/`：最终 Material 3 状态截图与 `contact_sheet.png`。
- `_qa/export/`：PNG/SVG/PDF 样例。
- `_qa/perf/wpf_perf.json`：性能报告。
- `_qa/test_runner.txt`：测试记录。
- `rose/_qa/wpf_plan/`：迁移规划（旧 Python 版保留）。

## License

MIT License，详见仓库根目录 [LICENSE](../LICENSE)。第三方依赖保留各自许可证。

