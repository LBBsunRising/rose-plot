using System.Collections.ObjectModel;
using System.Data;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using Microsoft.Win32;
using RoseChartStudio.App.Controls;
using RoseChartStudio.App.Models;
using RoseChartStudio.App.Services;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;
using RoseChartStudio.Core.Palettes;
using RoseChartStudio.Core.Parsing;
using RoseChartStudio.Core.Services;
using RoseChartStudio.Rendering;
using MenuItem = System.Windows.Controls.MenuItem;

namespace RoseChartStudio.App;

/// <summary>
/// Material 3 workbench: any Excel column can become a rose chart. The chart list is
/// dynamic, so the window is no longer hard-wired to "project statistics" and
/// "status statistics".
/// </summary>
public partial class MainWindow : Window
{
    private readonly ExcelService _excel = new();
    private readonly SettingsService _settingsService = new();
    private AppSettingsDocument _settings = new();
    private readonly ChartStyle _style = new();
    private readonly ExportSettings _export = new();
    private readonly ObservableCollection<ChartState> _charts = new();
    private readonly ObservableCollection<ColumnOption> _columns = new();

    private ChartState? _activeChart;
    private SheetTable? _sheet;
    private string? _filePath;
    private bool _pastedData;
    private DataTable? _editorTable;
    private DataTable? _hookedEditorTable;
    private int _contextRow = -1;
    private int _contextColumn = -1;
    private IReadOnlyList<string> _sheetNames = Array.Empty<string>();
    private bool _uiReady;
    private bool _suppress;
    private Dictionary<string, LayoutOffset>? _pendingUndo;
    private string? _selectedLabel;
    private string _groupFilter = "全部色系";
    private bool _populatingGroupFilter;
    private List<ChartStateDto> _pendingSavedCharts = new();
    private string? _pendingActiveColumn;
    private bool _pendingChartsConsumed;
    private bool _inlineTitleEditing;
    private string _titleBeforeInlineEdit = "";

    private const string AllGroups = "全部色系";

    public MainWindow()
    {
        InitializeComponent();
        BlankPasteGrid.LoadingRow += (_, e) =>
            e.Row.Header = (e.Row.GetIndex() + 1).ToString(CultureInfo.InvariantCulture);
        InitializeBlankPasteGrid();
        SheetPreviewGrid.LoadingRow += (_, e) =>
            e.Row.Header = (e.Row.GetIndex() + 2).ToString(CultureInfo.InvariantCulture);
        _export.OutputDirectory = Path.Combine(AppContext.BaseDirectory, "output");
        Directory.CreateDirectory(_export.OutputDirectory);
        _settings = _settingsService.Load();
        ApplyPersistedSettings();
        ChartTabs.ItemsSource = _charts;
        AllowDrop = true;
        Drop += OnWindowDrop;
        PreviewKeyDown += OnWindowPreviewKeyDown;
        ChartView.LabelSelected += OnLabelSelected;
        ChartView.LabelMoved += OnLabelMoved;
        ChartView.LabelMoveCompleted += OnLabelMoveCompleted;
        ChartView.LabelResetRequested += OnLabelResetRequested;
        ChartView.TitleEditRequested += OnTitleEditRequested;
        Loaded += OnWindowLoaded;
        Closing += OnWindowClosing;
    }

    private void ApplyPersistedSettings()
    {
        try
        {
            _style.CopyFrom(_settings.Style);
            _export.Format = _settings.Export.Format;
            _export.Preset = _settings.Export.Preset;
            _export.Width = _settings.Export.Width;
            _export.Height = _settings.Export.Height;
            _export.Dpi = _settings.Export.Dpi;
            _export.Transparent = _settings.Export.Transparent;
            _export.Filename = _settings.Export.Filename;
            if (!string.IsNullOrWhiteSpace(_settings.Export.OutputDirectory))
            {
                _export.OutputDirectory = _settings.Export.OutputDirectory;
            }
            Width = Math.Max(MinWidth, _settings.Window.Width);
            Height = Math.Max(MinHeight, _settings.Window.Height);
            if (_settings.Window.Maximized)
            {
                WindowState = WindowState.Maximized;
            }

            _pendingSavedCharts = _settings.Charts?
                .Where(chart => !string.IsNullOrWhiteSpace(chart.Column))
                .ToList() ?? new();
            _pendingActiveColumn = _settings.ActiveChartColumn;

            // v3 migration: fixed chart1/chart2 settings + category/status columns.
            if (_pendingSavedCharts.Count == 0 && !string.IsNullOrWhiteSpace(_settings.CategoryColumn))
            {
                _pendingSavedCharts.Add(MigrateLegacyChart(
                    _settings.CategoryColumn!, _settings.Chart1, "SW项目统计", "legacy_project"));
                if (!string.IsNullOrWhiteSpace(_settings.StatusColumn) &&
                    !string.Equals(_settings.StatusColumn, _settings.CategoryColumn, StringComparison.Ordinal))
                {
                    _pendingSavedCharts.Add(MigrateLegacyChart(
                        _settings.StatusColumn!, _settings.Chart2, "SW项目状态统计", "legacy_status"));
                }
                _pendingActiveColumn = string.Equals(_settings.ActiveChart, "chart2", StringComparison.Ordinal)
                    ? _settings.StatusColumn
                    : _settings.CategoryColumn;
            }
        }
        catch
        {
            // keep defaults on a broken settings file
        }
    }

    private static ChartStateDto MigrateLegacyChart(
        string column, ChartStateDto? source, string fallbackTitle, string fallbackPalette) => new()
    {
        Column = column,
        Name = string.IsNullOrWhiteSpace(source?.Name) ? column : source!.Name,
        Title = string.IsNullOrWhiteSpace(source?.Title) ? $"{column}统计" : source!.Title,
        Subtitle = source?.Subtitle ?? "",
        PaletteId = string.IsNullOrWhiteSpace(source?.PaletteId) ? fallbackPalette : source!.PaletteId,
        LabelMode = source?.LabelMode ?? "auto",
        LabelSingleColor = source?.LabelSingleColor ?? "#334155",
        SortMode = source?.SortMode ?? "count_desc",
        Overrides = source?.Overrides is null
            ? new Dictionary<string, string>(StringComparer.Ordinal)
            : new Dictionary<string, string>(source.Overrides, StringComparer.Ordinal),
        Layout = source?.Layout is null
            ? new Dictionary<string, LayoutOffset>(StringComparer.Ordinal)
            : new Dictionary<string, LayoutOffset>(source.Layout, StringComparer.Ordinal),
    };

    // ------------------------------------------------------------------
    // startup
    // ------------------------------------------------------------------

    private void OnWindowLoaded(object sender, RoutedEventArgs e)
    {
        PopulateGroupFilter();
        InitializeStyleControls();
        InitializeExportControls();
        _uiReady = true;

        var args = Environment.GetCommandLineArgs();
        var sampleIndex = Array.IndexOf(args, "--sample");
        if (sampleIndex >= 0)
        {
            var sample = sampleIndex + 1 < args.Length && !args[sampleIndex + 1].StartsWith("--", StringComparison.Ordinal)
                ? args[sampleIndex + 1]
                : FindSampleFile();
            if (!string.IsNullOrWhiteSpace(sample) && File.Exists(sample))
            {
                LoadWorkbook(sample);
            }
        }
        else
        {
            var fileIndex = Array.IndexOf(args, "--file");
            var initialFile = fileIndex >= 0 && fileIndex + 1 < args.Length &&
                              !args[fileIndex + 1].StartsWith("--", StringComparison.Ordinal)
                ? args[fileIndex + 1]
                : _settings.File;
            if (!string.IsNullOrWhiteSpace(initialFile) && File.Exists(initialFile))
            {
                LoadWorkbook(initialFile);
            }
        }

        if (_activeChart is null)
        {
            RefreshActiveChartUi();
            if (_sheet is null)
            {
                ShowPasteGrid();
            }
        }

        var tabIndex = Array.IndexOf(args, "--tab");
        if (tabIndex >= 0 && tabIndex + 1 < args.Length)
        {
            SelectRightTab(args[tabIndex + 1]);
        }
        if (Array.IndexOf(args, "--export") >= 0)
        {
            Dispatcher.BeginInvoke(new Action(() =>
            {
                ExportCurrentChart(reveal: false);
                Close();
            }), System.Windows.Threading.DispatcherPriority.Background);
        }
        var qaIndex = Array.IndexOf(args, "--qa");
        if (qaIndex >= 0)
        {
            var scenarios = new List<string>();
            for (var index = qaIndex + 1;
                 index < args.Length && !args[index].StartsWith("--", StringComparison.Ordinal);
                 index++)
            {
                scenarios.Add(args[index].ToLowerInvariant());
            }
            Dispatcher.BeginInvoke(
                new Action(() => RunQaScenarios(scenarios)),
                System.Windows.Threading.DispatcherPriority.Background);
        }
    }

    private static string? FindSampleFile()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "samples", "project_test_data.xlsx"),
            Path.Combine(AppContext.BaseDirectory, "examples", "project_test_data.xlsx"),
            @"C:\Users\admin\Desktop\rose-new\rose\examples\project_test_data.xlsx",
        };
        return candidates.FirstOrDefault(File.Exists);
    }

    private void PopulateGroupFilter()
    {
        _populatingGroupFilter = true;
        var groups = new List<string> { AllGroups };
        groups.AddRange(PaletteLibrary.GroupOrder);
        GroupFilterCombo.ItemsSource = groups;
        GroupFilterCombo.SelectedIndex = 0;
        _populatingGroupFilter = false;
    }

    // ------------------------------------------------------------------
    // workbook / column analysis
    // ------------------------------------------------------------------

    private void OpenFile_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "打开 Excel 数据",
            Filter = "Excel 工作簿 (*.xlsx;*.xlsm)|*.xlsx;*.xlsm|所有文件 (*.*)|*.*",
            CheckFileExists = true,
        };
        if (dialog.ShowDialog(this) == true)
        {
            LoadWorkbook(dialog.FileName);
        }
    }

    private void BrowseFile_Click(object sender, RoutedEventArgs e) => OpenFile_Click(sender, e);

    private void LoadWorkbook(string path)
    {
        try
        {
            _pastedData = false;
            SheetCombo.IsEnabled = true;
            _filePath = path;
            FileNameText.Text = Path.GetFileName(path);
            FileTextBox.Text = path;
            _sheetNames = _excel.GetSheetNames(path);
            _suppress = true;
            SheetCombo.ItemsSource = _sheetNames;
            SheetCombo.SelectedIndex = _sheetNames.Count > 0 ? 0 : -1;
            _suppress = false;
            if (_sheetNames.Count == 0)
            {
                SetStatus("工作簿中没有工作表", error: true);
                UpdateEmptyState();
                return;
            }
            LoadSheet(_sheetNames[0]);
            SetStatus($"已打开 {Path.GetFileName(path)}", error: false);
        }
        catch (Exception exception)
        {
            SetStatus("打开文件失败", error: true);
            MessageBox.Show(this, exception.Message, "打开 Excel 失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void LoadSheet(string sheetName)
    {
        if (_filePath is null)
        {
            return;
        }
        try
        {
            var sheet = _excel.ReadSheet(_filePath, sheetName);
            ApplySheet(sheet, sheetName, pasted: false);
        }
        catch (Exception exception)
        {
            SetStatus("读取工作表失败", error: true);
            MessageBox.Show(this, exception.Message, "读取工作表失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    /// <summary>Loads either an Excel sheet or pasted clipboard data into the workbench.</summary>
    private void ApplySheet(SheetTable sheet, string sourceLabel, bool pasted)
    {
        PasteGridOverlay.Visibility = Visibility.Collapsed;
        _sheet = sheet;
        _pastedData = pasted;
        if (pasted)
        {
            // Pasted data is a fresh source; do not restore charts from an Excel file.
            _pendingChartsConsumed = true;
            _pendingSavedCharts.Clear();
            _pendingActiveColumn = null;
        }
        BuildColumnOptions();
        RestoreOrCreateCharts();
        BuildSheetPreview();
        SetStatus(
            pasted
                ? $"已载入粘贴数据 · {sheet.RowCount} 行"
                : $"已读取工作表「{sourceLabel}」 · {sheet.RowCount} 行",
            error: false);
        UpdatePasteButtonText();
    }

    private void UpdatePasteButtonText()
    {
        if (PasteTableButtonText is not null)
        {
            PasteTableButtonText.Text = _sheet is null ? "粘贴表格" : "编辑数据";
        }
    }

    private void SetPastedSourceUi()
    {
        _filePath = null;
        _sheetNames = Array.Empty<string>();
        FileNameText.Text = "剪贴板数据";
        FileTextBox.Text = "已粘贴表格 · 无文件";
        _suppress = true;
        SheetCombo.ItemsSource = new[] { "粘贴数据" };
        SheetCombo.SelectedIndex = 0;
        SheetCombo.IsEnabled = false;
        _suppress = false;
        UpdatePasteButtonText();
    }

    private void ApplyEditedSheet(SheetTable sheet)
    {
        var activeColumn = _activeChart?.ColumnName;
        var keepCharts = _charts.Count > 0 &&
                         _charts.All(chart => sheet.Headers.Any(header =>
                             string.Equals(header, chart.ColumnName, StringComparison.Ordinal)));
        SetPastedSourceUi();
        _sheet = sheet;
        _pastedData = true;
        BuildColumnOptions();
        if (keepCharts)
        {
            RefreshColumnSelection();
            RebuildAllCharts();
            var desired = activeColumn is null
                ? null
                : _charts.FirstOrDefault(chart =>
                    string.Equals(chart.ColumnName, activeColumn, StringComparison.Ordinal));
            _activeChart = desired ?? _charts.FirstOrDefault();
            foreach (var chart in _charts)
            {
                chart.IsActive = ReferenceEquals(chart, _activeChart);
            }
        }
        else
        {
            _pendingChartsConsumed = true;
            _pendingSavedCharts.Clear();
            _pendingActiveColumn = null;
            RestoreOrCreateCharts();
        }
        BuildSheetPreview();
        PasteGridOverlay.Visibility = Visibility.Collapsed;
        RefreshActiveChartUi();
        UpdatePasteButtonText();
        SetStatus($"已生成图表 · {sheet.RowCount} 行", error: false);
    }

    private void PasteTable_Click(object sender, RoutedEventArgs e) => ShowPasteGrid();

    /// <summary>Builds the editable spreadsheet shown before and after generation.</summary>
    private void InitializeBlankPasteGrid()
    {
        _editorTable = new DataTable();
        for (var index = 0; index < 8; index++)
        {
            _editorTable.Columns.Add($"列{index + 1}", typeof(string));
        }
        for (var row = 0; row < 12; row++)
        {
            _editorTable.Rows.Add(new object[8]);
        }
        BindEditorTable();
    }

    private void BindEditorTable()
    {
        if (_editorTable is null)
        {
            return;
        }
        if (!ReferenceEquals(_hookedEditorTable, _editorTable))
        {
            _hookedEditorTable = _editorTable;
            _editorTable.ColumnChanged += (_, _) => UpdateEditorGenerateState();
            _editorTable.RowChanged += (_, _) => UpdateEditorGenerateState();
        }
        BlankPasteGrid.Columns.Clear();
        for (var index = 0; index < _editorTable.Columns.Count; index++)
        {
            BlankPasteGrid.Columns.Add(new DataGridTextColumn
            {
                Header = _editorTable.Columns[index].ColumnName,
                Binding = new Binding($"[{index}]"),
                Width = new DataGridLength(110),
                IsReadOnly = false,
                ElementStyle = BlankPasteCellStyle(),
            });
        }
        BlankPasteGrid.ItemsSource = _editorTable.DefaultView;
        UpdateEditorGenerateState();
        RefreshEditorRowHeaders();
    }

    private void RefreshEditorRowHeaders()
    {
        for (var index = 0; index < BlankPasteGrid.Items.Count; index++)
        {
            if (BlankPasteGrid.ItemContainerGenerator.ContainerFromIndex(index) is DataGridRow row)
            {
                row.Header = (index + 1).ToString(CultureInfo.InvariantCulture);
            }
        }
    }

    private static Style BlankPasteCellStyle()
    {
        var style = new Style(typeof(TextBlock));
        style.Setters.Add(new Setter(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center));
        style.Setters.Add(new Setter(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0)));
        return style;
    }

    private static string[] MakeEditorHeaders(IReadOnlyList<string> source, int columnCount)
    {
        var used = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var headers = new string[columnCount];
        for (var index = 0; index < columnCount; index++)
        {
            var raw = index < source.Count ? source[index].Trim() : "";
            var name = raw.Length > 0 ? raw : $"列{index + 1}";
            if (used.Contains(name))
            {
                var suffix = 2;
                var candidate = $"{name} ({suffix})";
                while (used.Contains(candidate))
                {
                    suffix++;
                    candidate = $"{name} ({suffix})";
                }
                name = candidate;
            }
            used.Add(name);
            headers[index] = name;
        }
        return headers;
    }

    private void PopulateEditorFromSheet(SheetTable? sheet)
    {
        var table = new DataTable();
        if (sheet is null)
        {
            for (var index = 0; index < 8; index++)
            {
                table.Columns.Add($"列{index + 1}", typeof(string));
            }
            for (var row = 0; row < 12; row++)
            {
                table.Rows.Add(new object[8]);
            }
        }
        else
        {
            var headers = MakeEditorHeaders(sheet.Headers, sheet.Headers.Count);
            foreach (var header in headers)
            {
                table.Columns.Add(header, typeof(string));
            }
            foreach (var source in sheet.Rows)
            {
                var cells = new object[headers.Length];
                for (var index = 0; index < headers.Length; index++)
                {
                    cells[index] = index < source.Count ? source[index] : "";
                }
                table.Rows.Add(cells);
            }
        }
        _editorTable = table;
        BindEditorTable();
    }

    private void UpdateEditorGenerateState()
    {
        var hasData = HasEditorData();
        GenerateChartButton.IsEnabled = hasData;
        CancelPasteGridButton.Visibility = hasData || _sheet is not null
            ? Visibility.Visible
            : Visibility.Collapsed;
    }

    private bool HasEditorData()
    {
        if (_editorTable is null)
        {
            return false;
        }
        foreach (DataRow row in _editorTable.Rows)
        {
            foreach (DataColumn column in _editorTable.Columns)
            {
                if (!string.IsNullOrWhiteSpace(row[column]?.ToString()))
                {
                    return true;
                }
            }
        }
        return false;
    }

    private void ShowPasteGrid()
    {
        PopulateEditorFromSheet(_sheet);
        PasteGridHeaderCheck.IsChecked = true;
        PasteGridStatus.Text = _sheet is null
            ? "支持 Tab、CSV、分号、竖线分隔；点击空白表格后按 Ctrl+V"
            : "可直接编辑单元格，完成后点击“生成图表”";
        CancelPasteGridButton.Visibility = _sheet is not null
            ? Visibility.Visible
            : Visibility.Collapsed;
        PasteGridOverlay.Visibility = Visibility.Visible;
        EmptyOverlay.Visibility = Visibility.Collapsed;
        TitleEditButton.Visibility = Visibility.Collapsed;
        DragHintText.Visibility = Visibility.Collapsed;
        LayoutStateText.Visibility = Visibility.Collapsed;
        if (_editorTable is { Rows.Count: > 0, Columns.Count: > 0 })
        {
            SelectEditorCell(0, 0);
        }
        else
        {
            BlankPasteGrid.Focus();
        }
    }

    private void HidePasteGrid()
    {
        PasteGridOverlay.Visibility = Visibility.Collapsed;
        DragHintText.Visibility = Visibility.Visible;
        LayoutStateText.Visibility = Visibility.Visible;
        if (_sheet is not null)
        {
            RefreshActiveChartUi();
        }
        else
        {
            UpdateEmptyState();
        }
        UpdatePasteButtonText();
    }

    private void PasteGridCancel_Click(object sender, RoutedEventArgs e) => HidePasteGrid();

    private void PasteGridClipboard_Click(object sender, RoutedEventArgs e) =>
        PasteClipboardIntoWorkbench();

    private void PasteGridOverlay_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.V && e.KeyboardDevice.Modifiers.HasFlag(ModifierKeys.Control))
        {
            PasteClipboardIntoWorkbench();
            e.Handled = true;
        }
    }

    private void PasteClipboardIntoWorkbench()
    {
        try
        {
            if (!Clipboard.ContainsText())
            {
                PasteGridStatus.Text = "剪贴板中没有可用的文本。";
                return;
            }
            var text = Clipboard.GetText();
            var result = TabularDataParser.Parse(text, PasteGridHeaderCheck.IsChecked == true);
            if (!result.Success || result.Table is null)
            {
                PasteGridStatus.Text = result.Error ?? "无法识别剪贴板中的表格。";
                return;
            }
            PopulateEditorFromSheet(result.Table);
            if (_editorTable is { Rows.Count: > 0, Columns.Count: > 0 })
            {
                SelectEditorCell(0, 0);
            }
            PasteGridStatus.Text =
                $"已识别 {result.Table.RowCount} 行 × {result.Table.Headers.Count} 列；可直接编辑，完成后点击“生成图表”";
        }
        catch (Exception exception)
        {
            PasteGridStatus.Text = $"无法读取剪贴板：{exception.Message}";
        }
    }

    private void CommitEditorEdits()
    {
        BlankPasteGrid.CommitEdit(DataGridEditingUnit.Cell, true);
        BlankPasteGrid.CommitEdit(DataGridEditingUnit.Row, true);
    }

    private int GetSelectedEditorRow()
    {
        var cell = BlankPasteGrid.CurrentCell;
        if (!cell.IsValid && BlankPasteGrid.SelectedCells.Count > 0)
        {
            cell = BlankPasteGrid.SelectedCells[0];
        }
        if (!cell.IsValid || _editorTable is null || cell.Item is not DataRowView rowView)
        {
            return -1;
        }
        return _editorTable.Rows.IndexOf(rowView.Row);
    }

    private int GetSelectedEditorColumn()
    {
        var cell = BlankPasteGrid.CurrentCell;
        if (!cell.IsValid && BlankPasteGrid.SelectedCells.Count > 0)
        {
            cell = BlankPasteGrid.SelectedCells[0];
        }
        return cell.IsValid ? BlankPasteGrid.Columns.IndexOf(cell.Column) : -1;
    }

    private void SelectEditorCell(int rowIndex, int columnIndex)
    {
        if (_editorTable is null || BlankPasteGrid.Items.Count == 0 || BlankPasteGrid.Columns.Count == 0)
        {
            return;
        }
        rowIndex = Math.Clamp(rowIndex, 0, BlankPasteGrid.Items.Count - 1);
        columnIndex = Math.Clamp(columnIndex, 0, BlankPasteGrid.Columns.Count - 1);
        var item = BlankPasteGrid.Items[rowIndex];
        var column = BlankPasteGrid.Columns[columnIndex];
        BlankPasteGrid.CurrentCell = new DataGridCellInfo(item, column);
        BlankPasteGrid.ScrollIntoView(item, column);
        BlankPasteGrid.Focus();
    }

    private string NextEditorColumnName()
    {
        var index = 1;
        while (_editorTable?.Columns.Contains($"新列{index}") == true)
        {
            index++;
        }
        return $"新列{index}";
    }

    private void InsertRowAt(int index)
    {
        if (_editorTable is null)
        {
            return;
        }
        CommitEditorEdits();
        index = Math.Clamp(index, 0, _editorTable.Rows.Count);
        _editorTable.Rows.InsertAt(_editorTable.NewRow(), index);
        UpdateEditorGenerateState();
        RefreshEditorRowHeaders();
        SelectEditorCell(index, Math.Max(0, GetSelectedEditorColumn()));
        PasteGridStatus.Text = "已插入一行，可继续编辑";
    }

    private void DeleteRowAt(int index)
    {
        if (_editorTable is null || _editorTable.Rows.Count == 0)
        {
            return;
        }
        CommitEditorEdits();
        index = Math.Clamp(index, 0, _editorTable.Rows.Count - 1);
        _editorTable.Rows.RemoveAt(index);
        UpdateEditorGenerateState();
        RefreshEditorRowHeaders();
        if (_editorTable.Rows.Count > 0)
        {
            SelectEditorCell(Math.Min(index, _editorTable.Rows.Count - 1),
                Math.Max(0, GetSelectedEditorColumn()));
        }
        PasteGridStatus.Text = "已删除一行";
    }

    private void InsertColumnAt(int index)
    {
        if (_editorTable is null)
        {
            return;
        }
        CommitEditorEdits();
        index = Math.Clamp(index, 0, _editorTable.Columns.Count);
        var rowIndex = Math.Max(0, GetSelectedEditorRow());
        var column = _editorTable.Columns.Add(NextEditorColumnName(), typeof(string));
        column.SetOrdinal(index);
        BindEditorTable();
        SelectEditorCell(rowIndex, index);
        PasteGridStatus.Text = "已插入一列，可继续编辑";
    }

    private void DeleteColumnAt(int index)
    {
        if (_editorTable is null || _editorTable.Columns.Count <= 1)
        {
            PasteGridStatus.Text = "至少保留一列。";
            return;
        }
        CommitEditorEdits();
        index = Math.Clamp(index, 0, _editorTable.Columns.Count - 1);
        var rowIndex = Math.Max(0, GetSelectedEditorRow());
        _editorTable.Columns.RemoveAt(index);
        BindEditorTable();
        SelectEditorCell(rowIndex, Math.Min(index, _editorTable.Columns.Count - 1));
        PasteGridStatus.Text = "已删除一列";
    }

    private void BlankPasteGrid_PreviewMouseRightButtonDown(object sender, MouseButtonEventArgs e)
    {
        CommitEditorEdits();
        _contextRow = -1;
        _contextColumn = -1;
        var source = e.OriginalSource as DependencyObject;
        var columnHeader = FindAncestor<DataGridColumnHeader>(source);
        var rowHeader = FindAncestor<DataGridRowHeader>(source);
        var cell = FindAncestor<DataGridCell>(source);
        var row = FindAncestor<DataGridRow>(source);

        if (columnHeader is not null)
        {
            _contextColumn = BlankPasteGrid.Columns.IndexOf(columnHeader.Column);
        }
        else if (rowHeader is not null)
        {
            var owner = FindAncestor<DataGridRow>(rowHeader);
            _contextRow = owner?.GetIndex() ?? -1;
        }
        else if (cell is not null)
        {
            _contextColumn = BlankPasteGrid.Columns.IndexOf(cell.Column);
            var owner = FindAncestor<DataGridRow>(cell);
            _contextRow = owner?.GetIndex() ?? GetSelectedEditorRow();
            if (_contextRow >= 0 && _contextColumn >= 0)
            {
                SelectEditorCell(_contextRow, _contextColumn);
            }
        }
        else if (row is not null)
        {
            _contextRow = row.GetIndex();
            _contextColumn = GetSelectedEditorColumn();
        }

        if (_contextRow < 0 && _contextColumn < 0)
        {
            BlankPasteGrid.ContextMenu = null;
            return;
        }

        var menu = new ContextMenu();
        if (_contextRow >= 0)
        {
            var rowIndex = _contextRow;
            menu.Items.Add(ContextItem("在上方插入行", () => InsertRowAt(rowIndex)));
            menu.Items.Add(ContextItem("在下方插入行", () => InsertRowAt(rowIndex + 1)));
            var deleteRow = ContextItem("删除行", () => DeleteRowAt(rowIndex));
            deleteRow.IsEnabled = _editorTable is { Rows.Count: > 0 };
            menu.Items.Add(deleteRow);
        }
        if (_contextRow >= 0 && _contextColumn >= 0)
        {
            menu.Items.Add(new Separator());
        }
        if (_contextColumn >= 0)
        {
            var columnIndex = _contextColumn;
            menu.Items.Add(ContextItem("在左侧插入列", () => InsertColumnAt(columnIndex)));
            menu.Items.Add(ContextItem("在右侧插入列", () => InsertColumnAt(columnIndex + 1)));
            var deleteColumn = ContextItem("删除列", () => DeleteColumnAt(columnIndex));
            deleteColumn.IsEnabled = _editorTable is { Columns.Count: > 1 };
            menu.Items.Add(deleteColumn);
        }

        BlankPasteGrid.ContextMenu = menu;
        menu.PlacementTarget = BlankPasteGrid;
        menu.IsOpen = true;
        e.Handled = true;
    }

    private static MenuItem ContextItem(string header, Action action)
    {
        var item = new MenuItem { Header = header };
        item.Click += (_, _) => action();
        return item;
    }

    private static T? FindAncestor<T>(DependencyObject? current) where T : DependencyObject
    {
        while (current is not null)
        {
            if (current is T match)
            {
                return match;
            }
            try
            {
                current = VisualTreeHelper.GetParent(current);
            }
            catch
            {
                current = LogicalTreeHelper.GetParent(current);
            }
        }
        return null;
    }
    private void GenerateChart_Click(object sender, RoutedEventArgs e)
    {
        if (_editorTable is null)
        {
            return;
        }
        BlankPasteGrid.CommitEdit(DataGridEditingUnit.Cell, true);
        BlankPasteGrid.CommitEdit(DataGridEditingUnit.Row, true);
        var sheet = ReadSheetFromEditor();
        if (sheet is null)
        {
            PasteGridStatus.Text = "表格中还没有可生成图表的数据，请先粘贴或输入内容。";
            return;
        }
        ApplyEditedSheet(sheet);
    }

    private SheetTable? ReadSheetFromEditor()
    {
        if (_editorTable is null || _editorTable.Columns.Count == 0)
        {
            return null;
        }
        var headers = _editorTable.Columns
            .Cast<DataColumn>()
            .Select(column => column.ColumnName.Trim())
            .ToList();
        var rows = _editorTable.Rows
            .Cast<DataRow>()
            .Select(row => _editorTable.Columns
                .Cast<DataColumn>()
                .Select(column => row[column]?.ToString()?.Trim() ?? "")
                .ToArray())
            .ToList();

        var lastRow = -1;
        var lastColumn = -1;
        for (var rowIndex = 0; rowIndex < rows.Count; rowIndex++)
        {
            for (var columnIndex = 0; columnIndex < headers.Count; columnIndex++)
            {
                if (!string.IsNullOrWhiteSpace(rows[rowIndex][columnIndex]))
                {
                    lastRow = rowIndex;
                    lastColumn = Math.Max(lastColumn, columnIndex);
                }
            }
        }
        if (lastRow < 0 || lastColumn < 0)
        {
            return null;
        }

        var trimmedHeaders = headers.Take(lastColumn + 1).ToArray();
        var trimmedRows = rows
            .Take(lastRow + 1)
            .Select(row => (IReadOnlyList<string>)row.Take(lastColumn + 1).ToArray())
            .ToList();
        for (var index = 0; index < trimmedHeaders.Length; index++)
        {
            if (string.IsNullOrWhiteSpace(trimmedHeaders[index]))
            {
                trimmedHeaders[index] = $"列{index + 1}";
            }
        }
        return new SheetTable
        {
            SheetName = "粘贴数据",
            Headers = trimmedHeaders,
            Rows = trimmedRows,
        };
    }

    private void BuildColumnOptions()
    {
        _columns.Clear();
        if (_sheet is null)
        {
            ColumnOptionsSummary.Text = "未打开文件";
            return;
        }
        foreach (var header in _sheet.Headers)
        {
            _columns.Add(new ColumnOption { Name = header });
        }
        ColumnOptionsSummary.Text = $"{_sheet.Headers.Count} 列";
    }

    private void BuildSheetPreview()
    {
        SheetPreviewGrid.Columns.Clear();
        SheetPreviewGrid.ItemsSource = null;
        if (_sheet is null || _sheet.Headers.Count == 0)
        {
            SheetPreviewGrid.Visibility = Visibility.Collapsed;
            PreviewEmpty.Visibility = Visibility.Visible;
            ColumnOptionsSummary.Text = "未打开文件";
            return;
        }

        var headerTemplate = (DataTemplate)FindResource("PreviewColumnHeaderTemplate");
        for (var index = 0; index < _sheet.Headers.Count; index++)
        {
            var option = _columns[index];
            SheetPreviewGrid.Columns.Add(new DataGridTemplateColumn
            {
                Header = option,
                HeaderTemplate = headerTemplate,
                CellTemplate = CreatePreviewCellTemplate(index),
                Width = new DataGridLength(112),
                CanUserSort = false,
                CanUserResize = false,
                CanUserReorder = false,
            });
        }
        var rows = _sheet.Rows
            .Take(6)
            .Select(row => new SheetPreviewRow { Cells = row })
            .ToList();
        SheetPreviewGrid.ItemsSource = rows;
        PreviewEmpty.Visibility = Visibility.Collapsed;
        SheetPreviewGrid.Visibility = Visibility.Visible;
        ColumnOptionsSummary.Text = $"{_sheet.Headers.Count} 列 · {_charts.Count} 图";
    }

    private static DataTemplate CreatePreviewCellTemplate(int columnIndex)
    {
        var factory = new FrameworkElementFactory(typeof(TextBlock));
        factory.SetValue(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0));
        factory.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);
        factory.SetValue(TextBlock.FontSizeProperty, 12.0);
        factory.SetValue(TextBlock.TextTrimmingProperty, TextTrimming.CharacterEllipsis);
        factory.SetResourceReference(TextBlock.ForegroundProperty, "Text");
        factory.SetBinding(TextBlock.TextProperty, new Binding($"Cells[{columnIndex}]"));
        return new DataTemplate { VisualTree = factory };
    }

    private void RestoreOrCreateCharts()
    {
        if (_sheet is null)
        {
            return;
        }
        _suppress = true;
        _charts.Clear();
        _activeChart = null;

        if (!_pendingChartsConsumed && _pendingSavedCharts.Count > 0)
        {
            foreach (var dto in _pendingSavedCharts)
            {
                if (_columns.All(option => option.Name != dto.Column))
                {
                    continue;
                }
                var chart = CreateChart(dto.Column, dto);
                _charts.Add(chart);
            }
            if (_charts.Count > 0)
            {
                _pendingChartsConsumed = true;
            }
        }
        if (_charts.Count == 0)
        {
            _pendingChartsConsumed = true;
            foreach (var column in SuggestColumns())
            {
                var chart = CreateChart(column, null);
                _charts.Add(chart);
            }
        }

        var desired = _pendingActiveColumn is not null
            ? _charts.FirstOrDefault(chart => string.Equals(chart.ColumnName, _pendingActiveColumn, StringComparison.Ordinal))
            : null;
        _activeChart = desired ?? _charts.FirstOrDefault();
        foreach (var chart in _charts)
        {
            chart.IsActive = ReferenceEquals(chart, _activeChart);
        }
        _suppress = false;
        RefreshColumnSelection();
        RefreshActiveChartUi();
    }

    private IEnumerable<string> SuggestColumns()
    {
        if (_sheet is null)
        {
            return Array.Empty<string>();
        }
        var detected = ColumnDetector.Detect(_sheet);
        var suggestions = new List<string>();
        if (!string.IsNullOrWhiteSpace(detected.CategoryColumn))
        {
            suggestions.Add(detected.CategoryColumn);
        }
        if (!string.IsNullOrWhiteSpace(detected.StatusColumn) &&
            !suggestions.Contains(detected.StatusColumn, StringComparer.Ordinal))
        {
            suggestions.Add(detected.StatusColumn);
        }
        if (suggestions.Count == 0)
        {
            var skipKeywords = new[] { "编号", "序号", "id", "index", "日期", "时间", "备注" };
            foreach (var header in _sheet.Headers)
            {
                if (skipKeywords.Any(keyword => header.Contains(keyword, StringComparison.OrdinalIgnoreCase)))
                {
                    continue;
                }
                suggestions.Add(header);
                if (suggestions.Count >= 2)
                {
                    break;
                }
            }
        }
        return suggestions;
    }

    private ChartState CreateChart(string column, ChartStateDto? dto)
    {
        var chart = new ChartState(column, dto?.PaletteId)
        {
            Name = string.IsNullOrWhiteSpace(dto?.Name) ? column : dto!.Name,
            Title = string.IsNullOrWhiteSpace(dto?.Title) ? $"{column}统计" : dto!.Title,
            Subtitle = dto?.Subtitle ?? "",
            LabelMode = string.IsNullOrWhiteSpace(dto?.LabelMode) ? "auto" : dto!.LabelMode,
            LabelSingleColor = string.IsNullOrWhiteSpace(dto?.LabelSingleColor) ? "#334155" : dto!.LabelSingleColor,
            SortMode = string.IsNullOrWhiteSpace(dto?.SortMode) ? "count_desc" : dto!.SortMode,
        };
        if (dto?.Overrides is not null)
        {
            foreach (var pair in dto.Overrides)
            {
                chart.Overrides[pair.Key] = pair.Value;
            }
        }
        if (dto?.Layout is not null)
        {
            chart.Layout = new Dictionary<string, LayoutOffset>(dto.Layout, StringComparer.Ordinal);
        }
        RebuildChartData(chart);
        return chart;
    }

    private void RebuildAllCharts()
    {
        foreach (var chart in _charts)
        {
            RebuildChartData(chart);
        }
    }

    private void RebuildChartData(ChartState chart)
    {
        if (_sheet is null)
        {
            chart.Counts = new List<CountItem>();
        }
        else
        {
            chart.Counts = ColumnCounter.Count(_sheet, chart.ColumnName).ToList();
        }
        SortCounts(chart);
        chart.Labels = chart.Counts.Select(item => item.Value).ToList();
        chart.Values = chart.Counts.Select(item => item.Count).ToList();
        if (string.IsNullOrWhiteSpace(chart.PaletteId) && chart.Labels.Count > 0)
        {
            chart.PaletteId = PaletteLibrary.Recommend(chart.Labels.Count, 1)
                .FirstOrDefault()?.Id ?? "legacy_project";
        }
        RecomputeColors(chart);
        BuildScene(chart);
    }

    private static void SortCounts(ChartState chart)
    {
        var ascending = string.Equals(chart.SortMode, "count_asc", StringComparison.Ordinal);
        chart.Counts = (ascending
                ? chart.Counts.OrderBy(item => item.Count).ThenBy(item => item.Value, StringComparer.Ordinal)
                : chart.Counts.OrderByDescending(item => item.Count).ThenBy(item => item.Value, StringComparer.Ordinal))
            .ToList();
    }

    private void RecomputeColors(ChartState chart)
    {
        var palette = GetPalette(chart.PaletteId);
        chart.FillColors = PaletteLibrary.AssignColors(palette, chart.Labels, chart.Overrides);
        var colors = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var label in chart.Labels)
        {
            var fill = chart.FillColors.TryGetValue(label, out var value) ? value : "#CCCCCC";
            var color = PaletteLibrary.LabelColor(fill, chart.LabelMode, chart.LabelSingleColor);
            if (string.Equals(chart.LabelMode, "auto", StringComparison.Ordinal))
            {
                color = EnsureLabelContrast(color);
            }
            colors[label] = color;
        }
        chart.LabelColors = colors;
    }

    private static string EnsureLabelContrast(string color)
    {
        const double target = 4.0;
        if (PaletteLibrary.ContrastRatio(color, "#FFFFFF") >= target)
        {
            return color;
        }
        var current = color;
        var luminance = PaletteLibrary.Luminance(current);
        for (var index = 0; index < 24; index++)
        {
            current = luminance > 0.45
                ? PaletteLibrary.Darken(current, 0.07)
                : PaletteLibrary.Lighten(current, 0.07);
            if (PaletteLibrary.ContrastRatio(current, "#FFFFFF") >= target)
            {
                return current;
            }
        }
        return "#191C1B";
    }

    private static Palette GetPalette(string paletteId)
    {
        try
        {
            return PaletteLibrary.ById(paletteId);
        }
        catch (KeyNotFoundException)
        {
            return PaletteLibrary.ById("legacy_project");
        }
    }

    private void BuildScene(ChartState chart)
    {
        var style = _style.Clone();
        style.Title = chart.Title;
        style.Subtitle = chart.Subtitle;
        var spec = new ChartSpec
        {
            Labels = chart.Labels.ToList(),
            Values = chart.Values.ToList(),
            Style = style,
            FillColors = new Dictionary<string, string>(chart.FillColors, StringComparer.Ordinal),
            LabelColors = new Dictionary<string, string>(chart.LabelColors, StringComparer.Ordinal),
            LayoutOffsets = new Dictionary<string, LayoutOffset>(chart.Layout, StringComparer.Ordinal),
        };
        try
        {
            chart.Scene = ChartSceneBuilder.Build(spec);
        }
        catch (Exception exception)
        {
            chart.Scene = null;
            SetStatus($"绘制失败：{exception.Message}", error: true);
        }
    }

    private void SheetCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        if (SheetCombo.SelectedItem is string sheetName)
        {
            LoadSheet(sheetName);
        }
    }

    private void ColumnOption_Toggled(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress || sender is not CheckBox { DataContext: ColumnOption option })
        {
            return;
        }
        if (option.IsSelected)
        {
            AddChartForColumn(option);
        }
        else
        {
            var chart = _charts.FirstOrDefault(c => c.ColumnName == option.Name);
            if (chart is not null)
            {
                RemoveChart(chart);
            }
        }
    }

    private void AddChartForColumn(ColumnOption option)
    {
        if (_charts.Any(chart => string.Equals(chart.ColumnName, option.Name, StringComparison.Ordinal)))
        {
            return;
        }
        var chart = CreateChart(option.Name, null);
        _charts.Add(chart);
        RefreshColumnSelection();
        ActivateChart(chart);
    }

    private void AddChart_Click(object sender, RoutedEventArgs e)
    {
        var menu = new ContextMenu { PlacementTarget = AddChartButton };
        var available = _columns.Where(column =>
            _charts.All(chart => !string.Equals(chart.ColumnName, column.Name, StringComparison.Ordinal))).ToList();
        if (available.Count == 0)
        {
            menu.Items.Add(new MenuItem { Header = "所有列都已生成图表", IsEnabled = false });
        }
        else
        {
            foreach (var column in available)
            {
                var item = new MenuItem { Header = column.Name };
                item.Click += (_, _) => AddChartForColumn(column);
                menu.Items.Add(item);
            }
        }
        menu.IsOpen = true;
    }

    private void DeleteChart_Click(object sender, RoutedEventArgs e)
    {
        if (_activeChart is not null)
        {
            RemoveChart(_activeChart);
        }
    }

    private void RemoveChart(ChartState chart)
    {
        if (_inlineTitleEditing)
        {
            FinishInlineTitleEdit(commit: true);
        }
        var index = _charts.IndexOf(chart);
        if (index < 0)
        {
            return;
        }
        var wasActive = ReferenceEquals(chart, _activeChart);
        _charts.RemoveAt(index);
        chart.IsActive = false;
        if (wasActive)
        {
            _activeChart = _charts.Count == 0
                ? null
                : _charts[Math.Clamp(index, 0, _charts.Count - 1)];
            if (_activeChart is not null)
            {
                _activeChart.IsActive = true;
            }
        }
        RefreshColumnSelection();
        RefreshActiveChartUi();
        if (_activeChart is null)
        {
            UpdateEmptyState();
        }
    }

    private void RefreshColumnSelection()
    {
        _suppress = true;
        foreach (var option in _columns)
        {
            option.IsSelected = _charts.Any(chart =>
                string.Equals(chart.ColumnName, option.Name, StringComparison.Ordinal));
        }
        _suppress = false;
        RefreshColumnSummary();
    }

    private void RefreshColumnSummary()
    {
        ColumnOptionsSummary.Text = _sheet is null
            ? "未打开文件"
            : $"{_sheet.Headers.Count} 列 · {_charts.Count} 图";
    }

    private void ChartTab_Checked(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress || sender is not RadioButton { DataContext: ChartState chart })
        {
            return;
        }
        if (ReferenceEquals(chart, _activeChart))
        {
            return;
        }
        ActivateChart(chart);
    }

    private void ChartTab_DoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (sender is not FrameworkElement { DataContext: ChartState chart })
        {
            return;
        }
        ActivateChart(chart);
        ChartNameBox.Focus();
        ChartNameBox.SelectAll();
        ChartNameBox.BringIntoView();
        e.Handled = true;
    }

    private void ActivateChart(ChartState chart)
    {
        if (_inlineTitleEditing)
        {
            FinishInlineTitleEdit(commit: true);
        }
        _activeChart = chart;
        foreach (var item in _charts)
        {
            item.IsActive = ReferenceEquals(item, chart);
        }
        _selectedLabel = null;
        RefreshActiveChartUi();
    }

    private void RefreshActiveChartUi()
    {
        _suppress = true;
        if (_activeChart is null)
        {
            TitleBox.Text = "";
            SubtitleBox.Text = "";
            ChartNameBox.Text = "";
            ChartNameBox.IsEnabled = false;
            ChartTitleBox.Text = "";
            ChartTitleBox.IsEnabled = false;
            SortCombo.SelectedIndex = 0;
            ApplyLabelModeToUi("auto");
            ActiveColumnText.Text = "—";
            ActiveColumnChip.Visibility = Visibility.Collapsed;
            DeleteChartButton.IsEnabled = false;
            SortCombo.IsEnabled = false;
            TitleEditButton.Visibility = Visibility.Collapsed;
            ChartRows.ItemsSource = null;
            ChartEmpty.Visibility = Visibility.Visible;
            ActiveChartCaption.Text = "未选择列";
        }
        else
        {
            TitleBox.Text = _activeChart.Title;
            SubtitleBox.Text = _activeChart.Subtitle;
            ChartNameBox.Text = _activeChart.Name;
            ChartNameBox.IsEnabled = true;
            ChartTitleBox.Text = _activeChart.Title;
            ChartTitleBox.IsEnabled = true;
            SortCombo.SelectedIndex = string.Equals(_activeChart.SortMode, "count_asc", StringComparison.Ordinal) ? 1 : 0;
            ApplyLabelModeToUi(_activeChart.LabelMode);
            ActiveColumnText.Text = _activeChart.ColumnName;
            ActiveColumnChip.Visibility = Visibility.Visible;
            DeleteChartButton.IsEnabled = true;
            SortCombo.IsEnabled = true;
            TitleEditButton.Visibility = _activeChart.Scene is not null
                ? Visibility.Visible
                : Visibility.Collapsed;
            UpdateTableForActiveChart();
        }
        _suppress = false;
        RenderActiveChart();
        RebuildPalettePage();
        UpdateStatusStats();
        UpdateActiveColumnCaption();
    }

    private void UpdateActiveColumnCaption()
    {
        if (_activeChart is null)
        {
            ActiveChartCaption.Text = "未选择列";
            return;
        }
        ActiveChartCaption.Text = $"{_activeChart.Counts.Count} 类";
    }

    private void UpdateTableForActiveChart()
    {
        if (_activeChart is null)
        {
            ChartRows.ItemsSource = null;
            ChartEmpty.Visibility = Visibility.Visible;
            return;
        }
        var total = _activeChart.Counts.Sum(item => item.Count);
        var rows = _activeChart.Counts.Select(item => new CountRow
        {
            Value = item.Value,
            Count = item.Count,
            ShareText = ((total > 0 ? item.Count / (double)total * 100.0 : 0))
                .ToString("F2", CultureInfo.InvariantCulture) + "%",
        }).ToList();
        ChartRows.ItemsSource = rows;
        ChartEmpty.Visibility = rows.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        ActiveChartCaption.Text = $"{rows.Count} 类";
    }

    private void RenderActiveChart()
    {
        if (_activeChart is null || _activeChart.Scene is null || _activeChart.Labels.Count == 0)
        {
            ChartView.ClearScene();
            UpdateEmptyState();
            DragHintText.Text = "";
            LayoutStateText.Text = "布局：无数据";
            AutoArrangeButton.IsEnabled = false;
            UpdateUndoButtons();
            return;
        }
        EmptyOverlay.Visibility = Visibility.Collapsed;
        ChartView.SetScene(_activeChart.Scene);
        ChartView.HighlightLabel(_selectedLabel);
        AutoArrangeButton.IsEnabled = true;
        DragHintText.Text = "拖动标签微调位置 · 双击标签复位 · 点击图表标题直接编辑";
        LayoutStateText.Text = _activeChart.Layout.Count > 0 ? "布局：自定义" : "布局：自动";
        UpdateUndoButtons();
    }

    private void UpdateEmptyState()
    {
        if (_sheet is null)
        {
            EmptyTitle.Text = "打开 Excel 或粘贴表格数据";
            EmptyDescription.Text = "打开一个 Excel 工作簿，或从剪贴板粘贴表格内容。";
            EmptyOpenButton.Visibility = Visibility.Visible;
            EmptyPasteButton.Visibility = Visibility.Visible;
        }
        else if (_columns.Count == 0)
        {
            EmptyTitle.Text = "这个数据源没有可分析的列";
            EmptyDescription.Text = "请确认第一行是表头，且至少有一列非空数据。";
            EmptyOpenButton.Visibility = Visibility.Collapsed;
            EmptyPasteButton.Visibility = Visibility.Collapsed;
        }
        else if (_activeChart is not null)
        {
            EmptyTitle.Text = "该列没有可统计的数据";
            EmptyDescription.Text = "这一列全是空值。换一个分析列，或补全数据。";
            EmptyOpenButton.Visibility = Visibility.Collapsed;
            EmptyPasteButton.Visibility = Visibility.Collapsed;
        }
        else
        {
            EmptyTitle.Text = "从左侧勾选一个分析列";
            EmptyDescription.Text = "每一列都可以生成一张玫瑰图，可同时打开多张。";
            EmptyOpenButton.Visibility = Visibility.Collapsed;
            EmptyPasteButton.Visibility = Visibility.Collapsed;
        }
        EmptyOverlay.Visibility = Visibility.Visible;
        ChartView.ClearScene();
        DragHintText.Text = "";
        LayoutStateText.Text = "布局：无数据";
        AutoArrangeButton.IsEnabled = false;
        ChartRows.ItemsSource = null;
        ChartEmpty.Visibility = Visibility.Visible;
        ActiveChartCaption.Text = "未选择列";
        if (_activeChart is null)
        {
            ActiveColumnChip.Visibility = Visibility.Collapsed;
            ActiveColumnText.Text = "—";
            DeleteChartButton.IsEnabled = false;
        }
    }

    private void SortCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_uiReady || _suppress || _activeChart is null)
        {
            return;
        }
        _activeChart.SortMode = SortCombo.SelectedIndex == 1 ? "count_asc" : "count_desc";
        SortCounts(_activeChart);
        _activeChart.Labels = _activeChart.Counts.Select(item => item.Value).ToList();
        _activeChart.Values = _activeChart.Counts.Select(item => item.Count).ToList();
        RecomputeColors(_activeChart);
        BuildScene(_activeChart);
        RefreshActiveChartUi();
        SetStatus($"排序：{(_activeChart.SortMode == "count_asc" ? "数量从少到多" : "数量从多到少")}", error: false);
    }

    private void CountRow_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button button || button.Tag is not string value || _activeChart is null)
        {
            return;
        }
        _selectedLabel = value;
        ChartView.HighlightLabel(value);
        SetStatus($"已定位标签「{value}」", error: false);
    }

    // ------------------------------------------------------------------
    // palette
    // ------------------------------------------------------------------

    private void RebuildPalettePage()
    {
        var chart = _activeChart;
        var currentId = chart?.PaletteId;
        var current = GetPalette(string.IsNullOrWhiteSpace(currentId) ? "legacy_project" : currentId!);
        CurrentPaletteSwatches.ItemsSource = current.Colors
            .Select(color => (Brush)new SolidColorBrush(ColorUtil.ToColor(color, Colors.Gray)))
            .ToList();
        CurrentPaletteName.Text = current.Name;
        CurrentPaletteMeta.Text = $"{current.Colors.Count} 色";

        var labelCount = chart?.Labels.Count ?? 0;
        var showRecommendations = labelCount > 0;
        RecommendTitle.Visibility = showRecommendations ? Visibility.Visible : Visibility.Collapsed;
        RecommendHint.Visibility = showRecommendations ? Visibility.Visible : Visibility.Collapsed;
        RecPalettes.Visibility = showRecommendations ? Visibility.Visible : Visibility.Collapsed;
        var recommended = showRecommendations
            ? PaletteLibrary.Recommend(labelCount, 4)
            : Array.Empty<Palette>();
        var recIds = recommended.Select(palette => palette.Id).ToHashSet(StringComparer.Ordinal);
        if (showRecommendations)
        {
            RecommendHint.Text = $"为 {labelCount} 个类别推荐";
            RecPalettes.ItemsSource = recommended
                .Select(palette => BuildPaletteCard(palette, palette.Id == currentId, ""))
                .ToList();
        }
        else
        {
            RecPalettes.ItemsSource = null;
        }

        var gallery = string.Equals(_groupFilter, AllGroups, StringComparison.Ordinal)
            ? PaletteLibrary.All
            : PaletteLibrary.ByGroup(_groupFilter);
        GalleryPalettes.ItemsSource = gallery
            .Select(palette =>
            {
                var duplicated = palette.Id == currentId && recIds.Contains(palette.Id);
                return BuildPaletteCard(palette, palette.Id == currentId && !duplicated, duplicated ? "已选" : "");
            })
            .ToList();

        var rows = new List<CategoryColorRow>();
        if (chart is not null)
        {
            var total = chart.Counts.Sum(item => item.Count);
            foreach (var label in chart.Labels)
            {
                var fill = chart.FillColors.TryGetValue(label, out var color) ? color : "#CCCCCC";
                var count = chart.Counts.FirstOrDefault(item => item.Value == label);
                rows.Add(new CategoryColorRow
                {
                    Label = label,
                    ColorHex = fill,
                    Brush = new SolidColorBrush(ColorUtil.ToColor(fill, Colors.Gray)),
                    Meta = count is null
                        ? ""
                        : $"{count.Count} · {(total > 0 ? count.Count / (double)total * 100 : 0):0}%",
                });
            }
        }
        CategoryColors.ItemsSource = rows;
        CategoryColorEmpty.Visibility = rows.Count == 0 ? Visibility.Visible : Visibility.Collapsed;

        _suppress = true;
        ApplyLabelModeToUi(chart?.LabelMode ?? "auto");
        _suppress = false;
        SingleLabelColorButton.Background = new SolidColorBrush(
            ColorUtil.ToColor(chart?.LabelSingleColor ?? "#334155", Colors.DarkSlateGray));
    }

    private static PaletteCardItem BuildPaletteCard(Palette palette, bool selected, string tag) => new()
    {
        Id = palette.Id,
        Name = palette.Name,
        Meta = $"{palette.Colors.Count} 色",
        Tag = tag,
        IsSelected = selected,
        Swatches = palette.Colors
            .Select(color => (Brush)new SolidColorBrush(ColorUtil.ToColor(color, Colors.Gray)))
            .ToList(),
    };

    private void PaletteCard_Click(object sender, RoutedEventArgs e)
    {
        if (_activeChart is null || sender is not Button button || button.Tag is not string paletteId)
        {
            return;
        }
        if (string.Equals(_activeChart.PaletteId, paletteId, StringComparison.Ordinal))
        {
            return;
        }
        _activeChart.PaletteId = paletteId;
        var palette = GetPalette(paletteId);
        RecomputeColors(_activeChart);
        BuildScene(_activeChart);
        RenderActiveChart();
        RebuildPalettePage();
        SetStatus($"已应用配色方案：{palette.Name}", error: false);
    }

    private void GroupFilter_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_uiReady || _populatingGroupFilter)
        {
            return;
        }
        _groupFilter = GroupFilterCombo.SelectedItem as string ?? AllGroups;
        RebuildPalettePage();
    }

    private void LabelMode_Checked(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress || _activeChart is null)
        {
            return;
        }
        _activeChart.LabelMode = LabelModeFollow.IsChecked == true
            ? "match"
            : LabelModeSingle.IsChecked == true ? "single" : "auto";
        RecomputeColors(_activeChart);
        BuildScene(_activeChart);
        RenderActiveChart();
        RebuildPalettePage();
        SetStatus($"标签配色：{LabelModeText(_activeChart.LabelMode)}", error: false);
    }

    private static string LabelModeText(string mode) => mode switch
    {
        "match" => "跟随扇区",
        "single" => "统一深色",
        _ => "自动加深",
    };

    private void SingleLabelColor_Click(object sender, RoutedEventArgs e)
    {
        if (_activeChart is null)
        {
            return;
        }
        var dialog = new ColorPickerDialog(_activeChart.LabelSingleColor, "选择统一标签颜色") { Owner = this };
        if (dialog.ShowDialog() != true)
        {
            return;
        }
        _activeChart.LabelSingleColor = dialog.SelectedHex;
        SingleLabelColorButton.Background = new SolidColorBrush(
            ColorUtil.ToColor(_activeChart.LabelSingleColor, Colors.Black));
        if (string.Equals(_activeChart.LabelMode, "single", StringComparison.Ordinal))
        {
            RecomputeColors(_activeChart);
            BuildScene(_activeChart);
            RenderActiveChart();
        }
        SetStatus("已更新统一标签颜色", error: false);
    }

    private void CategoryColor_Click(object sender, RoutedEventArgs e)
    {
        if (_activeChart is null || sender is not Button button || button.Tag is not string label)
        {
            return;
        }
        var initial = _activeChart.FillColors.TryGetValue(label, out var fill) ? fill : "#CCCCCC";
        var dialog = new ColorPickerDialog(initial, $"选择「{label}」的颜色") { Owner = this };
        if (dialog.ShowDialog() != true)
        {
            return;
        }
        _activeChart.Overrides[label] = dialog.SelectedHex;
        RecomputeColors(_activeChart);
        BuildScene(_activeChart);
        RenderActiveChart();
        RebuildPalettePage();
        SetStatus($"已设置「{label}」的颜色", error: false);
    }

    // ------------------------------------------------------------------
    // style
    // ------------------------------------------------------------------

    private void InitializeStyleControls()
    {
        _suppress = true;
        TitleFontSlider.Value = _style.TitleFontSize;
        InnerRadiusSlider.Value = _style.InnerRadius;
        OuterRadiusSlider.Value = _style.OuterRadius;
        StartAngleSlider.Value = _style.StartAngle;
        GapRatioSlider.Value = _style.GapRatio;
        CornerRadiusSlider.Value = _style.CornerRadius;
        EdgeWidthSlider.Value = _style.EdgeWidth;
        LabelFontSlider.Value = _style.LabelFontSize;
        LabelLineSlider.Value = _style.LabelLineWidth;
        LabelWireSlider.Value = _style.LabelWireScale;
        CenterFontSlider.Value = _style.CenterFontSize;
        ShowNameCheck.IsChecked = _style.ShowName;
        ShowValueCheck.IsChecked = _style.ShowValue;
        ShowPercentCheck.IsChecked = _style.ShowPercent;
        DecimalsBox.Text = _style.PercentDecimals.ToString(CultureInfo.InvariantCulture);
        SuffixBox.Text = _style.ValueSuffix;
        CenterTextBox.Text = _style.CenterText;
        var fontIndex = 0;
        for (var index = 0; index < FontFamilyCombo.Items.Count; index++)
        {
            if (FontFamilyCombo.Items[index] is ComboBoxItem item &&
                string.Equals(item.Content as string, _style.FontFamily, StringComparison.Ordinal))
            {
                fontIndex = index;
                break;
            }
        }
        FontFamilyCombo.SelectedIndex = fontIndex;
        EdgeColorButton.Background = new SolidColorBrush(ColorUtil.ToColor(_style.EdgeColor, Colors.White));
        CenterColorButton.Background = new SolidColorBrush(ColorUtil.ToColor(_style.CenterColor, Colors.Gray));
        UpdateStyleValueLabels();
        _suppress = false;
    }

    private void UpdateStyleValueLabels()
    {
        TitleFontValue.Text = _style.TitleFontSize.ToString("0.#", CultureInfo.InvariantCulture);
        InnerRadiusValue.Text = _style.InnerRadius.ToString("0.00", CultureInfo.InvariantCulture);
        OuterRadiusValue.Text = _style.OuterRadius.ToString("0.00", CultureInfo.InvariantCulture);
        StartAngleValue.Text = _style.StartAngle.ToString("0", CultureInfo.InvariantCulture);
        GapRatioValue.Text = _style.GapRatio.ToString("0.00", CultureInfo.InvariantCulture);
        CornerRadiusValue.Text = _style.CornerRadius.ToString("0.000", CultureInfo.InvariantCulture);
        EdgeWidthValue.Text = _style.EdgeWidth.ToString("0.0", CultureInfo.InvariantCulture);
        LabelFontValue.Text = _style.LabelFontSize.ToString("0.#", CultureInfo.InvariantCulture);
        LabelLineValue.Text = _style.LabelLineWidth.ToString("0.0", CultureInfo.InvariantCulture);
        LabelWireValue.Text = _style.LabelWireScale.ToString("0.0", CultureInfo.InvariantCulture);
        CenterFontValue.Text = _style.CenterFontSize.ToString("0.#", CultureInfo.InvariantCulture);
    }

    private void StyleSlider_Changed(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        if (ReferenceEquals(sender, TitleFontSlider)) _style.TitleFontSize = e.NewValue;
        else if (ReferenceEquals(sender, InnerRadiusSlider)) _style.InnerRadius = e.NewValue;
        else if (ReferenceEquals(sender, OuterRadiusSlider)) _style.OuterRadius = e.NewValue;
        else if (ReferenceEquals(sender, StartAngleSlider)) _style.StartAngle = e.NewValue;
        else if (ReferenceEquals(sender, GapRatioSlider)) _style.GapRatio = e.NewValue;
        else if (ReferenceEquals(sender, CornerRadiusSlider)) _style.CornerRadius = e.NewValue;
        else if (ReferenceEquals(sender, EdgeWidthSlider)) _style.EdgeWidth = e.NewValue;
        else if (ReferenceEquals(sender, LabelFontSlider)) _style.LabelFontSize = e.NewValue;
        else if (ReferenceEquals(sender, LabelLineSlider)) _style.LabelLineWidth = e.NewValue;
        else if (ReferenceEquals(sender, LabelWireSlider)) _style.LabelWireScale = e.NewValue;
        else if (ReferenceEquals(sender, CenterFontSlider)) _style.CenterFontSize = e.NewValue;
        UpdateStyleValueLabels();
        RebuildAllScenesForActiveStyle();
    }

    private void RebuildAllScenesForActiveStyle()
    {
        foreach (var chart in _charts)
        {
            BuildScene(chart);
        }
        RenderActiveChart();
        SetStatus("已更新样式", error: false);
    }

    private void TitleBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_uiReady || _suppress || _activeChart is null)
        {
            return;
        }
        _activeChart.Title = TitleBox.Text;
        SyncTitleField(ChartTitleBox, TitleBox.Text);
        BuildScene(_activeChart);
        RenderActiveChart();
    }

    private void ChartTitleBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_uiReady || _suppress || _activeChart is null)
        {
            return;
        }
        _activeChart.Title = ChartTitleBox.Text;
        SyncTitleField(TitleBox, ChartTitleBox.Text);
        BuildScene(_activeChart);
        RenderActiveChart();
    }

    private void SyncTitleField(TextBox target, string text)
    {
        if (string.Equals(target.Text, text, StringComparison.Ordinal))
        {
            return;
        }
        _suppress = true;
        target.Text = text;
        _suppress = false;
    }

    private void ChartNameBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_uiReady || _suppress || _activeChart is null)
        {
            return;
        }
        _activeChart.Name = ChartNameBox.Text.Trim();
    }

    // ------------------------------------------------------------------
    // inline title editing, directly on the preview canvas
    // ------------------------------------------------------------------

    private void OnTitleEditRequested(object? sender, EventArgs e)
    {
        if (_activeChart?.Scene is null || _inlineTitleEditing)
        {
            return;
        }
        _inlineTitleEditing = true;
        _titleBeforeInlineEdit = _activeChart.Title;
        InlineTitleBox.Text = _titleBeforeInlineEdit;
        InlineTitleBox.FontFamily = new FontFamily(
            string.IsNullOrWhiteSpace(_style.FontFamily) ? "Microsoft YaHei" : _style.FontFamily);
        InlineTitleBox.FontSize = Math.Max(18, _style.TitleFontSize * 100.0 / 72.0);
        InlineTitleBox.FontWeight = FontWeights.Bold;
        InlineTitleBox.Foreground = new SolidColorBrush(
            ColorUtil.ToColor(_style.TitleColor, Colors.DarkSlateGray));

        // Hide the rendered title while the overlay editor is on top of it.
        _activeChart.Title = "";
        BuildScene(_activeChart);
        RenderActiveChart();
        InlineTitleEditor.Visibility = Visibility.Visible;
        TitleEditButton.Visibility = Visibility.Collapsed;
        InlineTitleBox.Focus();
        InlineTitleBox.SelectAll();
    }

    private void TitleEditButton_Click(object sender, RoutedEventArgs e) =>
        OnTitleEditRequested(sender, EventArgs.Empty);

    private void InlineTitleBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            FinishInlineTitleEdit(commit: true);
            e.Handled = true;
        }
        else if (e.Key == Key.Escape)
        {
            FinishInlineTitleEdit(commit: false);
            e.Handled = true;
        }
    }

    private void InlineTitleBox_LostFocus(object sender, RoutedEventArgs e) =>
        FinishInlineTitleEdit(commit: true);

    private void FinishInlineTitleEdit(bool commit)
    {
        if (!_inlineTitleEditing)
        {
            return;
        }
        _inlineTitleEditing = false;
        InlineTitleEditor.Visibility = Visibility.Collapsed;
        if (_activeChart is not null)
        {
            _activeChart.Title = commit ? InlineTitleBox.Text.Trim() : _titleBeforeInlineEdit;
            BuildScene(_activeChart);
        }
        _titleBeforeInlineEdit = "";
        RefreshActiveChartUi();
        ChartView.Focus();
    }

    private void SubtitleBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_uiReady || _suppress || _activeChart is null)
        {
            return;
        }
        _activeChart.Subtitle = SubtitleBox.Text;
        BuildScene(_activeChart);
        RenderActiveChart();
    }

    private void LabelSwitch_Changed(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        _style.ShowName = ShowNameCheck.IsChecked == true;
        _style.ShowValue = ShowValueCheck.IsChecked == true;
        _style.ShowPercent = ShowPercentCheck.IsChecked == true;
        RebuildAllScenesForActiveStyle();
    }

    private void DecimalsBox_LostFocus(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        if (int.TryParse(DecimalsBox.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value))
        {
            _style.PercentDecimals = Math.Clamp(value, 0, 6);
        }
        DecimalsBox.Text = _style.PercentDecimals.ToString(CultureInfo.InvariantCulture);
        RebuildAllScenesForActiveStyle();
    }

    private void SuffixBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        _style.ValueSuffix = SuffixBox.Text;
        RebuildAllScenesForActiveStyle();
    }

    private void CenterTextBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        _style.CenterText = CenterTextBox.Text;
        RebuildAllScenesForActiveStyle();
    }

    private void FontFamily_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        if (FontFamilyCombo.SelectedItem is ComboBoxItem item && item.Content is string family)
        {
            _style.FontFamily = family;
            RebuildAllScenesForActiveStyle();
        }
    }

    private void EdgeColor_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new ColorPickerDialog(_style.EdgeColor, "选择扇区描边颜色") { Owner = this };
        if (dialog.ShowDialog() != true)
        {
            return;
        }
        _style.EdgeColor = dialog.SelectedHex;
        EdgeColorButton.Background = new SolidColorBrush(ColorUtil.ToColor(_style.EdgeColor, Colors.White));
        RebuildAllScenesForActiveStyle();
    }

    private void CenterColor_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new ColorPickerDialog(_style.CenterColor, "选择中心文字颜色") { Owner = this };
        if (dialog.ShowDialog() != true)
        {
            return;
        }
        _style.CenterColor = dialog.SelectedHex;
        CenterColorButton.Background = new SolidColorBrush(ColorUtil.ToColor(_style.CenterColor, Colors.Gray));
        RebuildAllScenesForActiveStyle();
    }

    private void ApplyLabelModeToUi(string mode)
    {
        LabelModeFollow.IsChecked = string.Equals(mode, "match", StringComparison.Ordinal);
        LabelModeAuto.IsChecked = string.Equals(mode, "auto", StringComparison.Ordinal);
        LabelModeSingle.IsChecked = string.Equals(mode, "single", StringComparison.Ordinal);
    }

    // ------------------------------------------------------------------
    // layout: drag / undo / auto arrange
    // ------------------------------------------------------------------

    private void AutoArrange_Click(object sender, RoutedEventArgs e)
    {
        if (_activeChart?.Scene is null)
        {
            return;
        }
        PushUndo(_activeChart, _activeChart.SnapshotLayout());
        _activeChart.Layout.Clear();
        BuildScene(_activeChart);
        RenderActiveChart();
        LayoutStateText.Text = "布局：自动";
        SetStatus("已恢复自动排列", error: false);
    }

    private void Undo_Click(object sender, RoutedEventArgs e) => UndoLayout();

    private void Redo_Click(object sender, RoutedEventArgs e) => RedoLayout();

    private void UndoLayout()
    {
        if (_activeChart is null || _activeChart.Undo.Count == 0)
        {
            return;
        }
        _activeChart.Redo.Push(_activeChart.SnapshotLayout());
        _activeChart.Layout = _activeChart.Undo.Pop();
        BuildScene(_activeChart);
        RenderActiveChart();
        SetStatus("已撤销标签调整", error: false);
    }

    private void RedoLayout()
    {
        if (_activeChart is null || _activeChart.Redo.Count == 0)
        {
            return;
        }
        _activeChart.Undo.Push(_activeChart.SnapshotLayout());
        _activeChart.Layout = _activeChart.Redo.Pop();
        BuildScene(_activeChart);
        RenderActiveChart();
        SetStatus("已重做标签调整", error: false);
    }

    private static void PushUndo(ChartState chart, Dictionary<string, LayoutOffset> snapshot)
    {
        chart.Undo.Push(snapshot);
        chart.Redo.Clear();
    }

    private void UpdateUndoButtons()
    {
        UndoButton.IsEnabled = _activeChart is not null && _activeChart.Undo.Count > 0;
        RedoButton.IsEnabled = _activeChart is not null && _activeChart.Redo.Count > 0;
    }

    private void OnLabelSelected(object? sender, LabelEventArgs e)
    {
        if (_activeChart is null)
        {
            return;
        }
        _pendingUndo = _activeChart.SnapshotLayout();
        _selectedLabel = e.Label;
        SetStatus($"已选中「{e.Label}」· 拖动调整位置", error: false);
    }

    private void OnLabelMoved(object? sender, LabelMovedEventArgs e)
    {
        LayoutStateText.Text = "布局：自定义";
    }

    private void OnLabelMoveCompleted(object? sender, LabelEventArgs e)
    {
        if (_activeChart?.Scene is null)
        {
            return;
        }
        var previous = _pendingUndo ?? _activeChart.SnapshotLayout();
        _activeChart.Layout = ChartSceneBuilder.CollectOffsets(_activeChart.Scene);
        PushUndo(_activeChart, previous);
        _pendingUndo = null;
        LayoutStateText.Text = _activeChart.Layout.Count > 0 ? "布局：自定义" : "布局：自动";
        UpdateUndoButtons();
        SetStatus($"已调整「{e.Label}」的位置 · Ctrl+Z 可撤销", error: false);
    }

    private void OnLabelResetRequested(object? sender, LabelEventArgs e)
    {
        if (_activeChart?.Scene is null)
        {
            return;
        }
        var previous = _activeChart.SnapshotLayout();
        _activeChart.Layout = ChartSceneBuilder.CollectOffsets(_activeChart.Scene);
        PushUndo(_activeChart, previous);
        LayoutStateText.Text = _activeChart.Layout.Count > 0 ? "布局：自定义" : "布局：自动";
        UpdateUndoButtons();
        SetStatus($"已恢复「{e.Label}」的自动位置", error: false);
    }

    private void OnWindowPreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.KeyboardDevice.Modifiers.HasFlag(ModifierKeys.Control))
        {
            if (e.Key == Key.Z)
            {
                UndoLayout();
                e.Handled = true;
            }
            else if (e.Key == Key.Y)
            {
                RedoLayout();
                e.Handled = true;
            }
            else if (e.Key == Key.E)
            {
                ExportTab.IsChecked = true;
                e.Handled = true;
            }
            else if (e.Key == Key.V && e.KeyboardDevice.Modifiers.HasFlag(ModifierKeys.Shift))
            {
                ShowPasteGrid();
                e.Handled = true;
            }
        }
        else if (e.Key == Key.F5)
        {
            RebuildAllCharts();
            RenderActiveChart();
            e.Handled = true;
        }
    }

    // ------------------------------------------------------------------
    // right tabs + export
    // ------------------------------------------------------------------

    private void RailData_Click(object sender, RoutedEventArgs e)
    {
        SetSidePanes(dataVisible: true, inspectorVisible: true);
        DataScrollViewer.ScrollToTop();
    }

    private void RailChart_Click(object sender, RoutedEventArgs e)
    {
        var focused = DataPaneColumn.Width.Value < 1 && InspectorPaneColumn.Width.Value < 1;
        SetSidePanes(dataVisible: focused, inspectorVisible: focused);
        RailChartButton.Background = focused
            ? Brushes.Transparent
            : (Brush)FindResource("RailActive");
    }

    private void RailPalette_Click(object sender, RoutedEventArgs e)
    {
        SetSidePanes(dataVisible: true, inspectorVisible: true);
        SelectRightTab("palette");
    }

    private void RailStyle_Click(object sender, RoutedEventArgs e)
    {
        SetSidePanes(dataVisible: true, inspectorVisible: true);
        SelectRightTab("style");
    }

    private void RailExport_Click(object sender, RoutedEventArgs e)
    {
        SetSidePanes(dataVisible: true, inspectorVisible: true);
        SelectRightTab("export");
    }

    private void SetSidePanes(bool dataVisible, bool inspectorVisible)
    {
        DataPaneColumn.Width = dataVisible ? new GridLength(336) : new GridLength(0);
        InspectorPaneColumn.Width = inspectorVisible ? new GridLength(388) : new GridLength(0);
        if (dataVisible && inspectorVisible)
        {
            RailChartButton.Background = Brushes.Transparent;
        }
    }
    private void SelectRightTab(string name)
    {
        switch (name.Trim().ToLowerInvariant())
        {
            case "style":
                StyleTab.IsChecked = true;
                break;
            case "export":
                ExportTab.IsChecked = true;
                break;
            default:
                PaletteTab.IsChecked = true;
                break;
        }
    }

    private void ExportNav_Click(object sender, RoutedEventArgs e) => ExportTab.IsChecked = true;

    private void RightTab_Checked(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        PalettePage.Visibility = PaletteTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        StylePage.Visibility = StyleTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        ExportPage.Visibility = ExportTab.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        if (PaletteTab.IsChecked == true)
        {
            RebuildPalettePage();
        }
        else if (StyleTab.IsChecked == true)
        {
            _suppress = true;
            if (_activeChart is not null)
            {
                TitleBox.Text = _activeChart.Title;
                SubtitleBox.Text = _activeChart.Subtitle;
            }
            _suppress = false;
        }
        else if (ExportTab.IsChecked == true)
        {
            UpdateDimensionState();
        }
    }

    private void InitializeExportControls()
    {
        _suppress = true;
        OutputDirBox.Text = _export.OutputDirectory;
        WidthBox.Text = _export.Width.ToString(CultureInfo.InvariantCulture);
        HeightBox.Text = _export.Height.ToString(CultureInfo.InvariantCulture);
        DpiBox.Text = _export.Dpi.ToString(CultureInfo.InvariantCulture);
        FilenameBox.Text = _export.Filename;
        TransparentCheck.IsChecked = _export.Transparent;
        var formatRadio = string.Equals(_export.Format, "svg", StringComparison.Ordinal)
            ? FormatSvg
            : string.Equals(_export.Format, "pdf", StringComparison.Ordinal) ? FormatPdf : FormatPng;
        formatRadio.IsChecked = true;
        var presetIndex = 0;
        for (var index = 0; index < SizePresetCombo.Items.Count; index++)
        {
            if (SizePresetCombo.Items[index] is ComboBoxItem item &&
                string.Equals(item.Tag as string, _export.Preset, StringComparison.Ordinal))
            {
                presetIndex = index;
                break;
            }
        }
        SizePresetCombo.SelectedIndex = presetIndex;
        _suppress = false;
        UpdateDimensionState();
        DpiBox.LostFocus += (_, _) => UpdateExportFromControls();
        WidthBox.LostFocus += (_, _) => UpdateExportFromControls();
        HeightBox.LostFocus += (_, _) => UpdateExportFromControls();
    }

    private void ExportFormat_Checked(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        _export.Format = FormatSvg.IsChecked == true ? "svg" : FormatPdf.IsChecked == true ? "pdf" : "png";
    }

    private void SizePreset_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        if (SizePresetCombo.SelectedItem is not ComboBoxItem item || item.Tag is not string tag)
        {
            return;
        }
        _export.Preset = tag;
        if (tag == "custom")
        {
            WidthBox.IsEnabled = true;
            HeightBox.IsEnabled = true;
            DimensionHint.Text = "按像素输入宽度与高度";
            return;
        }
        var parts = tag.Split('x');
        if (parts.Length == 2 &&
            int.TryParse(parts[0], out var width) &&
            int.TryParse(parts[1], out var height))
        {
            _export.Width = width;
            _export.Height = height;
            WidthBox.Text = width.ToString(CultureInfo.InvariantCulture);
            HeightBox.Text = height.ToString(CultureInfo.InvariantCulture);
        }
        UpdateDimensionState();
    }

    private void UpdateDimensionState()
    {
        var custom = string.Equals(_export.Preset, "custom", StringComparison.Ordinal);
        WidthBox.IsEnabled = custom;
        HeightBox.IsEnabled = custom;
        DimensionHint.Text = custom
            ? "按像素输入宽度与高度"
            : "尺寸由上方预设决定，选择“自定义”后可修改";
    }

    private void ExportOption_Changed(object sender, RoutedEventArgs e)
    {
        if (!_uiReady || _suppress)
        {
            return;
        }
        UpdateExportFromControls();
    }

    private void UpdateExportFromControls()
    {
        _export.Transparent = TransparentCheck.IsChecked == true;
        _export.Filename = FilenameBox.Text;
        if (int.TryParse(WidthBox.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var width))
        {
            _export.Width = Math.Clamp(width, 200, 8000);
        }
        if (int.TryParse(HeightBox.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var height))
        {
            _export.Height = Math.Clamp(height, 200, 8000);
        }
        if (int.TryParse(DpiBox.Text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var dpi))
        {
            _export.Dpi = Math.Clamp(dpi, 50, 600);
        }
    }

    private void ChooseOutputDir_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog
        {
            Title = "选择导出目录",
            InitialDirectory = Directory.Exists(_export.OutputDirectory)
                ? _export.OutputDirectory
                : AppContext.BaseDirectory,
        };
        if (dialog.ShowDialog(this) == true)
        {
            _export.OutputDirectory = dialog.FolderName;
            OutputDirBox.Text = _export.OutputDirectory;
            SetStatus("已选择输出目录", error: false);
        }
    }

    private void ExportCurrent_Click(object sender, RoutedEventArgs e) => ExportCurrentChart();

    private void ExportCurrentChart(bool reveal = true)
    {
        if (_activeChart?.Scene is null)
        {
            SetStatus("当前没有可导出的图表", error: true);
            return;
        }
        UpdateExportFromControls();
        try
        {
            var path = ExportScene(_activeChart, 1);
            SetStatus($"已导出：{Path.GetFileName(path)}", error: false);
            if (reveal)
            {
                OpenExportFolder();
            }
        }
        catch (Exception exception)
        {
            SetStatus("导出失败", error: true);
            MessageBox.Show(this, exception.Message, "导出失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void ExportAll_Click(object sender, RoutedEventArgs e)
    {
        UpdateExportFromControls();
        try
        {
            var paths = new List<string>();
            foreach (var chart in _charts.Where(chart => chart.Scene is not null).ToList())
            {
                paths.Add(ExportScene(chart, paths.Count + 1));
            }
            SetStatus(paths.Count > 0 ? $"已导出 {paths.Count} 张图" : "没有可导出的图表", error: paths.Count == 0);
            if (paths.Count > 0)
            {
                OpenExportFolder();
            }
        }
        catch (Exception exception)
        {
            SetStatus("导出失败", error: true);
            MessageBox.Show(this, exception.Message, "导出失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    /// <summary>Open the export folder in Windows Explorer.</summary>
    private void OpenExportFolder()
    {
        try
        {
            Directory.CreateDirectory(_export.OutputDirectory);
            Process.Start(new ProcessStartInfo
            {
                FileName = "explorer.exe",
                Arguments = $"\"{_export.OutputDirectory}\"",
                UseShellExecute = true,
            });
        }
        catch (Exception exception)
        {
            SetStatus($"无法打开输出目录：{exception.Message}", error: true);
        }
    }

    private string ExportScene(ChartState chart, int index)
    {
        Directory.CreateDirectory(_export.OutputDirectory);
        var format = string.Equals(_export.Format, "svg", StringComparison.Ordinal)
            ? "svg"
            : string.Equals(_export.Format, "pdf", StringComparison.Ordinal) ? "pdf" : "png";
        var title = string.IsNullOrWhiteSpace(chart.Title) ? chart.ColumnName : chart.Title;
        var filename = _export.Filename
            .Replace("{title}", title, StringComparison.Ordinal)
            .Replace("{column}", chart.ColumnName, StringComparison.Ordinal)
            .Replace("{date}", DateTime.Now.ToString("yyyyMMdd", CultureInfo.InvariantCulture), StringComparison.Ordinal)
            .Replace("{index}", index.ToString(CultureInfo.InvariantCulture), StringComparison.Ordinal);
        filename = SanitizeFilename(filename);
        var path = Path.Combine(_export.OutputDirectory, filename + "." + format);
        var options = new ChartExportService.ExportOptions
        {
            Width = _export.Width,
            Height = _export.Height,
            Dpi = _export.Dpi,
            Transparent = _export.Transparent && format == "png",
        };
        return format switch
        {
            "svg" => ChartExportService.ExportSvg(chart.Scene!, options, path),
            "pdf" => ChartExportService.ExportPdf(chart.Scene!, options, path),
            _ => ChartExportService.ExportPng(chart.Scene!, options, path),
        };
    }

    private static string SanitizeFilename(string text)
    {
        var cleaned = Regex.Replace(text, "[\\\\/:*?\"<>|]+", "_").Trim(' ', '.');
        return string.IsNullOrWhiteSpace(cleaned) ? "rose-chart" : cleaned;
    }

    private void CopyImage_Click(object sender, RoutedEventArgs e)
    {
        if (_activeChart?.Scene is null)
        {
            SetStatus("当前没有可复制的图表", error: true);
            return;
        }
        try
        {
            var bitmap = ChartExportService.CreatePngBitmap(_activeChart.Scene, new ChartExportService.ExportOptions
            {
                Width = _export.Width,
                Height = _export.Height,
                Dpi = _export.Dpi,
                Transparent = _export.Transparent,
            });
            Clipboard.SetImage(bitmap);
            SetStatus("已复制当前图为图片", error: false);
        }
        catch (Exception exception)
        {
            SetStatus("复制失败", error: true);
            MessageBox.Show(this, exception.Message, "复制图片失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OpenOutputDir_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Directory.CreateDirectory(_export.OutputDirectory);
            OpenExportFolder();
        }
        catch (Exception exception)
        {
            SetStatus($"无法打开输出目录：{exception.Message}", error: true);
        }
    }

    // ------------------------------------------------------------------
    // file drop / status / persistence / QA
    // ------------------------------------------------------------------

    private void OnWindowDrop(object sender, DragEventArgs e)
    {
        if (e.Data.GetData(DataFormats.FileDrop) is string[] files)
        {
            var file = files.FirstOrDefault(path =>
                path.EndsWith(".xlsx", StringComparison.OrdinalIgnoreCase) ||
                path.EndsWith(".xlsm", StringComparison.OrdinalIgnoreCase));
            if (file is not null)
            {
                LoadWorkbook(file);
            }
        }
    }

    private void SetStatus(string message, bool error)
    {
        StatusText.Text = message;
        StatusDot.Fill = error
            ? new SolidColorBrush(Color.FromRgb(0xBA, 0x1A, 0x1A))
            : (Brush)FindResource("Success");
    }

    private void UpdateStatusStats()
    {
        var parts = new List<string>();
        if (_charts.Count > 0)
        {
            parts.Add($"图表 {_charts.Count}");
        }
        if (_activeChart is not null && _activeChart.Counts.Count > 0)
        {
            parts.Add($"类别 {_activeChart.Counts.Count}");
        }
        if (_sheet is not null)
        {
            parts.Add($"{_sheet.RowCount} 行");
        }
        StatsText.Text = string.Join(" · ", parts);
    }

    private void OnWindowClosing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        try
        {
            if (_inlineTitleEditing)
            {
                FinishInlineTitleEdit(commit: true);
            }
            _settings.File = _filePath;
            _settings.Sheet = _sheet?.SheetName;
            _settings.ActiveChartColumn = _activeChart?.ColumnName;
            _settings.Charts = _charts.Select(ToDto).ToList();
            if (_pastedData)
            {
                // Clipboard data is session-only; do not restore stale charts on next launch.
                _settings.File = null;
                _settings.Sheet = null;
                _settings.ActiveChartColumn = null;
                _settings.Charts = new List<ChartStateDto>();
            }
            _settings.Style = _style.Clone();
            _settings.Export = new ExportSettings
            {
                Format = _export.Format,
                Preset = _export.Preset,
                Width = _export.Width,
                Height = _export.Height,
                Dpi = _export.Dpi,
                Transparent = _export.Transparent,
                Filename = _export.Filename,
                OutputDirectory = _export.OutputDirectory,
            };
            _settings.Window = new WindowSettings
            {
                Width = WindowState == WindowState.Maximized ? RestoreBounds.Width : Width,
                Height = WindowState == WindowState.Maximized ? RestoreBounds.Height : Height,
                Maximized = WindowState == WindowState.Maximized,
            };
            _settings.CategoryColumn = null;
            _settings.StatusColumn = null;
            _settings.Chart1 = null;
            _settings.Chart2 = null;
            _settings.ActiveChart = null;
            if (_filePath is not null)
            {
                _settings.RecentFiles.RemoveAll(path =>
                    string.Equals(path, _filePath, StringComparison.OrdinalIgnoreCase));
                _settings.RecentFiles.Insert(0, _filePath);
                if (_settings.RecentFiles.Count > 10)
                {
                    _settings.RecentFiles.RemoveRange(10, _settings.RecentFiles.Count - 10);
                }
            }
            _settingsService.Save(_settings);
        }
        catch
        {
            // persistence must never block closing
        }
    }

    private static ChartStateDto ToDto(ChartState chart) => new()
    {
        Column = chart.ColumnName,
        Name = chart.Name,
        Title = chart.Title,
        Subtitle = chart.Subtitle,
        PaletteId = chart.PaletteId,
        LabelMode = chart.LabelMode,
        LabelSingleColor = chart.LabelSingleColor,
        SortMode = chart.SortMode,
        Overrides = new Dictionary<string, string>(chart.Overrides, StringComparer.Ordinal),
        Layout = new Dictionary<string, LayoutOffset>(chart.Layout, StringComparer.Ordinal),
    };

    private void RunQaScenarios(IReadOnlyList<string> scenarios)
    {
        foreach (var scenario in scenarios)
        {
            switch (scenario)
            {
                case "drag":
                    if (_activeChart?.Scene is not null)
                    {
                        var label = _activeChart.Scene.Labels.FirstOrDefault();
                        if (label is not null)
                        {
                            _pendingUndo = _activeChart.SnapshotLayout();
                            ChartView.MoveLabelForPerf(label.Label, label.Y - 0.16, label.LineEndX - 0.10);
                            OnLabelMoveCompleted(this, new LabelEventArgs(label.Label));
                        }
                    }
                    break;
                case "palette":
                    ApplyPaletteById("tech_neon");
                    break;
                case "status":
                    if (_charts.Count > 1)
                    {
                        ActivateChart(_charts[1]);
                    }
                    break;
                case "owner":
                {
                    var ownerColumn = _columns.FirstOrDefault(column =>
                        string.Equals(column.Name, "负责人", StringComparison.Ordinal));
                    if (ownerColumn is not null)
                    {
                        ownerColumn.IsSelected = true;
                        AddChartForColumn(ownerColumn);
                    }
                    break;
                }
                case "min":
                    Width = MinWidth;
                    Height = MinHeight;
                    break;
                case "follow":
                    LabelModeFollow.IsChecked = true;
                    break;
                case "auto":
                    AutoArrange_Click(this, new RoutedEventArgs());
                    break;
                case "title":
                    OnTitleEditRequested(this, EventArgs.Empty);
                    break;
                case "undo":
                    UndoLayout();
                    break;
                case "redo":
                    RedoLayout();
                    break;
            }
        }
    }

    private void ApplyPaletteById(string paletteId)
    {
        if (_activeChart is null || string.Equals(_activeChart.PaletteId, paletteId, StringComparison.Ordinal))
        {
            return;
        }
        _activeChart.PaletteId = paletteId;
        var palette = GetPalette(paletteId);
        RecomputeColors(_activeChart);
        BuildScene(_activeChart);
        RenderActiveChart();
        RebuildPalettePage();
        SetStatus($"已应用配色方案：{palette.Name}", error: false);
    }
}
