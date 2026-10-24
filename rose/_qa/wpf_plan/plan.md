# RoseChart Studio → WPF/.NET 10 + 自绘图表 · 迁移规划

> 状态：规划稿（本轮不改现有应用代码）
> 目标：保留 v2.1 的功能与设计语言，把卡顿的 Tkinter + matplotlib/TkAgg 预览替换为 WPF 自绘图表，达到拖标签/拖滑杆/缩放窗口 60fps 的手感。

## 1. 成功标准（可验收）

| 指标 | 目标 | 测量方式 |
| --- | --- | --- |
| 标签拖动（12 类别） | p95 帧时间 ≤ 16.7ms（≥60fps） | 内置 PerfHarness：模拟 200 次 mousemove，记录 `CompositionTarget.Rendering` 帧间隔 |
| 滑杆拖动（内外半径/字号等） | p95 ≤ 16.7ms | 同上，自动化拖动滑块 |
| 窗口缩放 | 拖动跟手，无整帧冻结；停下后 150ms 内清晰 | 录制/逐帧截图 + 帧时间 |
| 启动 | 冷启动 ≤ 2s（SSD） | 从进程启动到主窗口可交互 |
| 打开 Excel | 5,000 行 .xlsx ≤ 1s，10,000 行 ≤ 2s | Stopwatch + UI 可用时间 |
| 导出 | 1920×1080 透明 PNG ≤ 300ms | 导出计时 |
| 功能回归 | v2.1 功能清单全部通过 | 回归清单 + xUnit + 截图验收 |
| 视觉回归 | 与 v2.1 截图并排评审，布局/字号/色彩一致，允许 WPF 抗锯齿差异 | 截图并排 + 独立评审 |
| 分发 | 无 .NET 运行时的 Windows 10/11 x64 上可运行 | 干净虚拟机/另一台机器验证 |

## 2. 已完成的可行性验证（本机，离线）

| 项 | 结果 |
| --- | --- |
| .NET SDK | 10.0.204 / 10.0.302 已安装 |
| WPF 模板 + `dotnet build` | `net10.0-windows` 离线构建成功 |
| 自包含发布 | `dotnet publish -r win-x64 --self-contained true` 成功，约 139MB 目录 |
| 单文件发布 | `PublishSingleFile + 压缩` 成功，空 WPF 壳 **64.8MB exe**，无需目标机安装 .NET |
| ClosedXML 0.105.0（NuGet 缓存） | 离线读取示例 xlsx 成功：`项目数据` 25 行、列头与计数正确 |
| SkiaSharp 3.119.0（缓存） | 离线生成 PNG/PDF 成功；`Microsoft YaHei` 可找到；PDF 含全字库导致单页约 12MB（需优化/或仅用于 P1） |
| xUnit / Microsoft.NET.Test.Sdk / CommunityToolkit.Mvvm | 均已在 NuGet 本地缓存（17.14.1 / 2.9.3 / 8.4.x） |
| 网络 | nuget.org / pypi 均不可达 → 必须用缓存包 + vendor 包，禁止引入未缓存依赖 |

> 结论：WPF 方案在本机离线可行；但“60fps 自绘图表”必须由 M0 原型实测把关，不能只靠推理。

## 3. 技术选型与架构

### 3.1 技术栈
- **.NET 10 + WPF**（`net10.0-windows`），Windows x64；不使用 UWP/WinUI/Maui。
- **UI**：XAML + 轻量 MVVM（CommunityToolkit.Mvvm 8.4.x，已有缓存）；不使用收费控件库。
- **Excel**：ClosedXML 0.105.0（+ DocumentFormat.OpenXml 3.1.1），只支持 `.xlsx/.xlsm`；`.xls` 需决策（见 §10）。
- **图表渲染（屏幕）**：WPF 原生自绘，**分层 DrawingVisual**（首选）；备选方案见 3.3。
- **导出**：
  - PNG：WPF `RenderTargetBitmap`（与屏幕同一套绘图几何）或 SkiaSharp。
  - SVG：自绘场景导出器（或 `SKSvgCanvas` 实测可用）。
  - PDF：SkiaSharp `SKDocument.CreatePdf` 起步；字库体积问题需在 M0 评估，必要时把文字转路径或后置到 P1。
- **测试**：xUnit + 自建 PerfHarness + 截图对比；无需联网。
- **打包**：self-contained 单文件 `RoseChartStudio.exe`（目标 ~70–100MB，含依赖）；直接双击，无需安装 .NET。

### 3.2 工程结构（建议）
```
wpf/
  RoseChartStudio.sln
  Directory.Packages.props          # 锁定缓存版本
  NuGet.config                      # 清空在线源，指向 vendor 目录
  vendor/nuget/                     # 从本机缓存复制 .nupkg，保证离线可重建
  src/
    RoseChartStudio.App/            # WPF Shell：窗口/面板/控件/ViewModel
    RoseChartStudio.Core/           # 模型、色板算法、统计、场景几何、命令
    RoseChartStudio.Rendering/      # 分层 DrawingVisual 渲染 + 导出
    RoseChartStudio.Data/           # ClosedXML 读取、项目/设置
    RoseChartStudio.Tests/          # xUnit + golden tests + perf harness
  assets/                           # icon.ico、palettes.json、示例 Excel
  scripts/build.ps1 | test.ps1 | publish.ps1
```

### 3.3 渲染架构（核心）

**首选：WPF 分层 DrawingVisual，按“变化的层”增量重绘。**

```
RoseChartView (FrameworkElement, 承载输入与布局)
 ├─ CheckerboardLayer   DrawingBrush 平铺，静态，不参与每帧重绘
 ├─ ChartBaseLayer      DrawingVisual：扇区/描边/标题/副标题/中心文字
 │                      仅在数据、样式、尺寸、配色变化时重绘（约 1–3ms）
 ├─ LabelLayer          VisualCollection，每个标签一个 DrawingVisual
 │                      （文字 + 引线 + 白底保护片），拖动只重绘/移动对应 visual
 ├─ HoverLayer          悬停/选中/焦点装饰，独立视觉
 └─ OverlayLayer        空状态、加载、错误提示
```

- 拖动标签：只更新该标签 visual 的几何与文本位置，`InvalidateVisual()` 范围极小；WPF 合成器 60fps。
- 滑杆：重建扇区 PathGeometry（12 个以内）+ 重新布局标签（文字测量缓存），只重绘 Base+Label，不重绘画布背景；目标 <8ms。
- 窗口缩放：WPF 布局后再重建 Base/Label（同样只 1–3ms），拖动窗口边缘不冻结。
- 棋盘格：`DrawingBrush` 小图块平铺，由 WPF 合成器处理，**不再进入每帧 CPU 绘制**。
- 高 DPI：WPF 原生 PerMonitorV2；文字 `FormattedText` 按 `PixelsPerDip` 渲染。导出用目标 DPI 独立渲染。
- 鼠标输入：`Mouse.Capture` + 手算标签命中（几何模型）；不用全画布 hit-test 扫描；拖动时使用最新鼠标位置（不需要事件队列）。
- 撤销/重做、双击复位、自动排列：沿用 v2.1 语义，数据模型保存标签偏移。

**备选（M0 对比后决定）：SkiaSharp 整画布渲染（`SKElement`）**
- 优点：屏幕与 PNG/PDF/SVG 共用同一个 `ChartRenderer`，一致性最高；Skia CPU 绘制 900×600 图表预计 2–6ms。
- 缺点：每次重绘整张位图（无脏区域），4K/高缩放屏仍有风险；与 WPF 原生输入/无障碍融合略差。
- M0 用同一套场景分别实现 WPF 分层与 Skia 原型，各测 12 标签拖动/滑杆/缩放，选 p95 更好、导出更一致者。**默认押注 WPF 分层，Skia 作为兜底与导出后端。**

### 3.4 数据流
```
Excel → ExcelReader → SheetData(DataFrame 等价)
      → ColumnDetector → 选择列 → CountService → ChartData(labels, values)
      → PaletteService(16 套 + 推荐 + 自动对比色 + 覆盖色)
      → ChartScene(几何：扇区路径、标签锚点/自动布局、样式)
      → RoseChartView 渲染 / Exporter 导出
```
- 所有几何计算在 `Core` 中与 UI 无关，可用 xUnit 测试；
- 标签自动布局、长标签内收、拖拽约束、白底保护片判定与 v2.1 逻辑保持一致（通过 Python 生成的 golden fixture 校验）。

## 4. 功能范围（对齐 v2.1）

### P0（首版必须）
- 打开 `.xlsx/.xlsm`、选工作表、自动识别/手动指定统计列；项目/状态两张图或单图；数量/占比表格。
- 16 套色板 + 推荐 + 「当前方案」行 + 标签配色三模式 + 每类别改色 + 色数不足提示。
- 完整的图表样式参数（标题、内外半径、起始角、间隙、圆角、描边、标签字号/引线、显示项、小数位、后缀、中心文字、字体、背景）。
- 标签拖拽（悬停、拖拽、双击复位、撤销/重做、自动排列、按类别记忆位置、导出保留位置）。
- 导出 PNG/SVG，尺寸预设+自定义、DPI、透明背景、文件名模板、双图导出、复制图片到剪贴板。
- 设置持久化、最近文件、窗口尺寸、错误日志、启动示例数据。
- 与 v2.1 相同的视觉语言（颜色 token、字号、间距、图标资产）。

### P1（补齐）
- PDF 导出（视 M0 字库体积评估：路径化文字/或接受较大文件）。
- 项目文件 `.roseproj` 兼容导入；拖拽 Excel 文件到窗口；多显示器 DPI 处理；键盘无障碍；输出目录打开。
- 表格点击定位、空状态、加载/失败态、超长类别名处理。

### P2（后续）
- `.xls` 支持（若必须：Excel COM 兜底或单独解析器）；批量处理；更多图表类型；深色模式；多语言；自动更新。

## 5. 关键性能设计依据（来自本项目实测）
- 现状瓶颈：TkAgg 每帧整幅重绘 35ms，其中棋盘格 22ms；12 标签 55ms；滑杆每次重建 82–89ms；这与 WPF 无关，是“全帧光栅化 + 无脏区域”的架构问题。
- WPF 分层后：
  - 棋盘格 → 静态 DrawingBrush，每帧 0ms；
  - 拖标签 → 只重绘一个 label visual（文字+线）；
  - 滑杆 → 最多 12 个扇区 Path + 标签，不重绘静态层；
  - 缩放 → 同上，WPF 布局完成后再重建两层。
- M0 会给每项设定实测门禁：12 标签拖动 p95 ≤16.7ms、滑杆 ≤16.7ms、缩放无冻结；达不到则切 Skia 方案或调整（例如只重绘局部区域/缓存）。

## 6. 数据与兼容性

- **Excel**：ClosedXML 逐行/按 UsedRange 读取，自动识别 `开发类别/状态` 等关键字；空值/空格清洗；公式取缓存值；不支持 `.xls` 除非另定方案。
- **色板**：从 Python 生成 `palettes.json`（16 套、命名映射、推荐权重所需字段），C# 实现相同的 WCAG/CIELAB/HSL 工具与推荐排序，使用 Python 现有测试的期望值做 golden 校验。
- **旧项目文件**：读取 v2 `.roseproj` JSON（字段：file/sheet/column_a/column_b/charts/style/export/layout），映射为 v3 模型；标签位置按类别名保留。
- **设置**：便携优先（exe 同目录 `rosechart_settings.json`，不可写时回退 `%LOCALAPPDATA%`）；沿用现有最近文件/窗口记忆语义。
- **资源**：复用 `assets/icon.ico`、icon_256、示例 xlsx；应用图标嵌入 exe。

## 7. 导出设计

| 格式 | 方案 | 备注 |
| --- | --- | --- |
| PNG | WPF 场景渲染到 `RenderTargetBitmap`（目标像素/DPI，透明背景） | 与屏幕共用场景，透明度需保留 |
| SVG | 自绘场景 → SVG（路径 + text；可选文字转路径） | 无第三方依赖；与 HTML/PPT 兼容 |
| PDF | SkiaSharp `SKDocument.CreatePdf`（M0 评估） | 探针单页约 12MB（全字库）；需转路径/子集化或降级 P1 |
| 剪贴板 | WPF `Clipboard.SetImage` | 等价当前功能 |

布局/标签位置、配色、样式在三种格式中共用同一个 `ChartScene`，避免"屏幕与导出不一致"。

## 8. 测试与验收

- **单元**：统计、列识别、色板算法（颜色/推荐/对比色）、几何（扇区路径、标签自动布局、长标签、hit-test）、项目读写、导出参数。
- **Golden**：由现有 Python 测试生成 JSON fixtures（计数、palette 分配、默认标签位置、推荐 id），C# 逐项断言。
- **渲染 golden**：固定样例（3 类、12 类、单类、超长标签、透明背景、12 编码）渲染 PNG，与基线图做像素差（允许抗锯齿容差），人工评审并排图。
- **PerfHarness**：拖标签 200 次、滑杆 100 次、窗口缩放 20 次；输出 p50/p95/最大值，低于阈值才通过。
- **UI 自动化**：启动 `--smoke` 自动加载示例、切页、导出；用 WPF `RenderTargetBitmap` 或窗口截图（PowerShell/ImageGrab）取状态图；xUnit 覆盖无 UI 依赖部分。
- **打包验证**：干净机/无 .NET 机器运行 self-contained exe；大 DPI/中文系统；权限异常；杀毒首次扫描启动。

## 9. 打包与分发

- 发布：`dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true`
- 输出：`RoseChartStudio.exe`（预计 70–100MB，含 WPF + ClosedXML + 可选 Skia）；示例 Excel + README 放同目录。
- 图标/版本信息：`<ApplicationIcon>`、`AssemblyInfo` 版本、文件属性；应用内 About。
- 便携 vs 安装：首版绿色单文件（与当前"复制文件夹即用"一致）；后续可选 Inno Setup/NSIS 安装包（不做自动更新）。
- 回退：旧 Tkinter 版保留为 `rose/`（v2.1），新版在 `wpf/` 独立发布，达到功能对等后再切换默认。

## 10. 里程碑与工作量（单人估算）

| 阶段 | 内容 | 工期 |
| --- | --- | --- |
| **M0 可行性门禁** | WPF 离线构建/发布已过；补：分层图表原型（3/12 标签、拖动、滑杆、缩放）测 FPS；ClosedXML/Skia 导出 proof；定渲染方案 | **2–3 天** |
| M1 骨架与设计系统 | 解决方案、MVVM、主题 token、主窗口三栏、空状态、状态栏、菜单、图标 | 3–4 天 |
| M2 图表静态渲染 | 扇区几何、圆角、标题、标签布局、棋盘格背景、配色/样式全量参数 | 5–7 天 |
| M3 交互 | 拖拽/悬停/双击复位/撤销重做/自动排列/布局记忆；滑杆实时更新；缩放 | 4–6 天 |
| M4 数据与设置 | ClosedXML 读取、工作表/列识别、统计、最近文件、项目导入导出、设置 | 3–4 天 |
| M5 导出 | PNG/SVG（+PDF 决策）、尺寸/DPI/透明、双图、剪贴板、文件名模板 | 3–4 天 |
| M6 验收 | golden/perf/DPI/边界/回归、截图评审、性能调优 | 4–6 天 |
| M7 打包文档 | 单文件发布、图标、干净机验证、README/迁移说明 | 2–3 天 |
| **合计** | | **约 26–37 人日（5–7.5 周）** |

- 2 人并行（A：渲染/交互/性能；B：壳/控件/数据/导出）：约 **3–4 周** 可达到 beta。
- 第 3 人（QA/打包）可在 M5 后加入。
- 现有 UI 设计、色板、示例数据、验收脚本可直接复用，减少设计时间。

## 11. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| WPF 分层未必达到 60fps（大画布/多标签/4K） | 核心目标失败 | M0 原型先测；备选 SkiaSharp 整画布；再不行调整预览尺寸/减少动态层 |
| 离线依赖不可得（新包） | 无法构建 | 只用已缓存版本 + vendor nupkg；M0 固定版本并验证重建 |
| 旧 `.xls` 不支持 | 老用户打不开 | v1 仅 `.xlsx/.xlsm`；若必须，Excel COM 兜底或保留旧版处理 `.xls` |
| PDF 字库体积过大（探针单页 12MB） | 导出文件不可接受 | 文字转路径/子集化；或 PDF 放 P1 |
| WPF/屏幕与导出渲染不一致 | 用户投诉所见非所得 | 共用 `ChartScene`；PNG 用同场景；三格式截图对比测试 |
| 中文字体在目标机缺失 | 方块字 | 微软雅黑/黑体/宋体回退链；启动自检提示；必要时可选打包开源中文字体（注意许可） |
| 目标机无 .NET / 权限/杀软 | 无法启动 | self-contained 单文件；干净机+杀软测试；错误日志 |
| 新旧功能对等遗漏 | 迁移延期 | 以 v2.1 功能清单打勾；双版本并行；逐项验收 |
| 团队不熟 C#/XAML | 效率低 | M0 同时定代码规范；渲染/交互模块化，便于分工 |

## 12. 需要你确认的决策

1. **Excel 兼容范围**：只支持 `.xlsx/.xlsm` 是否可接受？`.xls` 是否必须（若必须，优先做 Excel COM 兜底还是保留旧版处理）？
2. **PDF**：首版必须带 PDF，还是先 PNG/SVG、PDF 放 P1？若必须，接受“文字转路径”的实现吗？
3. **打包形式**：self-contained 单文件 exe（约 70–100MB、零安装，推荐）vs 依赖目标机 .NET 10 Desktop Runtime 的小体积版（约 5–10MB）？
4. **迁移策略**：是否保留旧 Tkinter 版作为回退/对照，直到新版功能对等再切换？
5. **目标系统**：Windows 10 22H2+ / Windows 11 x64 是否满足？是否还有 Win7/8 或 arm64 需求？
6. **UI 范围**：首版严格复刻 v2.1 视觉，还是借 WPF 允许做一定升级（圆角/阴影/微动效）？
7. **节奏/人力**：单人 5–7.5 周还是两人 3–4 周？是否先只做 M0 试验（2–3 天）再决定全面迁移？

## 13. 建议的下一步

**先做 M0（2–3 天）**，产出：
- WPF 分层图表原型（12 扇区/12 标签/拖拽/滑杆/缩放）＋帧时间报告；
- 与 SkiaSharp 整画布方案的同场对比（可选）；
- Excel 读取、PNG/SVG/PDF 导出、离线构建/发布 proof；
- Go/No-Go 结论与最终选型。

M0 通过后再进入 M1，避免直接投入数周后才发现性能或依赖不达标。

---

### 附：可行性探针记录
`feasibility.md`（本目录）：含 dotnet 构建/发布、ClosedXML 读表、SkiaSharp 导出、缓存包版本、限制条件。
