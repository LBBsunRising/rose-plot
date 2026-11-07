# QA 证据（WPF v3.4 / 简笔风 UI）

> v3.4 将整个界面改为简笔风：暖白点阵纸背景、墨线卡片、手写体标题、红色小印记、旋转便签、虚线分隔和线性玫瑰图图标。功能仍是任意列 → 任意数量动态图表，并继续使用 MaterialDesignThemes 5.3.2 的控件行为与灰色主题。统计方式当前为按行数计数。

## v3.4 简笔风

| 文件 | 内容 |
| --- | --- |
| `shots/final/30_sketch_blank.png` | 简笔风空白工作台：点阵纸 + 墨线卡片 + 便签标题 |
| `shots/final/31_sketch_sample.png` | 示例工作簿：图表工作室与线稿外框 |
| `shots/final/32_sketch_style.png` | 简笔风样式页：墨线分段 Tab 与手写体标题 |
| `shots/final/33_sketch_focus.png` | 专注画布：只保留图表与导航轨 |
| `shots/final/34_sketch_editor.png` | 粘贴/编辑表格：纸墨表格与线框按钮 |
| `shots/final/35_sketch_min.png` | 最小窗口 1440×870 下的简笔布局 |
| `shots/final/36_sketch_export.png` | 简笔风导出页 |

## v3.3 现代工作台（历史）

| 文件 | 内容 |
| --- | --- |
| `shots/final/20_modern_ui.png` | 现代工作台空白态：深色顶栏 + 导航轨 + 右侧分段属性页 |
| `shots/final/21_modern_sample.png` | 示例工作簿：图表工作室 + 配色页 |
| `shots/final/22_modern_focus.png` | 左侧「专注画布」收起数据/属性面板 |
| `shots/final/23_modern_min.png` | 最小窗口 1440×870 下的现代布局 |
| `shots/final/24_modern_style.png` | 分段式样式页 |
| `shots/final/25_modern_export.png` | 分段式导出页 |

## v3.2 及更早功能证据

| 文件 | 内容 |
| --- | --- |
| `shots/final/00_empty.png` | 空状态（首次启动，Material 3） |
| `shots/final/01_palette.png` | Material 3 配色页 + 真实表格预览 + 预览内联标题编辑 |
| `shots/final/02_style.png` | Material 3 样式页（Material 滑杆/文本框/按钮） |
| `shots/final/03_export.png` | 导出页（PNG/SVG/PDF、尺寸主从、导出全部图表、导出后自动打开文件夹） |
| `shots/final/04_dynamic_owner.png` | 任意列「负责人」动态生成第 3 张图 |
| `shots/final/05_status.png` | 状态列动态图表（第二张图 + 当前方案切换） |
| `shots/final/06_drag.png` | 拖动标签后（自定义布局 + Ctrl+Z 提示） |
| `shots/final/07_min_window.png` | 最小窗口 1440×870（逻辑） |
| `shots/final/08_restored_layout.png` | 重启后恢复动态图表与自定义标签位置 |
| `shots/final/09_inline_title.png` | 在预览画布内联编辑图表标题（点击标题或点铅笔） |
| `shots/final/11_blank_table.png` | 软件内空白表格（含行号；右键行号/列标题/单元格可插入或删除行列） |
| `shots/final/12_paste_grid_chart.png` | 编辑完成并点击“生成图表”后的玫瑰图 |
| `shots/final/15_paste_table_edit.png` | 生成后通过顶部“编辑数据”重新打开表格，编辑单元格 |
| `shots/final/16_row_col_context_menu.png` | 与 Excel 一致：右键行号/列标题/单元格插入或删除行列 |

截图通过 `PrintWindow` 从应用窗口本身捕获，避免桌面其他置顶窗口/广告浮层进入证据；分辨率 1900×1175（1520×940 @125% DPI），最小窗口 1800×1088（1440×870 @125%）。`contact_sheet.png` 为 6 个简笔风关键状态并排总览。

## 导出样例

- `export/sample.png`：1200×800 RGBA，透明背景（780k 透明像素）。
- `export/sample.svg`：1200×800，3 个扇区 path + 7 个 text。
- `export/sample.pdf`：`%PDF-1.4`，约 31KB（中文以矢量轮廓嵌入，非字库）。

## 性能（M0 门禁）

`perf/wpf_perf.json`（12 标签，1600×1000 窗口，Viewbox 缩放 1200×800 图表）：

| 场景 | 结果 |
| --- | --- |
| 拖动标签 180 次 | 更新 p50 0.15ms / p95 0.38ms；帧间隔 p95 16.66ms（≈60fps） |
| 样式重建 60 次 | 构建 p50 0.56ms / p95 0.78ms；帧间隔 p95 15.26ms |
| 窗口缩放 40 步 | 无图表重建；缩放事件期间 p95 29.5ms |

复现：

```powershell
dotnet build .\RoseChartStudio.PerfHarness\RoseChartStudio.PerfHarness.csproj -c Release -m:1 -nr:false
.\RoseChartStudio.PerfHarness\bin\Release\net10.0-windows\RoseChartStudio.PerfHarness.exe
```

## 测试

- `test_runner.txt`：**172/172 通过**（色板 138、Excel/列识别 19、场景/几何 8）。
- 本会话沙箱下 VSTest testhost 无法启动（`Win32Exception(5)`），所以用 `RoseChartStudio.TestRunner` 直接反射执行同一测试程序集；普通环境可直接 `dotnet test`。

## 工具与注意事项

- `printwindow_shot.py`：从 hwnd 抓取窗口客户区（包括被遮挡窗口），即截图的采集方式；可在任意机器上复现。
- 正式证据在 `_qa/shots/final/`；`contact_sheet.png` 为 6 个关键状态的并排总览。
- 旧 Python 应用的 UI/性能证据在 `rose/_qa/`，两套并行保留，便于回退对照。
## Excel 临时目录回归（2026-10-23）

- 现象：打开 Excel 时 `Access to the path '...\AppData\Local\Temp\tmp*.tmp' is denied`。
- 原因：Excel 库在受限 `%TEMP%` 下创建临时文件失败。
- 修复：应用启动时把进程 `TMP/TEMP/TMPDIR` 重定向到程序目录 `.tmp`（回退 `%LOCALAPPDATA%\RoseChartStudio\temp`），并在 ExcelService 错误信息中加入可写目录提示。
- 验证：以 `TEMP=C:\Windows\System32` 启动 Release 版并 `--sample --export`，成功读取并导出 PNG；普通环境与恢复后均正常。
