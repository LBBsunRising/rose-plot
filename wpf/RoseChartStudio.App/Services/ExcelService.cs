using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using ClosedXML.Excel;
using RoseChartStudio.Core.Models;

namespace RoseChartStudio.App.Services;

/// <summary>
/// Reads Excel workbooks into <see cref="SheetTable"/> instances with ClosedXML.
/// </summary>
/// <remarks>
/// Reading rules:
/// <list type="bullet">
///   <item>the first used row is the header row (header text is trimmed);</item>
///   <item>blank header cells are named after their Excel column, e.g. <c>列3</c>;</item>
///   <item>duplicate headers get a numeric suffix, pandas style: <c>数量</c>, <c>数量.1</c>, ...;</item>
///   <item>all used columns up to the widest used cell are materialised, short rows are padded with <c>""</c>;</item>
///   <item>cells are preserved as display strings: text verbatim, numbers with invariant culture,
///         dates as <c>yyyy-MM-dd</c>, blanks as <c>""</c>; cell number formats are not applied;</item>
///   <item>rows whose cells are all empty are skipped.</item>
/// </list>
/// </remarks>
public sealed class ExcelService
{
    /// <summary>Lists the sheet names of a workbook, in workbook order.</summary>
    /// <exception cref="FileNotFoundException">The file does not exist.</exception>
    /// <exception cref="InvalidOperationException">The file cannot be opened as an Excel workbook.</exception>
    public IReadOnlyList<string> GetSheetNames(string path)
    {
        var fullPath = ResolveFile(path);

        try
        {
            using var workbook = new XLWorkbook(fullPath);
            return workbook.Worksheets.Select(worksheet => worksheet.Name).ToArray();
        }
        catch (Exception exception) when (exception is not FileNotFoundException)
        {
            throw new InvalidOperationException(BuildReadError("无法读取 Excel 工作表列表", exception), exception);
        }
    }

    /// <summary>Reads one worksheet into a <see cref="SheetTable"/>.</summary>
    /// <exception cref="FileNotFoundException">The file does not exist.</exception>
    /// <exception cref="ArgumentException">The workbook has no sheet named <paramref name="sheetName"/>.</exception>
    /// <exception cref="InvalidOperationException">The workbook cannot be opened.</exception>
    public SheetTable ReadSheet(string path, string sheetName)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sheetName);
        var fullPath = ResolveFile(path);

        XLWorkbook workbook;
        try
        {
            workbook = new XLWorkbook(fullPath);
        }
        catch (Exception exception) when (exception is not FileNotFoundException)
        {
            throw new InvalidOperationException(BuildReadError("无法读取 Excel 文件", exception), exception);
        }

        using (workbook)
        {
            if (!workbook.TryGetWorksheet(sheetName, out var worksheet))
            {
                var available = string.Join("、", workbook.Worksheets.Select(sheet => sheet.Name));
                throw new ArgumentException($"工作表“{sheetName}”不存在。当前工作表为：{available}", nameof(sheetName));
            }

            return ReadWorksheet(worksheet);
        }
    }

    private static string BuildReadError(string title, Exception exception)
    {
        var hint = exception is UnauthorizedAccessException ||
                   exception.Message.Contains("Access to the path", StringComparison.OrdinalIgnoreCase) ||
                   exception.Message.Contains("访问被拒绝", StringComparison.Ordinal) ||
                   exception.Message.Contains("拒绝访问", StringComparison.Ordinal)
            ? $"{Environment.NewLine}提示：读取 Excel 需要可写的临时目录。请把程序放在可写文件夹（例如桌面或文档目录）后重试；应用已自动把 TMP/TEMP 指向程序目录。"
            : "";
        return $"{title}：{Environment.NewLine}{exception.Message}{hint}";
    }
    private static string ResolveFile(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        var fullPath = Path.GetFullPath(path);
        if (!File.Exists(fullPath))
        {
            throw new FileNotFoundException($"找不到 Excel 文件：{fullPath}", fullPath);
        }

        return fullPath;
    }

    private static SheetTable ReadWorksheet(IXLWorksheet worksheet)
    {
        var firstRowCell = worksheet.FirstRowUsed(XLCellsUsedOptions.AllContents);
        var lastRowCell = worksheet.LastRowUsed(XLCellsUsedOptions.AllContents);
        var firstColumnCell = worksheet.FirstColumnUsed(XLCellsUsedOptions.AllContents);
        var lastColumnCell = worksheet.LastColumnUsed(XLCellsUsedOptions.AllContents);
        if (firstRowCell is null || lastRowCell is null || firstColumnCell is null || lastColumnCell is null)
        {
            return new SheetTable
            {
                SheetName = worksheet.Name,
                Headers = Array.Empty<string>(),
                Rows = Array.Empty<IReadOnlyList<string>>(),
            };
        }

        var firstRow = firstRowCell.RowNumber();
        var lastRow = lastRowCell.RowNumber();
        var firstColumn = firstColumnCell.ColumnNumber();
        var lastColumn = lastColumnCell.ColumnNumber();
        var columnCount = lastColumn - firstColumn + 1;

        var headers = ReadHeaders(worksheet, firstRow, firstColumn, columnCount);

        var rows = new List<IReadOnlyList<string>>();
        for (var rowNumber = firstRow + 1; rowNumber <= lastRow; rowNumber++)
        {
            var values = new string[columnCount];
            var hasValue = false;
            for (var offset = 0; offset < columnCount; offset++)
            {
                var text = CellToText(worksheet.Cell(rowNumber, firstColumn + offset));
                values[offset] = text;
                hasValue |= text.Length > 0;
            }

            if (hasValue)
            {
                rows.Add(values);
            }
        }

        return new SheetTable
        {
            SheetName = worksheet.Name,
            Headers = headers,
            Rows = rows,
        };
    }

    private static string[] ReadHeaders(IXLWorksheet worksheet, int headerRow, int firstColumn, int columnCount)
    {
        var headers = new string[columnCount];
        var used = new HashSet<string>(StringComparer.Ordinal);
        for (var offset = 0; offset < columnCount; offset++)
        {
            var columnNumber = firstColumn + offset;
            var header = CellToText(worksheet.Cell(headerRow, columnNumber)).Trim();
            if (header.Length == 0)
            {
                header = $"列{columnNumber}";
            }

            if (!used.Add(header))
            {
                var suffix = 1;
                string candidate;
                do
                {
                    candidate = $"{header}.{suffix}";
                    suffix++;
                }
                while (!used.Add(candidate));
                header = candidate;
            }

            headers[offset] = header;
        }

        return headers;
    }

    /// <summary>
    /// Converts a cell to its raw display string. The cell style / number format is deliberately
    /// ignored so that the chart uses the stored value (e.g. <c>0.72</c> instead of <c>72%</c>).
    /// </summary>
    private static string CellToText(IXLCell cell)
    {
        switch (cell.DataType)
        {
            case XLDataType.Blank:
                return string.Empty;
            case XLDataType.Text:
                return cell.GetText();
            case XLDataType.Boolean:
                return cell.GetBoolean() ? "True" : "False";
            case XLDataType.Number:
                return cell.GetDouble().ToString(CultureInfo.InvariantCulture);
            case XLDataType.DateTime:
                return cell.GetDateTime().ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            case XLDataType.TimeSpan:
                return cell.GetTimeSpan().ToString("c", CultureInfo.InvariantCulture);
            case XLDataType.Error:
                return cell.GetError().ToString();
            default:
                return cell.GetString();
        }
    }
}
