namespace RoseChartStudio.Core.Models;

/// <summary>A (label, value) pair after ordering and zero filtering.</summary>
public sealed record ChartPair(string Label, int Value);

/// <summary>Label offset stored by the layout engine (data coordinate units).</summary>
public sealed record LayoutOffset(double Dx, double Dy);

/// <summary>Input snapshot needed to build a chart scene.</summary>
public sealed class ChartSpec
{
    public List<string> Labels { get; set; } = new();
    public List<int> Values { get; set; } = new();
    public ChartStyle Style { get; set; } = new();
    public Dictionary<string, string> FillColors { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string, string> LabelColors { get; set; } = new(StringComparer.Ordinal);
    public Dictionary<string, LayoutOffset> LayoutOffsets { get; set; } = new(StringComparer.Ordinal);
    /// <summary>Optional custom label order; when set it wins over input order.</summary>
    public List<string>? Order { get; set; }

    public IReadOnlyList<ChartPair> ResolvePairs()
    {
        var pairs = new List<ChartPair>(Math.Min(Labels.Count, Values.Count));
        var count = Math.Min(Labels.Count, Values.Count);
        for (var index = 0; index < count; index++)
        {
            if (Values[index] > 0)
            {
                pairs.Add(new ChartPair(Labels[index], Values[index]));
            }
        }
        if (Order is { Count: > 0 })
        {
            var rank = new Dictionary<string, int>(StringComparer.Ordinal);
            for (var index = 0; index < Order.Count; index++)
            {
                rank[Order[index]] = index;
            }
            pairs.Sort((left, right) =>
            {
                var leftRank = rank.TryGetValue(left.Label, out var lr) ? lr : rank.Count;
                var rightRank = rank.TryGetValue(right.Label, out var rr) ? rr : rank.Count;
                var rankCompare = leftRank.CompareTo(rightRank);
                return rankCompare != 0 ? rankCompare : right.Value.CompareTo(left.Value);
            });
        }
        return pairs;
    }
}
