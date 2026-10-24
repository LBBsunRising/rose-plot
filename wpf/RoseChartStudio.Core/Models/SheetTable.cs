namespace RoseChartStudio.Core.Models;

/// <summary>Raw sheet content read from an Excel workbook.</summary>
public sealed class SheetTable
{
    public required string SheetName { get; init; }
    public required IReadOnlyList<string> Headers { get; init; }
    public required IReadOnlyList<IReadOnlyList<string>> Rows { get; init; }

    public int RowCount => Rows.Count;
    public int ColumnCount => Headers.Count;

    public int IndexOf(string header)
    {
        for (var index = 0; index < Headers.Count; index++)
        {
            if (string.Equals(Headers[index], header, StringComparison.OrdinalIgnoreCase))
            {
                return index;
            }
        }
        return -1;
    }

    public IEnumerable<string> ValuesIn(string header)
    {
        var index = IndexOf(header);
        if (index < 0)
        {
            yield break;
        }
        foreach (var row in Rows)
        {
            if (index < row.Count)
            {
                yield return row[index];
            }
        }
    }

    public SheetTable WithRows(IReadOnlyList<IReadOnlyList<string>> rows) =>
        new() { SheetName = SheetName, Headers = Headers, Rows = rows };
}

/// <summary>One grouped value with its count and share of the total.</summary>
public sealed record CountItem(string Value, int Count, double Share)
{
    public string PercentText(int decimals) => (Share * 100.0).ToString($"F{decimals}") + "%";
}
