// Controlled TypeScript fixture: code-heavy input with comments and compound identifiers.
// The file mixes type declarations, generics, async logic, and ordinary control flow
// so the tokenizer sees a realistic surface area for a TypeScript codebase.

/**
 * A short, opinionated catalog of token-count observation kinds. The literal
 * union is intentionally narrow; in real code we would prefer a discriminated
 * union over a string literal, but this shape is closer to what shows up in
 * configuration files and quick scripts.
 */
export type TokenCountProvider =
  | "anthropic-count-tokens"
  | "openai-input-tokens"
  | "local-tiktoken";

export type SizeTier = "probe" | "signal" | "scaling";

export interface TokenCountObservation {
  fixtureName: string;
  provider: TokenCountProvider;
  model: string;
  inputTokenCount: number | null;
  byteLengthUtf8: number;
  characterLength: number;
  exactnessNote: string;
  sizeTier?: SizeTier;
}

export interface ObservationSummary {
  fixtureName: string;
  byProvider: Record<TokenCountProvider, number | null>;
  deltas: Array<{ a: TokenCountProvider; b: TokenCountProvider; delta: number | null }>;
}

const TIER_THRESHOLDS = {
  probeMaxTokens: 300,
  scalingMinTokens: 4000,
} as const;

export function classifySizeTier(tokens: number | null): SizeTier | "unknown" {
  if (tokens === null || Number.isNaN(tokens)) return "unknown";
  if (tokens < TIER_THRESHOLDS.probeMaxTokens) return "probe";
  if (tokens >= TIER_THRESHOLDS.scalingMinTokens) return "scaling";
  return "signal";
}

/**
 * Group observations by fixture and compute pairwise deltas. Only includes
 * pairs where both providers reported a count; missing counts produce a null
 * delta rather than throwing, since partial data is common in this harness.
 */
export function summarizeTokenDeltas(
  observations: TokenCountObservation[]
): ObservationSummary[] {
  const groupedByFixture = new Map<string, TokenCountObservation[]>();
  for (const observation of observations) {
    const existing = groupedByFixture.get(observation.fixtureName) ?? [];
    existing.push(observation);
    groupedByFixture.set(observation.fixtureName, existing);
  }

  const summaries: ObservationSummary[] = [];
  for (const [fixtureName, rows] of groupedByFixture) {
    const byProvider: Record<TokenCountProvider, number | null> = {
      "anthropic-count-tokens": null,
      "openai-input-tokens": null,
      "local-tiktoken": null,
    };
    for (const row of rows) {
      byProvider[row.provider] = row.inputTokenCount;
    }
    const providers: TokenCountProvider[] = [
      "anthropic-count-tokens",
      "openai-input-tokens",
      "local-tiktoken",
    ];
    const deltas: ObservationSummary["deltas"] = [];
    for (let i = 0; i < providers.length; i++) {
      for (let j = i + 1; j < providers.length; j++) {
        const a = providers[i];
        const b = providers[j];
        const av = byProvider[a];
        const bv = byProvider[b];
        deltas.push({
          a,
          b,
          delta: av === null || bv === null ? null : bv - av,
        });
      }
    }
    summaries.push({ fixtureName, byProvider, deltas });
  }
  summaries.sort((x, y) => x.fixtureName.localeCompare(y.fixtureName));
  return summaries;
}

export class ObservationStore {
  private readonly rows: TokenCountObservation[] = [];

  add(observation: TokenCountObservation): void {
    this.rows.push({
      ...observation,
      sizeTier:
        observation.sizeTier ??
        (classifySizeTier(observation.inputTokenCount) as SizeTier | undefined),
    });
  }

  filter(predicate: (row: TokenCountObservation) => boolean): TokenCountObservation[] {
    return this.rows.filter(predicate);
  }

  byTier(tier: SizeTier): TokenCountObservation[] {
    return this.filter((row) => row.sizeTier === tier);
  }

  averageInputTokens(provider: TokenCountProvider): number | null {
    const counts = this.rows
      .filter((row) => row.provider === provider && row.inputTokenCount !== null)
      .map((row) => row.inputTokenCount as number);
    if (counts.length === 0) return null;
    const total = counts.reduce((acc, n) => acc + n, 0);
    return total / counts.length;
  }
}

export async function fetchAndStore(
  store: ObservationStore,
  fetcher: (provider: TokenCountProvider) => Promise<number | null>,
  fixtureName: string,
  model: string,
  byteLengthUtf8: number,
  characterLength: number
): Promise<void> {
  const providers: TokenCountProvider[] = [
    "anthropic-count-tokens",
    "openai-input-tokens",
    "local-tiktoken",
  ];
  for (const provider of providers) {
    try {
      const inputTokenCount = await fetcher(provider);
      store.add({
        fixtureName,
        provider,
        model,
        inputTokenCount,
        byteLengthUtf8,
        characterLength,
        exactnessNote:
          provider === "openai-input-tokens"
            ? "exact provider count for the Responses API"
            : provider === "anthropic-count-tokens"
            ? "provider count_tokens estimate; may differ slightly from create-message usage"
            : "local tokenizer; secondary evidence only",
      });
    } catch (error) {
      const note = error instanceof Error ? error.message : String(error);
      store.add({
        fixtureName,
        provider,
        model,
        inputTokenCount: null,
        byteLengthUtf8,
        characterLength,
        exactnessNote: `unavailable: ${note}`,
      });
    }
  }
}
