namespace RoseChartStudio.Core.Models;

/// <summary>
/// Visual configuration shared by every chart of a document.
/// Values mirror the v2 engine defaults so migrated projects render identically.
/// </summary>
public sealed class ChartStyle
{
    public const string Transparent = "transparent";

    public string Title { get; set; } = "SW项目统计";
    public string Subtitle { get; set; } = "";

    public string FontFamily { get; set; } = "Microsoft YaHei";
    public double TitleFontSize { get; set; } = 34.0;
    public string TitleColor { get; set; } = "#333333";
    public double SubtitleFontSize { get; set; } = 14.0;
    public string SubtitleColor { get; set; } = "#64748B";

    public double InnerRadius { get; set; } = 0.30;
    public double OuterRadius { get; set; } = 0.98;
    public double StartAngle { get; set; } = 90.0;
    public double GapRatio { get; set; } = 0.18;
    public double GapMaxDegrees { get; set; } = 2.0;
    public double CornerRadius { get; set; } = 0.055;
    public string EdgeColor { get; set; } = "#FFFFFF";
    public double EdgeWidth { get; set; } = 3.2;

    public double LabelFontSize { get; set; } = 21.0;
    public double LabelLineWidth { get; set; } = 0.9;
    public double LabelWireScale { get; set; } = 1.0;
    public double LabelTextGap { get; set; } = 0.03;
    /// <summary>match | auto | single</summary>
    public string LabelColorMode { get; set; } = "auto";
    public string LabelSingleColor { get; set; } = "#334155";

    public bool ShowName { get; set; } = true;
    public bool ShowValue { get; set; } = true;
    public bool ShowPercent { get; set; } = true;
    public int PercentDecimals { get; set; } = 2;
    public string ValueSuffix { get; set; } = "";

    public string CenterText { get; set; } = "";
    public double CenterFontSize { get; set; } = 18.0;
    public string CenterColor { get; set; } = "#64748B";

    public string Background { get; set; } = Transparent;
    public double FigureWidth { get; set; } = 12.0;
    public double FigureHeight { get; set; } = 8.0;
    public int Dpi { get; set; } = 100;

    public ChartStyle Clone() => (ChartStyle)MemberwiseClone();

    public void CopyFrom(ChartStyle other)
    {
        Title = other.Title;
        Subtitle = other.Subtitle;
        FontFamily = other.FontFamily;
        TitleFontSize = other.TitleFontSize;
        TitleColor = other.TitleColor;
        SubtitleFontSize = other.SubtitleFontSize;
        SubtitleColor = other.SubtitleColor;
        InnerRadius = other.InnerRadius;
        OuterRadius = other.OuterRadius;
        StartAngle = other.StartAngle;
        GapRatio = other.GapRatio;
        GapMaxDegrees = other.GapMaxDegrees;
        CornerRadius = other.CornerRadius;
        EdgeColor = other.EdgeColor;
        EdgeWidth = other.EdgeWidth;
        LabelFontSize = other.LabelFontSize;
        LabelLineWidth = other.LabelLineWidth;
        LabelWireScale = other.LabelWireScale;
        LabelTextGap = other.LabelTextGap;
        LabelColorMode = other.LabelColorMode;
        LabelSingleColor = other.LabelSingleColor;
        ShowName = other.ShowName;
        ShowValue = other.ShowValue;
        ShowPercent = other.ShowPercent;
        PercentDecimals = other.PercentDecimals;
        ValueSuffix = other.ValueSuffix;
        CenterText = other.CenterText;
        CenterFontSize = other.CenterFontSize;
        CenterColor = other.CenterColor;
        Background = other.Background;
        FigureWidth = other.FigureWidth;
        FigureHeight = other.FigureHeight;
        Dpi = other.Dpi;
    }
}
