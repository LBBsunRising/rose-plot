using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Rendering;

public sealed class LabelMovedEventArgs(string label) : EventArgs
{
    public string Label { get; } = label;
}

public sealed class LabelEventArgs(string label) : EventArgs
{
    public string Label { get; } = label;
}

/// <summary>
/// Retained-mode WPF chart surface. Everything is drawn in virtual figure
/// coordinates (1200×800 for the default 12×8 figure); a surrounding Viewbox
/// scales the whole surface, so resizing the window never re-rasterises the
/// chart. Moving a label only re-renders that single label's DrawingVisual.
/// </summary>
public sealed class RoseChartView : FrameworkElement
{
    private readonly VisualCollection _children;
    private readonly ContainerVisual _root = new();
    private readonly DrawingVisual _baseVisual = new();
    private readonly Dictionary<string, DrawingVisual> _labelVisuals = new(StringComparer.Ordinal);

    private ChartScene? _scene;
    private SceneMapper? _mapper;
    private string? _hoverLabel;
    private string? _highlightLabel;
    private string? _dragLabel;
    private Point _dragStartPoint;
    private PointD _dragStartData;
    private double _dragStartY;
    private double _dragStartLineEndX;
    private bool _dragging;

    public RoseChartView()
    {
        _children = new VisualCollection(this);
        _children.Add(_root);
        _root.Children.Add(_baseVisual);
        ClipToBounds = true;
        Focusable = true;
    }

    public ChartScene? Scene => _scene;
    public SceneMapper? Mapper => _mapper;
    public bool IsDragging => _dragging;
    public string? HoverLabel => _hoverLabel;

    public event EventHandler<LabelMovedEventArgs>? LabelMoved;
    public event EventHandler<LabelEventArgs>? LabelMoveCompleted;
    public event EventHandler<LabelEventArgs>? LabelResetRequested;
    public event EventHandler<LabelEventArgs>? LabelSelected;
    public event EventHandler? TitleEditRequested;

    protected override int VisualChildrenCount => _children.Count;
    protected override Visual GetVisualChild(int index) => _children[index];

    protected override Size MeasureOverride(Size constraint)
    {
        var scene = _scene;
        return scene is null ? new Size(1200, 800) : new Size(scene.VirtualWidth, scene.VirtualHeight);
    }

    protected override Size ArrangeOverride(Size finalSize) => finalSize;

    public void SetScene(ChartScene scene)
    {
        _scene = scene;
        _mapper = new SceneMapper(scene.Style);
        RebuildVisuals();
        InvalidateMeasure();
    }

    public void ClearScene()
    {
        _scene = null;
        _mapper = null;
        _root.Children.Clear();
        _labelVisuals.Clear();
        _hoverLabel = null;
        _highlightLabel = null;
        InvalidateMeasure();
    }

    public void HighlightLabel(string? label)
    {
        var changed = !string.Equals(_highlightLabel, label, StringComparison.Ordinal);
        _highlightLabel = label;
        if (changed)
        {
            RedrawAllLabels();
        }
    }

    private void RebuildVisuals()
    {
        _root.Children.Clear();
        _labelVisuals.Clear();
        if (_scene is null || _mapper is null)
        {
            return;
        }
        _root.Children.Add(_baseVisual);
        using (var dc = _baseVisual.RenderOpen())
        {
            ChartDrawing.DrawBase(dc, _scene, _mapper);
        }
        foreach (var label in _scene.Labels)
        {
            var visual = new DrawingVisual();
            _labelVisuals[label.Label] = visual;
            _root.Children.Add(visual);
            RedrawLabel(label.Label);
        }
    }

    private void RedrawAllLabels()
    {
        foreach (var label in _scene?.Labels ?? Array.Empty<LabelShape>())
        {
            RedrawLabel(label.Label);
        }
    }

    private void RedrawLabel(string labelName)
    {
        if (_scene is null || _mapper is null ||
            !_labelVisuals.TryGetValue(labelName, out var visual))
        {
            return;
        }
        var label = _scene.FindLabel(labelName);
        if (label is null)
        {
            return;
        }
        using var dc = visual.RenderOpen();
        ChartDrawing.DrawLabel(
            dc, _scene, label, _mapper,
            hover: string.Equals(_hoverLabel, labelName, StringComparison.Ordinal),
            highlight: string.Equals(_highlightLabel, labelName, StringComparison.Ordinal));
    }

    /// <summary>QA hook: move one label and redraw only that label's visual.</summary>
    public void MoveLabelForPerf(string labelName, double y, double lineEndX)
    {
        if (_scene is null)
        {
            return;
        }
        ChartSceneBuilder.MoveLabel(_scene, labelName, y, lineEndX);
        RedrawLabel(labelName);
    }

    public LabelShape? HitTestLabel(Point position, double padding = 8.0)    {
        if (_scene is null || _mapper is null)
        {
            return null;
        }
        LabelShape? best = null;
        var bestDistance = double.MaxValue;
        foreach (var label in _scene.Labels)
        {
            var bounds = ChartDrawing.MeasureLabel(
                _scene, label, _mapper,
                hover: string.Equals(_hoverLabel, label.Label, StringComparison.Ordinal));
            var rect = new Rect(
                bounds.AngleRect.X - padding,
                bounds.AngleRect.Y - padding,
                bounds.AngleRect.Width + padding * 2,
                bounds.AngleRect.Height + padding * 2);
            if (!rect.Contains(position))
            {
                continue;
            }
            var center = new Point(rect.X + rect.Width / 2, rect.Y + rect.Height / 2);
            var distance = (center - position).Length;
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = label;
            }
        }
        return best;
    }

    /// <summary>True when a virtual-canvas point falls on the rendered chart title.</summary>
    public bool IsTitlePoint(Point point)
    {
        if (_scene is null || _mapper is null || string.IsNullOrWhiteSpace(_scene.Style.Title))
        {
            return false;
        }
        var style = _scene.Style;
        var text = ChartDrawing.Text(
            style, style.Title, style.TitleFontSize,
            ColorUtil.ToColor(style.TitleColor, ChartDrawing.TitleFallback), bold: true);
        var centerX = _scene.VirtualWidth / 2.0;
        var centerY = _scene.VirtualHeight * 0.06;
        var rect = new Rect(
            centerX - text.Width / 2.0 - 14,
            centerY - text.Height / 2.0 - 10,
            text.Width + 28,
            text.Height + 20);
        return rect.Contains(point);
    }

    protected override void OnMouseLeftButtonDown(MouseButtonEventArgs e)
    {
        base.OnMouseLeftButtonDown(e);
        Focus();
        var point = e.GetPosition(this);
        if (IsTitlePoint(point))
        {
            TitleEditRequested?.Invoke(this, EventArgs.Empty);
            e.Handled = true;
            return;
        }
        var hit = HitTestLabel(point);
        if (hit is null)
        {
            return;
        }
        if (e.ClickCount >= 2)
        {
            ChartSceneBuilder.ResetLabel(_scene!, hit.Label);
            RedrawLabel(hit.Label);
            LabelResetRequested?.Invoke(this, new LabelEventArgs(hit.Label));
            e.Handled = true;
            return;
        }
        _dragging = true;
        _dragLabel = hit.Label;
        _dragStartPoint = point;
        _dragStartData = _mapper!.ToData(point);
        _dragStartY = hit.Y;
        _dragStartLineEndX = hit.LineEndX;
        CaptureMouse();
        Cursor = Cursors.SizeAll;
        LabelSelected?.Invoke(this, new LabelEventArgs(hit.Label));
        e.Handled = true;
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (_scene is null || _mapper is null)
        {
            return;
        }
        var point = e.GetPosition(this);
        if (_dragging && _dragLabel is not null)
        {
            var data = _mapper.ToData(point);
            var newY = _dragStartY + (data.Y - _dragStartData.Y);
            var newLineEndX = _dragStartLineEndX + (data.X - _dragStartData.X);
            ChartSceneBuilder.MoveLabel(_scene, _dragLabel, newY, newLineEndX);
            RedrawLabel(_dragLabel);
            LabelMoved?.Invoke(this, new LabelMovedEventArgs(_dragLabel));
            e.Handled = true;
            return;
        }

        var hover = HitTestLabel(point);
        var nextHover = hover?.Label;
        if (!string.Equals(nextHover, _hoverLabel, StringComparison.Ordinal))
        {
            var previous = _hoverLabel;
            _hoverLabel = nextHover;
            if (previous is not null)
            {
                RedrawLabel(previous);
            }
            if (nextHover is not null)
            {
                RedrawLabel(nextHover);
                Cursor = Cursors.Hand;
            }
            else
            {
                Cursor = Cursors.Arrow;
            }
        }
    }

    protected override void OnMouseLeftButtonUp(MouseButtonEventArgs e)
    {
        base.OnMouseLeftButtonUp(e);
        if (!_dragging)
        {
            return;
        }
        FinishDrag();
        e.Handled = true;
    }

    protected override void OnLostMouseCapture(MouseEventArgs e)
    {
        base.OnLostMouseCapture(e);
        if (_dragging)
        {
            FinishDrag();
        }
    }

    private void FinishDrag()
    {
        var label = _dragLabel;
        _dragging = false;
        _dragLabel = null;
        if (IsMouseCaptured)
        {
            ReleaseMouseCapture();
        }
        Cursor = Cursors.Arrow;
        if (label is not null && _scene is not null)
        {
            RedrawLabel(label);
            LabelMoveCompleted?.Invoke(this, new LabelEventArgs(label));
        }
    }

    protected override void OnMouseLeave(MouseEventArgs e)
    {
        base.OnMouseLeave(e);
        if (_hoverLabel is not null)
        {
            var previous = _hoverLabel;
            _hoverLabel = null;
            RedrawLabel(previous);
            Cursor = Cursors.Arrow;
        }
    }

    protected override void OnMouseRightButtonDown(MouseButtonEventArgs e)
    {
        base.OnMouseRightButtonDown(e);
        var hit = HitTestLabel(e.GetPosition(this));
        if (hit is not null)
        {
            ChartSceneBuilder.ResetLabel(_scene!, hit.Label);
            RedrawLabel(hit.Label);
            LabelResetRequested?.Invoke(this, new LabelEventArgs(hit.Label));
            e.Handled = true;
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        base.OnKeyDown(e);
        if (_scene is null)
        {
            return;
        }
        var selected = _highlightLabel;
        if (selected is null)
        {
            return;
        }
        var label = _scene.FindLabel(selected);
        if (label is null)
        {
            return;
        }
        var step = e.KeyboardDevice.Modifiers.HasFlag(ModifierKeys.Shift) ? 0.04 : 0.01;
        var dx = 0.0;
        var dy = 0.0;
        switch (e.Key)
        {
            case Key.Left: dx = -step; break;
            case Key.Right: dx = step; break;
            case Key.Up: dy = step; break;
            case Key.Down: dy = -step; break;
            default: return;
        }
        ChartSceneBuilder.MoveLabel(_scene, selected, label.Y + dy, label.LineEndX + dx);
        RedrawLabel(selected);
        LabelMoved?.Invoke(this, new LabelMovedEventArgs(selected));
        LabelMoveCompleted?.Invoke(this, new LabelEventArgs(selected));
        e.Handled = true;
    }
}
