using System.Text;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.Core.Parsing;

/// <summary>Result of parsing tab-separated or CSV text pasted from a spreadsheet.</summary>
public sealed record TabularParseResult(SheetTable? Table, string? Error)
{
    public bool Success => Table is not null;
}

/// <summary>
/// Parses clipboard table text (Excel/Google Sheets TSV, CSV, semicolon or pipe
/// separated text) into the same <see cref="SheetTable"/> used by the Excel reader.
/// The first line is a header by default; quoted fields and embedded newlines are
/// supported so copied cells containing commas or line breaks remain intact.
/// </summary>
public static class TabularDataParser
{
    public static TabularParseResult Parse(string? text, bool firstRowIsHeader = true)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return new TabularParseResult(null, "没有可解析的表格文本，请先复制表格。");
        }

        var normalized = text
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Trim('\uFEFF', '\n');
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return new TabularParseResult(null, "没有可解析的表格文本，请先复制表格。");
        }

        var delimiter = DetectDelimiter(normalized);
        var (records, unclosedQuote) = ParseRecords(normalized, delimiter);
        if (unclosedQuote)
        {
            return new TabularParseResult(null, "表格中的引号没有闭合，请检查复制的内容。");
        }

        records = records
            .Where(record => record.Any(cell => !string.IsNullOrWhiteSpace(cell)))
            .ToList();
        if (records.Count == 0)
        {
            return new TabularParseResult(null, "没有检测到数据行。");
        }

        IReadOnlyList<string> header = firstRowIsHeader ? records[0] : Array.Empty<string>();
        var dataRecords = firstRowIsHeader ? records.Skip(1).ToList() : records.ToList();
        if (dataRecords.Count == 0)
        {
            return new TabularParseResult(null, "只有表头，没有数据行。");
        }

        var columnCount = Math.Max(header.Count, dataRecords.Max(row => row.Count));
        if (columnCount == 0)
        {
            return new TabularParseResult(null, "表格没有有效的列。");
        }

        // Drop trailing empty columns commonly produced by copy operations.
        while (columnCount > 1 &&
               string.IsNullOrWhiteSpace(Get(header, columnCount - 1)) &&
               dataRecords.All(row => string.IsNullOrWhiteSpace(Get(row, columnCount - 1))))
        {
            columnCount--;
        }

        var headers = MakeHeaders(header, columnCount, firstRowIsHeader);
        var rows = new List<IReadOnlyList<string>>(dataRecords.Count);
        foreach (var source in dataRecords)
        {
            var row = new string[columnCount];
            for (var index = 0; index < columnCount; index++)
            {
                row[index] = index < source.Count ? source[index].Trim() : "";
            }
            rows.Add(row);
        }

        return new TabularParseResult(
            new SheetTable
            {
                SheetName = "粘贴数据",
                Headers = headers,
                Rows = rows,
            },
            null);
    }

    private static string[] MakeHeaders(
        IReadOnlyList<string> source, int columnCount, bool firstRowIsHeader)
    {
        var headers = new string[columnCount];
        var used = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < columnCount; index++)
        {
            var raw = index < source.Count ? source[index].Trim() : "";
            var name = firstRowIsHeader && raw.Length > 0 ? raw : $"列{index + 1}";
            if (used.Contains(name))
            {
                var suffix = 2;
                var candidate = $"{name} ({suffix})";
                while (used.Contains(candidate))
                {
                    suffix++;
                    candidate = $"{name} ({suffix})";
                }
                name = candidate;
            }
            used.Add(name);
            headers[index] = name;
        }
        return headers;
    }

    private static string Get(IReadOnlyList<string> row, int index) =>
        index < row.Count ? row[index] : "";

    /// <summary>Pick the separator with the most occurrences outside quoted fields.</summary>
    private static char DetectDelimiter(string text)
    {
        var candidates = new[] { '\t', ',', ';', '|' };
        var scores = candidates.ToDictionary(candidate => candidate, _ => 0);
        var inQuotes = false;
        var linesSeen = 0;
        for (var index = 0; index < text.Length && linesSeen < 5; index++)
        {
            var c = text[index];
            if (c == '"')
            {
                if (inQuotes && index + 1 < text.Length && text[index + 1] == '"')
                {
                    index++;
                    continue;
                }
                inQuotes = !inQuotes;
                continue;
            }
            if (inQuotes)
            {
                continue;
            }
            if (c == '\n')
            {
                linesSeen++;
                continue;
            }
            if (scores.ContainsKey(c))
            {
                scores[c]++;
            }
        }

        var best = scores.OrderByDescending(pair => pair.Value).First();
        return best.Value > 0 ? best.Key : '\0';
    }

    private static (List<List<string>> Records, bool UnclosedQuote) ParseRecords(
        string text, char delimiter)
    {
        var records = new List<List<string>>();
        var row = new List<string>();
        var field = new StringBuilder();
        var inQuotes = false;

        void FlushField()
        {
            row.Add(field.ToString().Trim());
            field.Clear();
        }

        void FlushRow()
        {
            FlushField();
            records.Add(row);
            row = new List<string>();
        }

        for (var index = 0; index < text.Length; index++)
        {
            var c = text[index];
            if (inQuotes)
            {
                if (c == '"')
                {
                    if (index + 1 < text.Length && text[index + 1] == '"')
                    {
                        field.Append('"');
                        index++;
                    }
                    else
                    {
                        inQuotes = false;
                    }
                }
                else
                {
                    field.Append(c);
                }
                continue;
            }

            if (c == '"' && field.Length == 0)
            {
                inQuotes = true;
            }
            else if (delimiter != '\0' && c == delimiter)
            {
                FlushField();
            }
            else if (c == '\n')
            {
                FlushRow();
            }
            else
            {
                field.Append(c);
            }
        }

        if (row.Count > 0 || field.Length > 0)
        {
            FlushRow();
        }

        return (records, inQuotes);
    }
}
