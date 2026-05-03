// Syntax-heavy C# fixture. Not intended to compile.
#nullable enable
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Example.Syntax;

[AttributeUsage(AttributeTargets.All)]
public sealed class DemoAttribute(string name) : Attribute { public string Name { get; } = name; }

public interface IRepository<in TKey, TValue> where TValue : class { TValue? this[TKey key] { get; set; } }
public readonly record struct Point(int X, int Y);
public record Person(string Name, int Age) { public required string Email { get; init; } }

public enum Status { New = 1, Running, Done }

[Demo("syntax")]
public class Sample<T> : IDisposable where T : notnull
{
    private readonly Dictionary<string, T> _items = new();
    public event EventHandler<string>? Changed;
    public T? Optional { get; init; }
    public ref readonly T First => ref _items.Values.First();

    public async IAsyncEnumerable<string> StreamAsync(params string[] keys)
    {
        foreach (var key in keys)
        {
            await Task.Yield();
            yield return _items.TryGetValue(key, out var value) ? $"{key}:{value}" : key;
        }
    }

    public object Match(object input) => input switch
    {
        null => throw new ArgumentNullException(nameof(input)),
        Point { X: > 0, Y: var y } p when y >= 0 => p with { Y = y + 1 },
        Person(var name, _) { Email: { Length: > 3 } email } => (name, email),
        string s and not "" => s[..Math.Min(3, s.Length)],
        _ => default(int?)
    };

    public static Sample<T> operator +(Sample<T> left, (string key, T value) pair) { left._items[pair.key] = pair.value; return left; }
    public void Dispose() => Changed?.Invoke(this, "disposed");
}

/* Additional representative C# syntax coverage: exceptions, LINQ, raw/verbatim
   strings, preprocessor, tuples, local functions, pattern checks, using blocks. */
public partial class MoreCSharpSyntax
{
#if DEBUG
    private const string Mode = "debug";
#else
    private const string Mode = "release";
#endif
    public unsafe void* Pointer;
    public void Run(IEnumerable<int> source)
    {
        var raw = """
            raw string with "quotes", {braces}, and newlines
            """;
        var verbatim = @"C:\temp\file.txt";
        using var memory = new MemoryStream();
        try
        {
            (int count, string label) tuple = (source.Count(), Mode);
            var query = source.Where(static x => (x & 1) == 0).Select(x => x * x).ToList();
            int Local(int x) => x is > 10 and < 100 ? x : default(int);
            var collection = [1, 2, 3, .. query];
            foreach (var item in collection) { if (item == 0) continue; memory.WriteByte((byte)Local(item)); }
        }
        catch (IOException ex) when (ex.Message is { Length: > 0 })
        {
            throw new InvalidOperationException($"{verbatim}:{raw}", ex);
        }
        finally { memory.Flush(); }
    }
}
