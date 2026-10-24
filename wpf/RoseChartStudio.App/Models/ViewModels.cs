using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Media;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.App.Models;

/// <summary>One grouping of the active worksheet: an arbitrary column rendered as a rose chart.</summary>
public sealed class ChartState : INotifyPropertyChanged
{
    private string _name;
    private string _title;
    private bool _isActive;

    public ChartState(string columnName, string? paletteId = null)
    {
        ColumnName = columnName;
        _name = columnName;
        _title = $"{columnName}统计";
        PaletteId = paletteId ?? "";
    }

    public string ColumnName { get; }
    public string TabLabel => string.IsNullOrWhiteSpace(_name) ? ColumnName : _name;

    /// <summary>Editable label of the chart tab; defaults to the source column name.</summary>
    public string Name
    {
        get => _name;
        set
        {
            if (_name == value)
            {
                return;
            }
            _name = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(TabLabel));
        }
    }

    public string Title
    {
        get => _title;
        set
        {
            if (_title == value)
            {
                return;
            }
            _title = value;
            OnPropertyChanged();
        }
    }

    public bool IsActive
    {
        get => _isActive;
        set
        {
            if (_isActive == value)
            {
                return;
            }
            _isActive = value;
            OnPropertyChanged();
        }
    }

    public string Subtitle { get; set; } = "";
    public string PaletteId { get; set; }
    public string LabelMode { get; set; } = "auto";
    public string LabelSingleColor { get; set; } = "#334155";
    public string SortMode { get; set; } = "count_desc";
    public Dictionary<string, string> Overrides { get; } = new(StringComparer.Ordinal);
    public Dictionary<string, LayoutOffset> Layout { get; set; } = new(StringComparer.Ordinal);
    public List<CountItem> Counts { get; set; } = new();
    public List<string> Labels { get; set; } = new();
    public List<int> Values { get; set; } = new();
    public Dictionary<string, string> FillColors { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string, string> LabelColors { get; set; } = new(StringComparer.Ordinal);
    public ChartScene? Scene { get; set; }
    public Stack<Dictionary<string, LayoutOffset>> Undo { get; } = new();
    public Stack<Dictionary<string, LayoutOffset>> Redo { get; } = new();

    public Dictionary<string, LayoutOffset> SnapshotLayout() =>
        new(Layout, StringComparer.Ordinal);

    public event PropertyChangedEventHandler? PropertyChanged;

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
}

/// <summary>One checkbox in the "分析列" list; checking it adds a chart tab.</summary>
public sealed class ColumnOption : INotifyPropertyChanged
{
    private bool _isSelected;

    public required string Name { get; init; }
    public string Meta { get; init; } = "";

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected == value)
            {
                return;
            }
            _isSelected = value;
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsSelected)));
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
}

/// <summary>One real worksheet row shown in the miniature table preview.</summary>
public sealed class SheetPreviewRow
{
    public required IReadOnlyList<string> Cells { get; init; }
}

public sealed class CountRow
{
    public required string Value { get; init; }
    public int Count { get; init; }
    public string ShareText { get; init; } = "";
}

public sealed class PaletteCardItem
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required IReadOnlyList<Brush> Swatches { get; init; }
    public string Meta { get; init; } = "";
    public string Tag { get; init; } = "";
    public bool IsSelected { get; init; }
    public Visibility TagVisibility => Tag.Length > 0 ? Visibility.Visible : Visibility.Collapsed;
    public Visibility SelectedMarkVisibility => Tag.Length > 0
        ? Visibility.Collapsed
        : IsSelected ? Visibility.Visible : Visibility.Collapsed;
}

public sealed class CategoryColorRow
{
    public required string Label { get; init; }
    public required string ColorHex { get; init; }
    public required Brush Brush { get; init; }
    public string Meta { get; init; } = "";
}

public sealed class ExportSettings
{
    public string Format { get; set; } = "png";
    public string Preset { get; set; } = "1200x800";
    public int Width { get; set; } = 1200;
    public int Height { get; set; } = 800;
    public int Dpi { get; set; } = 100;
    public bool Transparent { get; set; } = true;
    public string Filename { get; set; } = "{title}";
    public string OutputDirectory { get; set; } = "";
}
