// Syntax-heavy Java fixture. Not intended to compile.
package example.syntax;

import java.io.*;
import java.lang.annotation.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

@Target({ElementType.TYPE, ElementType.METHOD}) @Retention(RetentionPolicy.RUNTIME)
@interface Demo { String value() default "demo"; }

sealed interface Shape permits Circle, Rect { double area(); }
record Circle(double radius) implements Shape { public double area() { return Math.PI * radius * radius; } }
record Rect(double width, double height) implements Shape { public double area() { return width * height; } }

enum Status { NEW, RUNNING, DONE }

@Demo("class")
public class Syntax<T extends Number & Comparable<T>> implements AutoCloseable {
    private final List<T> values = new ArrayList<>();
    public static final String TEXT = "hello";

    public Syntax(Collection<? extends T> input) { values.addAll(input); }

    @SafeVarargs public final <R> Optional<R> map(Function<? super T, ? extends R> fn, T... extra) {
        try (var ignored = this) {
            return values.stream().findFirst().map(fn);
        } catch (Exception ex) {
            throw new IllegalStateException("wrapped", ex);
        }
    }

    public String describe(Shape shape) {
        return switch (shape) {
            case Circle c when c.radius() > 10 -> "large circle";
            case Circle c -> "circle " + c.radius();
            case Rect(var w, var h) -> STR."rect \{w}x\{h}";
        };
    }

    public CompletableFuture<Void> runAsync() {
        return CompletableFuture.runAsync(() -> values.forEach(System.out::println));
    }

    @Override public void close() {}

    public static void main(String[] args) throws Exception {
        var s = new Syntax<Integer>(List.of(1, 2, 3));
        Map<String, ? super Integer> map = new HashMap<>();
        for (int i = 0; i < args.length; i++) map.put(args[i], i);
        synchronized (s) { assert !map.isEmpty() || args.length == 0; }
    }
}

/*
 * Additional representative Java syntax coverage: literals, control flow,
 * anonymous/inner classes, instanceof pattern, casts, bitwise operators.
 */
abstract class ExtraJavaSyntax {
    protected volatile transient long flags = 0xFF_FFL | 0b1010_0101L;
    private double scientific = 6.022e23d;
    private String block = """
        text block with \"quotes\", ${template-ish}, and newlines
        """;

    interface Named { default String name() { return "named"; } }
    abstract Number compute(Number input);

    void run(Object obj) {
        if (obj instanceof String s && !s.isBlank()) {
            flags ^= s.length();
        } else if (obj instanceof Integer i) {
            flags += (long) i;
        } else {
            flags = flags << 1 >>> 1;
        }
        int value = obj == null ? -1 : ((Number) compute(1)).intValue();
        while (value-- > 0) { if (value == 2) break; }
        do { value++; } while (value < 0);
        class LocalInner { String label() { return ExtraJavaSyntax.super.toString(); } }
        Named anon = new Named() { @Override public String name() { return "anon"; } };
        Runnable blockLambda = () -> { System.out.println(anon.name() + new LocalInner().label()); };
        switch (value) { case 1, 2 -> blockLambda.run(); default -> { yieldLike(); } }
    }

    void yieldLike() {}
}
