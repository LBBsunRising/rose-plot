using System.Text.RegularExpressions;

namespace RoseChartStudio.Core.Palettes;

/// <summary>
/// Hex / RGB / HSL / WCAG / CIELAB colour utilities, ported 1:1 from
/// <c>rose/rosechart/palettes.py</c> (which itself only uses the Python standard library).
/// </summary>
/// <remarks>
/// Every public method returns upper-case <c>#RRGGBB</c> strings.  The arithmetic is
/// kept in the same order as the Python source so that ported behaviour (including
/// banker's rounding and the <c>colorsys</c> HSL algorithm) is bit-for-bit equivalent.
/// </remarks>
public static class ColorMath
{
    /// <summary>Default single label colour (same as the Python module constant).</summary>
    public const string DefaultLabelColor = "#334155";

    /// <summary>Default label background (white).</summary>
    public const string DefaultBackground = "#FFFFFF";

    /// <summary>Minimum WCAG contrast a chart label must reach against its background.</summary>
    public const double LabelMinContrast = 3.0;

    /// <summary>Internal target contrast, slightly above the minimum to absorb 8-bit rounding.</summary>
    public const double LabelTargetContrast = 3.2;

    private const double XyzWhiteX = 0.95047;
    private const double XyzWhiteY = 1.0;
    private const double XyzWhiteZ = 1.08883;
    private const double LabEpsilon = 216.0 / 24389.0; // (6/29)^3
    private const double LabKappa = 24389.0 / 27.0;    // (29/3)^3

    // Matches palette.py's _HEX_RE: optional '#', then 3 or 6 hex digits.
    private static readonly Regex HexRegex = new(
        @"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
        RegexOptions.CultureInvariant,
        TimeSpan.FromSeconds(2));

    // ---------------------------------------------------------------------
    // Basic conversions
    // ---------------------------------------------------------------------

    /// <summary>
    /// Normalises a colour to upper-case <c>#RRGGBB</c>.
    /// Accepts <c>#aabbcc</c>, <c>aabbcc</c>, <c>#abc</c> and <c>abc</c>; throws
    /// <see cref="ArgumentException"/> for anything else.
    /// </summary>
    public static string NormalizeHex(string value)
    {
        if (value is null)
        {
            throw new ArgumentNullException(nameof(value), "颜色必须是字符串");
        }

        var text = value.Trim();
        var match = HexRegex.Match(text);
        if (!match.Success)
        {
            throw new ArgumentException($"不是合法的十六进制颜色：'{value}'", nameof(value));
        }

        var digits = match.Groups[1].Value;
        if (digits.Length == 3)
        {
            digits = string.Concat(digits[0], digits[0], digits[1], digits[1], digits[2], digits[2]);
        }

        return "#" + digits.ToUpperInvariant();
    }

    /// <summary>Returns whether <paramref name="value"/> is a parsable hex colour.</summary>
    public static bool IsHexColor(string? value)
    {
        if (value is null)
        {
            return false;
        }

        try
        {
            NormalizeHex(value);
        }
        catch (ArgumentException)
        {
            return false;
        }

        return true;
    }

    /// <summary><c>#RRGGBB</c> -&gt; <c>(r, g, b)</c>, each channel 0-255.</summary>
    public static (int R, int G, int B) HexToRgb(string color)
    {
        var text = NormalizeHex(color);
        return (
            Convert.ToInt32(text.Substring(1, 2), 16),
            Convert.ToInt32(text.Substring(3, 2), 16),
            Convert.ToInt32(text.Substring(5, 2), 16));
    }

    /// <summary><c>(r, g, b)</c> -&gt; <c>#RRGGBB</c>; channels are rounded and clamped to 0-255.</summary>
    public static string RgbToHex(double red, double green, double blue) =>
        "#" + RoundChannel(red).ToString("X2") +
        RoundChannel(green).ToString("X2") +
        RoundChannel(blue).ToString("X2");

    private static int RoundChannel(double component)
    {
        // Python: channel = int(round(float(component))); clamp(0, 255).
        // Math.Round defaults to banker's rounding (ToEven), exactly like Python's round().
        var channel = (int)Math.Round(component);
        return Math.Min(255, Math.Max(0, channel));
    }

    // ---------------------------------------------------------------------
    // WCAG relative luminance / contrast
    // ---------------------------------------------------------------------

    private static double Linearize(int channel)
    {
        var value = channel / 255.0;
        if (value <= 0.04045)
        {
            return value / 12.92;
        }

        return Math.Pow((value + 0.055) / 1.055, 2.4);
    }

    private static double Delinearize(double value)
    {
        var clamped = Clamp01(value);
        if (clamped <= 0.0031308)
        {
            return clamped * 12.92;
        }

        return 1.055 * Math.Pow(clamped, 1.0 / 2.4) - 0.055;
    }

    /// <summary>WCAG relative luminance (0.0-1.0).</summary>
    public static double Luminance(string color)
    {
        var (red, green, blue) = HexToRgb(color);
        return 0.2126 * Linearize(red)
               + 0.7152 * Linearize(green)
               + 0.0722 * Linearize(blue);
    }

    /// <summary>WCAG contrast ratio (1.0-21.0), order independent.</summary>
    public static double ContrastRatio(string colorA, string colorB)
    {
        var luminanceA = Luminance(colorA);
        var luminanceB = Luminance(colorB);
        var lighter = Math.Max(luminanceA, luminanceB);
        var darker = Math.Min(luminanceA, luminanceB);
        return (lighter + 0.05) / (darker + 0.05);
    }

    // ---------------------------------------------------------------------
    // Mixing / darkening / lightening
    // ---------------------------------------------------------------------

    /// <summary>
    /// Mixes two colours in linear-light space by <paramref name="weight"/>
    /// (0 -&gt; a, 1 -&gt; b).  Linear-light mixing avoids the greyish midpoint of sRGB
    /// interpolation, matching the Python implementation.
    /// </summary>
    public static string MixColors(string colorA, string colorB, double weight = 0.5)
    {
        if (!(weight >= 0.0 && weight <= 1.0))
        {
            throw new ArgumentOutOfRangeException(nameof(weight), weight, "weight 必须在 0-1 之间");
        }

        var (redA, greenA, blueA) = HexToRgb(colorA);
        var (redB, greenB, blueB) = HexToRgb(colorB);

        var linearRed = (1.0 - weight) * Linearize(redA) + weight * Linearize(redB);
        var linearGreen = (1.0 - weight) * Linearize(greenA) + weight * Linearize(greenB);
        var linearBlue = (1.0 - weight) * Linearize(blueA) + weight * Linearize(blueB);

        return RgbToHex(
            Delinearize(linearRed) * 255.0,
            Delinearize(linearGreen) * 255.0,
            Delinearize(linearBlue) * 255.0);
    }

    /// <summary>Darkens a colour by lowering its HSL lightness by <paramref name="amount"/> (0-1).</summary>
    public static string Darken(string color, double amount = 0.15)
    {
        var level = ClampAmount(amount);
        var (hue, saturation, lightness) = RgbToHsl(color);
        return HslToHex(hue, saturation, lightness * (1.0 - level));
    }

    /// <summary>Lightens a colour by moving its HSL lightness towards 1.0 by <paramref name="amount"/> (0-1).</summary>
    public static string Lighten(string color, double amount = 0.15)
    {
        var level = ClampAmount(amount);
        var (hue, saturation, lightness) = RgbToHsl(color);
        return HslToHex(hue, saturation, lightness + (1.0 - lightness) * level);
    }

    private static double ClampAmount(double amount)
    {
        if (!(amount >= 0.0 && amount <= 1.0))
        {
            throw new ArgumentOutOfRangeException(nameof(amount), amount, "amount 必须在 0-1 之间");
        }

        return amount;
    }

    // ---------------------------------------------------------------------
    // HSL (ports Python's colorsys with the CPython 3.11 formulas)
    // ---------------------------------------------------------------------

    /// <summary><c>#RRGGBB</c> -&gt; <c>(hue degrees, saturation, lightness)</c>; the latter two are 0-1.</summary>
    public static (double Hue, double Saturation, double Lightness) RgbToHsl(string color)
    {
        var (redChannel, greenChannel, blueChannel) = HexToRgb(color);
        var red = redChannel / 255.0;
        var green = greenChannel / 255.0;
        var blue = blueChannel / 255.0;

        // Port of colorsys.rgb_to_hls (CPython 3.11, including the gh-106498 fix:
        // s = rangec / (2.0 - maxc - minc), not 2.0 - sumc).
        var maxChannel = Math.Max(red, Math.Max(green, blue));
        var minChannel = Math.Min(red, Math.Min(green, blue));
        var sumChannel = maxChannel + minChannel;
        var rangeChannel = maxChannel - minChannel;
        var lightness = sumChannel / 2.0;
        if (minChannel == maxChannel)
        {
            return (0.0, 0.0, lightness);
        }

        var saturation = lightness <= 0.5
            ? rangeChannel / sumChannel
            : rangeChannel / (2.0 - maxChannel - minChannel);

        var rc = (maxChannel - red) / rangeChannel;
        var gc = (maxChannel - green) / rangeChannel;
        var bc = (maxChannel - blue) / rangeChannel;

        double hue;
        if (red == maxChannel)
        {
            hue = bc - gc;
        }
        else if (green == maxChannel)
        {
            hue = 2.0 + rc - bc;
        }
        else
        {
            hue = 4.0 + gc - rc;
        }

        hue = PyMod(hue / 6.0, 1.0);
        return (hue * 360.0, saturation, lightness);
    }

    /// <summary><c>(hue degrees, saturation, lightness)</c> -&gt; <c>#RRGGBB</c>.</summary>
    public static string HslToHex(double hue, double saturation, double lightness)
    {
        var normalizedHue = PyMod(hue, 360.0) / 360.0;
        var clampedSaturation = Clamp01(saturation);
        var clampedLightness = Clamp01(lightness);

        // Port of colorsys.hls_to_rgb.
        double red;
        double green;
        double blue;
        if (clampedSaturation == 0.0)
        {
            red = clampedLightness;
            green = clampedLightness;
            blue = clampedLightness;
        }
        else
        {
            var m2 = clampedLightness <= 0.5
                ? clampedLightness * (1.0 + clampedSaturation)
                : clampedLightness + clampedSaturation - (clampedLightness * clampedSaturation);
            var m1 = 2.0 * clampedLightness - m2;
            red = V(m1, m2, normalizedHue + OneThird);
            green = V(m1, m2, normalizedHue);
            blue = V(m1, m2, normalizedHue - OneThird);
        }

        return RgbToHex(red * 255.0, green * 255.0, blue * 255.0);
    }

    private const double OneThird = 1.0 / 3.0;
    private const double OneSixth = 1.0 / 6.0;
    private const double TwoThird = 2.0 / 3.0;

    private static double V(double m1, double m2, double hue)
    {
        hue = PyMod(hue, 1.0);
        if (hue < OneSixth)
        {
            return m1 + (m2 - m1) * hue * 6.0;
        }

        if (hue < 0.5)
        {
            return m2;
        }

        if (hue < TwoThird)
        {
            return m1 + (m2 - m1) * (TwoThird - hue) * 6.0;
        }

        return m1;
    }

    // ---------------------------------------------------------------------
    // CIELAB / Delta E
    // ---------------------------------------------------------------------

    /// <summary>CIELAB delta-E76 colour distance (about 2.3 is the just-noticeable difference).</summary>
    public static double DeltaE(string colorA, string colorB)
    {
        var (l1, a1, b1) = HexToLab(colorA);
        var (l2, a2, b2) = HexToLab(colorB);
        var deltaL = l1 - l2;
        var deltaA = a1 - a2;
        var deltaB = b1 - b2;
        return Math.Sqrt(deltaL * deltaL + deltaA * deltaA + deltaB * deltaB);
    }

    private static (double L, double A, double B) HexToLab(string color)
    {
        var (red, green, blue) = HexToRgb(color);
        var linearRed = Linearize(red);
        var linearGreen = Linearize(green);
        var linearBlue = Linearize(blue);

        var x = 0.4124564 * linearRed + 0.3575761 * linearGreen + 0.1804375 * linearBlue;
        var y = 0.2126729 * linearRed + 0.7151522 * linearGreen + 0.0721750 * linearBlue;
        var z = 0.0193339 * linearRed + 0.1191920 * linearGreen + 0.9503041 * linearBlue;

        var fx = LabF(x / XyzWhiteX);
        var fy = LabF(y / XyzWhiteY);
        var fz = LabF(z / XyzWhiteZ);
        return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz));
    }

    private static double LabF(double value)
    {
        if (value > LabEpsilon)
        {
            return Math.Pow(value > 0.0 ? value : 0.0, 1.0 / 3.0);
        }

        return (LabKappa * value + 16.0) / 116.0;
    }

    // ---------------------------------------------------------------------
    // Helpers that mirror Python semantics
    // ---------------------------------------------------------------------

    /// <summary>CPython's float <c>%</c> operator (fmod with the divisor's sign).</summary>
    private static double PyMod(double value, double modulus)
    {
        var result = value % modulus;
        if (result != 0.0 && (result < 0.0) != (modulus < 0.0))
        {
            result += modulus;
        }

        return result;
    }

    /// <summary>
    /// Mirrors <c>min(1.0, max(0.0, value))</c> for float inputs, including Python's
    /// NaN behaviour (NaN is clamped to 0.0).
    /// </summary>
    private static double Clamp01(double value)
    {
        var lower = value > 0.0 ? value : 0.0;
        return lower < 1.0 ? lower : 1.0;
    }
}
