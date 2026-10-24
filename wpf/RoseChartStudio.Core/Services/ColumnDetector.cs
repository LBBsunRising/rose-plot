using System;
using System.Collections.Generic;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Services;

/// <summary>
/// Detects the category ("开发类别", "项目类别", ...) and status ("状态", "进展", ...) columns
/// of a sheet. The keyword lists, their priority order and the fallback strategy are ported
/// verbatim from <c>rose/rosechart/data.py</c> (<c>detect_columns</c>).
/// </summary>
public static class ColumnDetector
{
    /// <summary>Category-column keywords, highest priority first (matches data.py order).</summary>
    public static IReadOnlyList<string> CategoryKeywords { get; } = Array.AsReadOnly(new[]
    {
        "开发类别",
        "项目类别",
        "类别",
        "项目类型",
        "类型",
        "分类",
        "系统",
        "模块",
        "产品",
    });

    /// <summary>Status-column keywords, highest priority first (matches data.py order).</summary>
    public static IReadOnlyList<string> StatusKeywords { get; } = Array.AsReadOnly(new[]
    {
        "状态",
        "项目状态",
        "进展",
        "进度状态",
        "阶段",
        "完成情况",
    });

    private static readonly string[] IdMarkers = { "编号", "序号", "id", "index", "no." };

    /// <summary>
    /// Detects the category and status columns of <paramref name="table"/>.
    /// </summary>
    /// <returns>
    /// The matching header names, or <see langword="null"/> when no suitable column exists.
    /// The names are the exact header strings of the table (they are not trimmed).
    /// </returns>
    public static (string? CategoryColumn, string? StatusColumn) Detect(SheetTable table)
    {
        ArgumentNullException.ThrowIfNull(table);

        var names = table.Headers;
        var category = DetectColumn(names, CategoryKeywords);
        var status = DetectColumn(names, StatusKeywords);

        // A column cannot serve both roles (data.py: "if second == first: second = None").
        if (status is not null && string.Equals(status, category, StringComparison.Ordinal))
        {
            status = null;
        }

        if (category is null || status is null)
        {
            // Fill the missing role(s) from the first remaining non-id-looking columns,
            // preserving the original column order (data.py fallback).
            var remaining = new List<string>(names.Count);
            foreach (var name in names)
            {
                if (NameEquals(name, category) || NameEquals(name, status))
                {
                    continue;
                }

                if (LooksLikeId(name))
                {
                    continue;
                }

                remaining.Add(name);
            }

            var cursor = 0;
            if (category is null && cursor < remaining.Count)
            {
                category = remaining[cursor++];
            }

            if (status is null && cursor < remaining.Count)
            {
                status = remaining[cursor];
            }
        }

        return (category, status);
    }

    private static string? DetectColumn(IReadOnlyList<string> names, IReadOnlyList<string> keywords)
    {
        // Pass 1: exact match on the trimmed header, keyword priority first (data.py).
        foreach (var keyword in keywords)
        {
            foreach (var name in names)
            {
                if (string.Equals(name.Trim(), keyword, StringComparison.Ordinal))
                {
                    return name;
                }
            }
        }

        // Pass 2: substring match, keyword priority first.
        foreach (var keyword in keywords)
        {
            foreach (var name in names)
            {
                if (name.Contains(keyword, StringComparison.Ordinal))
                {
                    return name;
                }
            }
        }

        return null;
    }

    private static bool NameEquals(string name, string? other) =>
        other is not null && string.Equals(name, other, StringComparison.Ordinal);

    private static bool LooksLikeId(string name)
    {
        var lowered = name.ToLowerInvariant();
        foreach (var marker in IdMarkers)
        {
            if (lowered.Contains(marker, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }
}
