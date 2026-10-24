using RoseChartStudio.Core.Formatting;
using RoseChartStudio.Core.Geometry;
using RoseChartStudio.Core.Models;
using RoseChartStudio.Rendering;

namespace RoseChartStudio.Tests;

public sealed class SceneTests
{
    private static ChartSpec Spec(int labelCount = 3, ChartStyle? style = null)
    {
        var labels = new List<string>();
        var values = new List<int>();
        for (var index = 0; index < labelCount; index++)
        {
            labels.Add(index switch
            {
                0 => "软件开发",
                1 => "MES改造",
                2 => "视觉改造",
                3 => "数据平台",
                _ => $"类别{index + 1}",
            });
            values.Add(Math.Max(1, 14 - index));
        }
        var fills = labels.ToDictionary(label => label, _ => "#6AFFFF", StringComparer.Ordinal);
        var labelColors = labels.ToDictionary(label => label, _ => "#182230", StringComparer.Ordinal);
        return new ChartSpec
        {
            Labels = labels,
            Values = values,
            Style = style ?? new ChartStyle(),
            FillColors = fills,
            LabelColors = labelColors,
        };
    }

    [Fact]
    public void ThreeLabelsProduceSectorsAndLabels()
    {
        var scene = ChartSceneBuilder.Build(Spec());
        Assert.Equal(3, scene.Sectors.Count);
        Assert.Equal(3, scene.Labels.Count);
        Assert.Equal(39, scene.Total);
        Assert.All(scene.Sectors, sector => Assert.True(sector.Points.Count > 20));
        Assert.Contains(scene.Labels, label => label.Text.Contains("35.90%", StringComparison.Ordinal));
    }

    [Fact]
    public void AutoLayoutStaysInsideChartBounds()
    {
        var scene = ChartSceneBuilder.Build(Spec(12));
        foreach (var label in scene.Labels)
        {
            Assert.InRange(label.Y, -1.16, 1.14);
            Assert.InRange(label.LineEndX, -1.46, 1.46);
            Assert.True(label.TextX is >= -1.7 and <= 1.7);
        }
        Assert.Equal(12, scene.Labels.Select(label => label.Label).Distinct().Count());
    }

    [Fact]
    public void StoredOffsetsAreApplied()
    {
        var spec = Spec();
        spec.LayoutOffsets["视觉改造"] = new LayoutOffset(0.05, 0.2);
        var scene = ChartSceneBuilder.Build(spec);
        var label = scene.FindLabel("视觉改造");
        Assert.NotNull(label);
        Assert.Equal(0.2, label!.Y - label.AutoY, 6);
        Assert.Equal(0.05, label.LineEndX - label.AutoLineEndX, 6);
        Assert.Single(ChartSceneBuilder.CollectOffsets(scene));
    }

    [Fact]
    public void LabelMovementIsClamped()
    {
        var scene = ChartSceneBuilder.Build(Spec());
        var label = scene.FindLabel("软件开发")!;
        ChartSceneBuilder.MoveLabel(scene, "软件开发", 5.0, 5.0);
        Assert.Equal(1.14, label.Y, 6);
        Assert.Equal(1.46, label.LineEndX, 6);
        ChartSceneBuilder.MoveLabel(scene, "软件开发", -5.0, -5.0);
        Assert.Equal(-1.16, label.Y, 6);
        Assert.Equal(-1.46, label.LineEndX, 6);
    }

    [Fact]
    public void EmptyDataBuildsEmptyScene()
    {
        var scene = ChartSceneBuilder.Build(new ChartSpec { Style = new ChartStyle() });
        Assert.Empty(scene.Sectors);
        Assert.Empty(scene.Labels);
        Assert.Equal(0, scene.Total);
    }

    [Fact]
    public void TextFormattingHonoursSwitchesAndSuffix()
    {
        var style = new ChartStyle
        {
            ShowName = false,
            ShowValue = true,
            ShowPercent = true,
            ValueSuffix = " 项",
            PercentDecimals = 1,
        };
        var lines = ChartText.LabelLines(style, "软件开发", 12, 50.0);
        Assert.Equal(2, lines.Count);
        Assert.Equal("12 项", lines[0]);
        Assert.Equal("50.0%", lines[1]);
        var center = ChartText.CenterText(
            new ChartStyle { CenterText = "{total}/{n}/{max}" }, 24, 3, 12);
        Assert.Equal("24/3/12", center);
    }

    [Fact]
    public void SceneMapperPlacesChartCenterAndRoundTrips()
    {
        var mapper = new SceneMapper(new ChartStyle());
        var center = mapper.ToVirtual(ChartScene.ChartCenter);
        Assert.Equal(600.0, center.X, 1);
        Assert.Equal(448.2, center.Y, 1);
        var data = mapper.ToData(center);
        Assert.Equal(0.0, data.X, 6);
        Assert.Equal(-0.05, data.Y, 6);
        Assert.Equal(273.33, mapper.Scale, 1);
    }

    [Fact]
    public void SectorPolygonHitTestingMatchesHoleAndRing()
    {
        var scene = ChartSceneBuilder.Build(Spec());
        var sector = scene.Sectors[0];
        Assert.True(RoseGeometry.PointInPolygon(sector.Points, new PointD(0.0, 0.0)) == false);
        var midAngle = sector.MidAngle * Math.PI / 180.0;
        var ringPoint = new PointD(
            Math.Cos(midAngle) * (scene.Style.InnerRadius + sector.OuterRadius) / 2.0,
            -0.05 + Math.Sin(midAngle) * (scene.Style.InnerRadius + sector.OuterRadius) / 2.0);
        Assert.True(RoseGeometry.PointInPolygon(sector.Points, ringPoint));
    }
}
