using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using RoseChartStudio.Rendering;

namespace RoseChartStudio.App.Controls;

/// <summary>A small, dependency-free hex color picker used for palette overrides.</summary>
public sealed class ColorPickerDialog : Window
{
    private readonly TextBox _hexBox;
    private readonly Border _preview;

    public string SelectedHex { get; private set; }

    public ColorPickerDialog(string initialHex, string title)
    {
        Title = title;
        Width = 360;
        Height = 300;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        ResizeMode = ResizeMode.NoResize;
        ShowInTaskbar = false;
        Background = (Brush)(Application.Current?.FindResource("Panel") ?? Brushes.White);
        SelectedHex = Normalize(initialHex);
        var root = new StackPanel { Margin = new Thickness(20) };

        root.Children.Add(new TextBlock
        {
            Text = "十六进制颜色",
            FontSize = 12,
            Foreground = (Brush)(Application.Current?.FindResource("Muted") ?? Brushes.Gray),
            Margin = new Thickness(0, 0, 0, 6),
        });
        var row = new StackPanel { Orientation = Orientation.Horizontal };
        _preview = new Border
        {
            Width = 36,
            Height = 32,
            CornerRadius = new CornerRadius(6),
            BorderThickness = new Thickness(1),
            BorderBrush = (Brush)(Application.Current?.FindResource("Hairline") ?? Brushes.LightGray),
            Background = new SolidColorBrush(ColorUtil.ToColor(SelectedHex, Colors.Gray)),
            Margin = new Thickness(0, 0, 10, 0),
        };
        _hexBox = new TextBox { Text = SelectedHex, Width = 160, VerticalContentAlignment = VerticalAlignment.Center };
        _hexBox.TextChanged += (_, _) =>
        {
            var candidate = Normalize(_hexBox.Text);
            _preview.Background = new SolidColorBrush(ColorUtil.ToColor(candidate, Colors.Gray));
        };
        row.Children.Add(_preview);
        row.Children.Add(_hexBox);
        root.Children.Add(row);

        var presets = new[]
        {
            "#0F766E", "#182230", "#334155", "#5C6B7F",
            "#B42318", "#B45309", "#6AFFFF", "#E0A6E5",
            "#EBE082", "#16A34A", "#2563EB", "#7C3AED",
        };
        var wrap = new WrapPanel { Margin = new Thickness(0, 16, 0, 0) };
        foreach (var hex in presets)
        {
            var button = new Button
            {
                Width = 26,
                Height = 26,
                Margin = new Thickness(0, 0, 8, 8),
                Padding = new Thickness(0),
                Background = new SolidColorBrush(ColorUtil.ToColor(hex, Colors.Gray)),
                BorderThickness = new Thickness(0),
                Cursor = System.Windows.Input.Cursors.Hand,
                ToolTip = hex,
            };
            button.Click += (_, _) =>
            {
                _hexBox.Text = hex;
                SelectedHex = hex;
            };
            wrap.Children.Add(button);
        }
        root.Children.Add(wrap);

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 18, 0, 0),
        };
        var cancel = new Button { Content = "取消", Width = 72, Margin = new Thickness(0, 0, 8, 0) };
        cancel.Click += (_, _) => DialogResult = false;
        var ok = new Button { Content = "确定", Width = 72, IsDefault = true };
        ok.Click += (_, _) =>
        {
            SelectedHex = Normalize(_hexBox.Text);
            DialogResult = true;
        };
        actions.Children.Add(cancel);
        actions.Children.Add(ok);
        root.Children.Add(actions);
        Content = root;
    }

    private static string Normalize(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "#334155";
        }
        var text = value.Trim();
        if (!text.StartsWith('#'))
        {
            text = "#" + text;
        }
        var color = ColorUtil.ToColor(text, Colors.Transparent);
        return color == Colors.Transparent && !string.Equals(text, "#000000", StringComparison.OrdinalIgnoreCase)
            ? "#334155"
            : ColorUtil.ToHex(color);
    }
}
