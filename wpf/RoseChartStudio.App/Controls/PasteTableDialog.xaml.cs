using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using RoseChartStudio.Core.Models;
using RoseChartStudio.Core.Parsing;

namespace RoseChartStudio.App.Controls;

/// <summary>Paste box with a live, read-only table preview before generating charts.</summary>
public partial class PasteTableDialog : Window
{
    private SheetTable? _table;
    private bool _ready;

    public PasteTableDialog()
    {
        InitializeComponent();
        Loaded += (_, _) =>
        {
            _ready = true;
            SourceBox.Focus();
            TryLoadClipboard();
            if (string.IsNullOrWhiteSpace(SourceBox.Text))
            {
                RefreshPreview();
            }
        };
    }

    public SheetTable? ResultTable => _table;

    private void TryLoadClipboard(bool force = false)
    {
        if (!force && !string.IsNullOrWhiteSpace(SourceBox.Text))
        {
            return;
        }
        try
        {
            if (!Clipboard.ContainsText())
            {
                if (force)
                {
                    ParseStatus.Text = "剪贴板里没有可读取的文本。";
                }
                return;
            }
            var text = Clipboard.GetText();
            if (string.IsNullOrWhiteSpace(text))
            {
                if (force)
                {
                    ParseStatus.Text = "剪贴板里没有可读取的表格内容。";
                }
                return;
            }

            var parsed = TabularDataParser.Parse(text, HeaderCheck.IsChecked == true);
            if (!force && !parsed.Success)
            {
                ParseStatus.Text = "剪贴板内容未识别为表格，请手动粘贴或检查格式。";
                return;
            }
            SourceBox.Text = text;
            if (_table is not null)
            {
                ParseStatus.Text = "已从剪贴板读取，可直接生成图表";
            }
        }
        catch (Exception exception)
        {
            ParseStatus.Text = $"无法读取剪贴板：{exception.Message}";
        }
    }

    private void ReadClipboard_Click(object sender, RoutedEventArgs e) => TryLoadClipboard(force: true);

    private void HeaderCheck_Changed(object sender, RoutedEventArgs e) => RefreshPreview();

    private void SourceBox_TextChanged(object sender, TextChangedEventArgs e) => RefreshPreview();

    private void RefreshPreview()
    {
        if (!_ready)
        {
            return;
        }
        if (string.IsNullOrWhiteSpace(SourceBox.Text))
        {
            _table = null;
            PreviewGrid.Columns.Clear();
            PreviewGrid.ItemsSource = null;
            GenerateButton.IsEnabled = false;
            ParseSummary.Text = "等待粘贴数据";
            ParseStatus.Text = "请粘贴表格内容。";
            ParseHint.Text = "从 Excel 或网页复制表格后，按 Ctrl+V 粘贴到这里。";
            ParseHint.Visibility = Visibility.Visible;
            return;
        }
        var result = TabularDataParser.Parse(
            SourceBox.Text,
            HeaderCheck.IsChecked == true);
        PreviewGrid.Columns.Clear();
        PreviewGrid.ItemsSource = null;

        if (!result.Success || result.Table is null)
        {
            _table = null;
            GenerateButton.IsEnabled = false;
            ParseSummary.Text = "未识别到有效表格";
            ParseStatus.Text = result.Error ?? "请粘贴表格内容。";
            ParseHint.Text = "从 Excel 或网页复制表格后，按 Ctrl+V 粘贴到这里。";
            ParseHint.Visibility = Visibility.Visible;
            return;
        }

        var table = result.Table;
        _table = table;
        GenerateButton.IsEnabled = true;
        ParseSummary.Text = $"{table.RowCount} 行 × {table.Headers.Count} 列 · 预览前 6 行";
        ParseStatus.Text = "识别成功，点击“生成图表”进入工作台。";
        for (var index = 0; index < table.Headers.Count; index++)
        {
            PreviewGrid.Columns.Add(new DataGridTextColumn
            {
                Header = table.Headers[index],
                Binding = new Binding($"Cells[{index}]"),
                Width = new DataGridLength(140),
                IsReadOnly = true,
                ElementStyle = PreviewTextStyle(),
            });
        }
        PreviewGrid.ItemsSource = table.Rows
            .Take(6)
            .Select(row => new PastePreviewRow { Cells = row })
            .ToList();
        ParseHint.Visibility = Visibility.Collapsed;
    }

    private static Style PreviewTextStyle()
    {
        var style = new Style(typeof(TextBlock));
        style.Setters.Add(new Setter(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center));
        style.Setters.Add(new Setter(FrameworkElement.MarginProperty, new Thickness(6, 0, 6, 0)));
        return style;
    }

    private void Generate_Click(object sender, RoutedEventArgs e)
    {
        if (_table is null)
        {
            return;
        }
        DialogResult = true;
    }
}

public sealed class PastePreviewRow
{
    public required IReadOnlyList<string> Cells { get; init; }
}
