using System.IO;
using System.Reflection;
using System.Text;

namespace RoseChartStudio.TestRunner;

/// <summary>
/// In-process xUnit Fact/Theory runner. The sandbox used for this project blocks the
/// VSTest testhost (it cannot open a handle to its parent process), so the QA runner
/// executes the same test assembly through reflection instead of `dotnet test`.
/// </summary>
internal static class Program
{
    private static int Main()
    {
        var assembly = Assembly.Load("RoseChartStudio.Tests");
        var passed = 0;
        var failed = new List<string>();
        var skipped = 0;
        var lines = new StringBuilder();
        foreach (var type in assembly.GetTypes().OrderBy(type => type.FullName, StringComparer.Ordinal))
        {
            if (type.IsAbstract || type.IsInterface)
            {
                continue;
            }
            var methods = type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly)
                .OrderBy(method => method.Name, StringComparer.Ordinal)
                .ToList();
            if (methods.Count == 0)
            {
                continue;
            }
            object? instance = null;
            try
            {
                foreach (var method in methods)
                {
                    var customAttributes = method.GetCustomAttributesData();
                    var fact = customAttributes.FirstOrDefault(attribute =>
                        attribute.AttributeType.FullName == "Xunit.FactAttribute");
                    var theory = customAttributes.FirstOrDefault(attribute =>
                        attribute.AttributeType.FullName == "Xunit.TheoryAttribute");
                    if (fact is null && theory is null)
                    {
                        continue;
                    }
                    var skipReason = (fact ?? theory)!.NamedArguments
                        .FirstOrDefault(argument => argument.MemberName == "Skip").TypedValue.Value as string;
                    if (!string.IsNullOrEmpty(skipReason))
                    {
                        skipped++;
                        continue;
                    }
                    var dataRows = customAttributes
                        .Where(attribute => attribute.AttributeType.FullName == "Xunit.InlineDataAttribute")
                        .Select(ExtractInlineData)
                        .ToList();
                    if (theory is not null && dataRows.Count == 0)
                    {
                        skipped++;
                        lines.AppendLine($"SKIP  {type.Name}.{method.Name} (non-inline theory data)");
                        continue;
                    }
                    if (dataRows.Count == 0)
                    {
                        instance ??= Activator.CreateInstance(type);
                        if (Invoke(method, instance!, Array.Empty<object>(), type.Name, failed, lines))
                        {
                            passed++;
                        }
                    }
                    else
                    {
                        foreach (var row in dataRows)
                        {
                            instance ??= Activator.CreateInstance(type);
                            if (Invoke(method, instance!, row, type.Name, failed, lines))
                            {
                                passed++;
                            }
                        }
                    }
                }
            }
            finally
            {
                (instance as IDisposable)?.Dispose();
            }
        }
        lines.AppendLine();
        lines.AppendLine($"passed={passed} failed={failed.Count} skipped={skipped}");
        if (failed.Count > 0)
        {
            lines.AppendLine("FAILURES:");
            foreach (var failure in failed)
            {
                lines.AppendLine("  " + failure);
            }
        }
        var report = lines.ToString();
        Console.WriteLine(report);
        var outputDirectory = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "_qa"));
        Directory.CreateDirectory(outputDirectory);
        File.WriteAllText(Path.Combine(outputDirectory, "test_runner.txt"), report);
        return failed.Count > 0 ? 1 : 0;
    }

    private static object?[] ExtractInlineData(CustomAttributeData attribute)
    {
        var arguments = attribute.ConstructorArguments;
        if (arguments.Count == 1 &&
            arguments[0].Value is IReadOnlyCollection<CustomAttributeTypedArgument> nested)
        {
            return nested.Select(argument => argument.Value).ToArray();
        }
        return arguments.Select(argument => argument.Value).ToArray();
    }
    private static bool Invoke(
        MethodInfo method, object instance, object?[] arguments, string typeName,
        List<string> failed, StringBuilder lines)
    {
        try
        {
            method.Invoke(instance, arguments);
            passedLine(lines, typeName, method.Name, arguments);
            return true;
        }
        catch (TargetInvocationException exception)
        {
            var inner = exception.InnerException ?? exception;
            failed.Add($"{typeName}.{method.Name}: {inner.GetType().Name}: {inner.Message}");
            lines.AppendLine($"FAIL  {typeName}.{method.Name}: {inner.GetType().Name}: {inner.Message}");
            return false;
        }
        catch (Exception exception)
        {
            failed.Add($"{typeName}.{method.Name}: {exception.GetType().Name}: {exception.Message}");
            lines.AppendLine($"FAIL  {typeName}.{method.Name}: {exception.GetType().Name}: {exception.Message}");
            return false;
        }
    }

    private static void passedLine(StringBuilder lines, string typeName, string methodName, object?[] arguments)
    {
        if (arguments.Length == 0)
        {
            lines.AppendLine($"PASS  {typeName}.{methodName}");
        }
        else
        {
            lines.AppendLine($"PASS  {typeName}.{methodName}({string.Join(", ", arguments.Select(value => value?.ToString() ?? "null"))})");
        }
    }
}
