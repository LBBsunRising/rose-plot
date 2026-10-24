using System;
using System.Collections.Generic;
using System.Linq;
using RoseChartStudio.Core.Models;
using RoseChartStudio.Core.Services;

namespace RoseChartStudio.Tests;

public class ColumnCounterTests
{
    [Fact]
    public void Count_SortsByCountDescendingThenValueAscending()
    {
        var table = MakeTable(
            new[] { "开发类别" },
            new[] { "软件开发" },
            new[] { "MES改造" },
            new[] { "软件开发" },
            new[] { "视觉改造" },
            new[] { "MES改造" },
            new[] { "软件开发" });

        var items = ColumnCounter.Count(table, "开发类别");

        Assert.Collection(
            items,
            item => AssertCount(item, "软件开发", 3, 6),
            item => AssertCount(item, "MES改造", 2, 6),
            item => AssertCount(item, "视觉改造", 1, 6));
    }

    [Fact]
    public void Count_TrimsValuesAndSkipsEmptyCells()
    {
        var table = MakeTable(
            new[] { "状态" },
            new[] { "  Done  " },
            new[] { "Done" },
            new[] { "" },
            new[] { "   " },
            new[] { "\t" },
            new string[0], // row shorter than the header (cell does not exist)
            new[] { "Pause" });

        var items = ColumnCounter.Count(table, "状态");

        Assert.Collection(
            items,
            item => AssertCount(item, "Done", 2, 3),
            item => AssertCount(item, "Pause", 1, 3));
    }

    [Fact]
    public void Count_GroupsNumericValuesAsInvariantStrings()
    {
        var table = MakeTable(
            new[] { "工期(天)" },
            new[] { "116" },
            new[] { "116 " },
            new[] { " 116" },
            new[] { "72" },
            new[] { "3.5" });

        var items = ColumnCounter.Count(table, "工期(天)");

        Assert.Collection(
            items,
            item => AssertCount(item, "116", 3, 5),
            item => AssertCount(item, "3.5", 1, 5),
            item => AssertCount(item, "72", 1, 5));
    }

    [Fact]
    public void Count_UsesUnicodeCodePointOrderForTies()
    {
        // Python sorts str by code point: "MES改造" (M < 视), 视觉改造 (U+89C6) < 软件开发 (U+8F6F).
        var table = MakeTable(
            new[] { "类别" },
            new[] { "软件开发" },
            new[] { "视觉改造" },
            new[] { "MES改造" });

        var items = ColumnCounter.Count(table, "类别");

        Assert.Equal(new[] { "MES改造", "视觉改造", "软件开发" }, items.Select(item => item.Value));
    }

    [Fact]
    public void Count_UsesCodePointOrderForSupplementaryPlaneCharacters()
    {
        // U+E000 sorts before U+1F600 by code point, while UTF-16 ordinal ordering would say otherwise.
        var table = MakeTable(
            new[] { "标签" },
            new[] { "\U0001F600" },
            new[] { "\uE000" });

        var items = ColumnCounter.Count(table, "标签");

        Assert.Equal(new[] { "\uE000", "\U0001F600" }, items.Select(item => item.Value));
    }

    [Fact]
    public void Count_SharesAreCountsOverTotal()
    {
        var table = MakeTable(
            new[] { "状态" },
            new[] { "On-going" },
            new[] { "Done" },
            new[] { "On-going" },
            new[] { "Delay" },
            new[] { "" });

        var items = ColumnCounter.Count(table, "状态");

        Assert.Equal(4, items.Sum(item => item.Count));
        Assert.All(items, item => Assert.Equal((double)item.Count / 4, item.Share, 9));
        Assert.Equal(1.0, items.Sum(item => item.Share), 9);
    }

    [Fact]
    public void Count_ReturnsEmptyListWhenColumnHasNoValues()
    {
        var table = MakeTable(
            new[] { "备注", "状态" },
            new[] { "", "" },
            new[] { "  ", "" });

        var items = ColumnCounter.Count(table, "状态");

        Assert.Empty(items);
    }

    [Fact]
    public void Count_ThrowsForUnknownColumn()
    {
        var table = MakeTable(new[] { "状态" }, new[] { "Done" });

        var exception = Assert.Throws<ArgumentException>(() => ColumnCounter.Count(table, "开发类别"));

        Assert.Contains("开发类别", exception.Message);
        Assert.Contains("状态", exception.Message);
    }

    [Fact]
    public void Count_MatchesHeaderCaseInsensitively()
    {
        // SheetTable.IndexOf compares headers case-insensitively; Count uses the same lookup.
        var table = MakeTable(new[] { "Status" }, new[] { "Done" }, new[] { "Done" });

        var items = ColumnCounter.Count(table, "status");

        var item = Assert.Single(items);
        AssertCount(item, "Done", 2, 2);
    }

    [Fact]
    public void Count_ExampleDatasetMatchesExpectedDistribution()
    {
        // Mirrors rose/examples/project_test_data.xlsx: 24 rows, 软件开发 12 / MES改造 7 / 视觉改造 5.
        var categories = new List<string>();
        categories.AddRange(Enumerable.Repeat("软件开发", 12));
        categories.AddRange(Enumerable.Repeat("MES改造", 7));
        categories.AddRange(Enumerable.Repeat("视觉改造", 5));
        var statuses = new List<string>();
        statuses.AddRange(Enumerable.Repeat("On-going", 9));
        statuses.AddRange(Enumerable.Repeat("Done", 8));
        statuses.AddRange(Enumerable.Repeat("Pause", 3));
        statuses.AddRange(Enumerable.Repeat("Delay", 4));

        var rows = categories
            .Select((category, index) => new[] { $"P2026-{index + 1:000}", category, statuses[index] })
            .ToArray();
        var table = MakeTable(new[] { "项目编号", "开发类别", "状态" }, rows);

        var categoryItems = ColumnCounter.Count(table, "开发类别");
        var statusItems = ColumnCounter.Count(table, "状态");

        Assert.Collection(
            categoryItems,
            item => AssertCount(item, "软件开发", 12, 24),
            item => AssertCount(item, "MES改造", 7, 24),
            item => AssertCount(item, "视觉改造", 5, 24));
        Assert.Collection(
            statusItems,
            item => AssertCount(item, "On-going", 9, 24),
            item => AssertCount(item, "Done", 8, 24),
            item => AssertCount(item, "Delay", 4, 24),
            item => AssertCount(item, "Pause", 3, 24));
    }

    private static void AssertCount(CountItem item, string value, int count, int total)
    {
        Assert.Equal(value, item.Value);
        Assert.Equal(count, item.Count);
        Assert.Equal((double)count / total, item.Share, 9);
    }

    private static SheetTable MakeTable(string[] headers, params string[][] rows) => new()
    {
        SheetName = "测试",
        Headers = headers,
        Rows = rows.Cast<IReadOnlyList<string>>().ToArray(),
    };
}

public class ColumnDetectorTests
{
    [Fact]
    public void Detect_FindsCategoryAndStatusColumns()
    {
        var table = MakeTable(
            "项目编号",
            "项目名称",
            "开发类别",
            "状态",
            "负责人",
            "开始日期",
            "计划完成日期",
            "进度",
            "预算(万元)",
            "计划工期(天)",
            "备注");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Equal("开发类别", category);
        Assert.Equal("状态", status);
    }

    [Fact]
    public void Detect_KeywordPriorityBeatsColumnOrder()
    {
        // Exact matches are searched in keyword order first: 开发类别 has priority over 类型.
        var table = MakeTable("类型", "开发类别", "项目状态", "状态");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Equal("开发类别", category);
        Assert.Equal("状态", status);
    }

    [Fact]
    public void Detect_FallsBackToSubstringMatching()
    {
        var table = MakeTable("项目类型说明", "当前状态");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Equal("项目类型说明", category);
        Assert.Equal("当前状态", status);
    }

    [Fact]
    public void Detect_FallsBackToFirstNonIdColumns()
    {
        var table = MakeTable("项目编号", "负责人", "备注");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Equal("负责人", category);
        Assert.Equal("备注", status);
    }

    [Fact]
    public void Detect_ReturnsNullsWhenOnlyIdColumnsExist()
    {
        var table = MakeTable("项目编号", "序号", "ID", "index", "No.");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Null(category);
        Assert.Null(status);
    }

    [Fact]
    public void Detect_DoesNotUseSameColumnForBothRoles()
    {
        // "分类状态" matches both keyword sets; the second role falls back to the next remaining column.
        var table = MakeTable("分类状态", "负责人", "备注");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Equal("分类状态", category);
        Assert.Equal("负责人", status);
    }

    [Fact]
    public void Detect_LeavesCategoryNullWhenOnlyStatusKeywordExists()
    {
        var table = MakeTable("项目编号", "状态");

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Null(category);
        Assert.Equal("状态", status);
    }

    [Fact]
    public void Detect_HandlesEmptyHeaders()
    {
        var table = MakeTable();

        var (category, status) = ColumnDetector.Detect(table);

        Assert.Null(category);
        Assert.Null(status);
    }

    [Fact]
    public void CategoryKeywordsAndStatusKeywordsMatchPythonOrder()
    {
        Assert.Equal("开发类别", ColumnDetector.CategoryKeywords[0]);
        Assert.Equal("类别", ColumnDetector.CategoryKeywords[2]);
        Assert.Equal("状态", ColumnDetector.StatusKeywords[0]);
        Assert.Equal("完成情况", ColumnDetector.StatusKeywords[^1]);
    }

    private static SheetTable MakeTable(params string[] headers) => new()
    {
        SheetName = "测试",
        Headers = headers,
        Rows = Array.Empty<IReadOnlyList<string>>(),
    };
}
