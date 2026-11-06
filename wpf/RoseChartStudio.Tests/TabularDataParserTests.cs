using RoseChartStudio.Core.Parsing;

namespace RoseChartStudio.Tests;

public class TabularDataParserTests
{
    [Fact]
    public void Parse_TabSeparatedClipboardWithHeader()
    {
        var result = TabularDataParser.Parse("项目\t状态\nA\t完成\nB\t进行中\nA\t完成\n");

        Assert.True(result.Success, result.Error);
        var table = result.Table!;
        Assert.Equal("粘贴数据", table.SheetName);
        Assert.Equal(new[] { "项目", "状态" }, table.Headers);
        Assert.Equal(3, table.RowCount);
        Assert.Equal("A", table.Rows[0][0]);
        Assert.Equal("进行中", table.Rows[1][1]);
    }

    [Fact]
    public void Parse_QuotedCsvSupportsCommasAndNewlines()
    {
        var result = TabularDataParser.Parse("name,note\nA,\"one, two\"\nB,\"line1\nline2\"\n");

        Assert.True(result.Success, result.Error);
        var table = result.Table!;
        Assert.Equal(new[] { "name", "note" }, table.Headers);
        Assert.Equal("one, two", table.Rows[0][1]);
        Assert.Equal("line1\nline2", table.Rows[1][1]);
    }

    [Fact]
    public void Parse_CanTreatFirstRowAsData()
    {
        var result = TabularDataParser.Parse("A\t1\nB\t2\n", firstRowIsHeader: false);

        Assert.True(result.Success, result.Error);
        Assert.Equal(2, result.Table!.RowCount);
        Assert.Equal(new[] { "列1", "列2" }, result.Table.Headers);
        Assert.Equal("A", result.Table.Rows[0][0]);
    }

    [Fact]
    public void Parse_GeneratesUniqueNamesForDuplicateAndBlankHeaders()
    {
        var result = TabularDataParser.Parse("状态\t状态\t\nA\tB\tC\n");

        Assert.True(result.Success, result.Error);
        Assert.Equal(new[] { "状态", "状态 (2)", "列3" }, result.Table!.Headers);
    }

    [Fact]
    public void Parse_SupportsSingleColumnText()
    {
        var result = TabularDataParser.Parse("类别\nA\nB\nA\n");

        Assert.True(result.Success, result.Error);
        Assert.Single(result.Table!.Headers);
        Assert.Equal(3, result.Table.RowCount);
        Assert.Equal("类别", result.Table.Headers[0]);
    }

    [Fact]
    public void Parse_RejectsHeaderWithoutData()
    {
        var result = TabularDataParser.Parse("类别\n");

        Assert.False(result.Success);
        Assert.Contains("没有数据行", result.Error);
    }

    [Fact]
    public void Parse_RejectsUnclosedQuote()
    {
        var result = TabularDataParser.Parse("name,note\nA,\"unfinished\n");

        Assert.False(result.Success);
        Assert.Contains("引号", result.Error);
    }
}
