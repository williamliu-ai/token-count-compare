// Syntax-heavy JavaScript fixture. Not intended to run.
import fs, { promises as fsp } from "node:fs";
export const VERSION = "0.0.0";

class Registry extends Map {
  static defaultName = "registry";
  #secret = Symbol("secret");
  constructor(entries = []) { super(entries); }
  get secret() { return this.#secret; }
  async *stream(prefix = "") {
    for (const [key, value] of this) yield `${prefix}${key}:${value}`;
  }
}

function tag(strings, ...values) { return String.raw({ raw: strings }, ...values); }
const arrow = ({ a = 1, b: alias, ...rest } = {}) => alias ?? a ?? rest;
const obj = {
  __proto__: null,
  method(x) { return x?.nested?.value ?? "fallback"; },
  async fetchLike(url, { signal } = {}) { return await Promise.resolve({ url, signal }); },
  [Symbol.iterator]: function* () { yield* [1, 2, 3]; },
};

try {
  for await (const line of new Registry([["x", 1]]).stream("#")) console.log(line);
  const pattern = /(?<word>\w+)\s+\1/giu;
  const result = tag`template ${arrow({ b: 2 })} ${pattern.source}`;
  switch (typeof result) { case "string": break; default: throw new Error("bad"); }
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
} finally {
  void fsp.readFile?.("missing").catch(() => null);
}

export default Object.freeze({ Registry, obj, fs });

// --- Additional representative syntax coverage ---
/**
 * JSDoc block with @param {number[]} values and @returns {bigint}.
 */
function moreJavaScriptSyntax(values = [0xFF, 0b1010, 1_000, 1.2e3]) {
  let total = 0;
  var legacy = "var-scope";
  outer: for (let i = 0; i < values.length; i++) {
    total += values[i];
    if ((total & 1) === 0) continue outer;
    while (total > 10) { total >>= 1; break; }
    do { total ||= 1; total &&= 255; total ??= 42; } while (false);
  }
  for (const index in values) total ^= Number(index);
  const [first, second = 2, ...rest] = values;
  const spread = { ...obj, first, second, rest, big: 123n, hex: 0xff };
  const ternary = total > 10 ? "large" : total === 0 ? "zero" : "small";
  class WithAccessors { static { this.ready = true; } get value() { return total; } set value(v) { total = v; } }
  @sealed class DecoratedExample {}
  await Promise.resolve?.(spread);
  return `${legacy}:${ternary}:${new WithAccessors().value}`;
}
