using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Services;

/// <summary>
/// Counts the distinct values of one sheet column.
/// This mirrors the legacy Python implementation (<c>rose/rosechart/data.py</c>,
/// <c>value_counts</c> with the default <c>count_desc</c> sort):
/// values are trimmed, empty/whitespace-only cells are skipped, the result is sorted by
/// count descending and then by value name ascending (Unicode code point order, which is
/// how Python sorts strings).
/// </summary>
public static class ColumnCounter
{
    /// <summary>
    /// Counts the non-empty values of <paramref name="columnHeader"/>.
    /// The header is matched through <see cref="SheetTable.IndexOf"/> (case-insensitive).
    /// </summary>
    /// <param name="table">Sheet content to inspect.</param>
    /// <param name="columnHeader">Header of the column to count.</param>
    /// <returns>
    /// One <see cref="CountItem"/> per distinct trimmed value; empty list when the column holds
    /// no countable value.
    /// </returns>
    /// <exception cref="ArgumentException">The sheet has no column named <paramref name="columnHeader"/>.</exception>
    public static IReadOnlyList<CountItem> Count(SheetTable table, string columnHeader)
    {
        ArgumentNullException.ThrowIfNull(table);
        ArgumentException.ThrowIfNullOrWhiteSpace(columnHeader);

        var columnIndex = table.IndexOf(columnHeader);
        if (columnIndex < 0)
        {
            var available = string.Join("、", table.Headers);
            throw new ArgumentException($"缺少列“{columnHeader}”。当前列为：{available}", nameof(columnHeader));
        }

        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        var total = 0;
        foreach (var row in table.Rows)
        {
            if (columnIndex >= row.Count)
            {
                continue;
            }

            var value = row[columnIndex].Trim();
            if (value.Length == 0)
            {
                continue;
            }

            counts.TryGetValue(value, out var current);
            counts[value] = current + 1;
            total++;
        }

        if (total == 0)
        {
            return Array.Empty<CountItem>();
        }

        return counts
            .OrderByDescending(pair => pair.Value)
            .ThenBy(pair => pair.Key, CodePointStringComparer.Instance)
            .Select(pair => new CountItem(pair.Key, pair.Value, (double)pair.Value / total))
            .ToArray();
    }

    /// <summary>
    /// Compares strings the way Python does (by Unicode code point). <see cref="Comparison{T}"/>
    /// with <see cref="StringComparison.Ordinal"/> compares UTF-16 code units instead and disagrees
    /// for characters outside the basic multilingual plane (surrogate pairs).
    /// </summary>
    private sealed class CodePointStringComparer : IComparer<string>
    {
        public static readonly CodePointStringComparer Instance = new();

        public int Compare(string? x, string? y)
        {
            if (ReferenceEquals(x, y))
            {
                return 0;
            }

            if (x is null)
            {
                return -1;
            }

            if (y is null)
            {
                return 1;
            }

            var left = x.EnumerateRunes();
            var right = y.EnumerateRunes();
            while (true)
            {
                var hasLeft = left.MoveNext();
                var hasRight = right.MoveNext();
                if (!hasLeft && !hasRight)
                {
                    return 0;
                }

                if (!hasLeft)
                {
                    return -1;
                }

                if (!hasRight)
                {
                    return 1;
                }

                var comparison = left.Current.Value.CompareTo(right.Current.Value);
                if (comparison != 0)
                {
                    return comparison;
                }
            }
        }
    }
}
