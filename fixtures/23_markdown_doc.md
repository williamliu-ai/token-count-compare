# Token Count Compare — Operator's Guide

> A short, opinionated guide for operators who want to reproduce, extend, or maintain the token-count comparison harness.

## Audience

This document is for operators, not researchers. If you are running this in a CI job, on a laptop before a meeting, or on a small VM that wakes up once a week to publish a snapshot, this is the right document. If you are looking for a methodology paper, that lives elsewhere.

## TL;DR

- The free path is `verify_token_counts.py`. It calls only count endpoints. It is the recommended workflow.
- The paid path is `compare_tokens.py`. It runs actual inference. Use it only as a sanity check.
- All fixtures are in `fixtures/`. Add new ones; do not delete the existing ones, since several of them are referenced from the README.

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.11+ | The harness uses PEP 695 syntax in some fixtures, but the harness scripts themselves are 3.10+ compatible. |
| `anthropic` SDK | >=0.49 | Required for `messages.count_tokens`. |
| `openai` SDK | >=1.65 | Required for `responses.input_tokens.count`. |
| `tiktoken` | >=0.7 | Optional; used as a secondary local sanity check. |

## Quick start

```bash
git clone https://github.com/<owner>/token-count-compare.git
cd token-count-compare
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
python3 verify_token_counts.py
```

That is the entire happy path.

## Configuration

The harness reads only this folder's `.env` file. It does not fall back to ambient environment variables. The intent is that no credential outside this folder can leak into the run.

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
CLAUDE_MODEL=claude-opus-4-7
OPENAI_MODEL=gpt-5.5
```

If a key is missing, the run will produce per-provider error rows for that provider but will still produce results for the other one. This is intentional: a partial run is more useful than a hard failure.

## What the output looks like

The verification report is a JSON document with two top-level surfaces per case:

1. `controlled_text` — counts on the fixture text alone. **This is the cross-model comparison surface.**
2. `full_benchmark_prompt` — counts on the fixture wrapped in the ingest-only prompt. Only present when validating an existing benchmark run.

A small printed table summarizes the controlled-text counts:

```text
case                                      claude_text  openai_text  openai_tiktoken
--------------------------------------------------------------------------------
01_plain_prose.txt                                1090         1058             1064
02_code.py                                        1640         1582             1611
...
```

## Fixture tiers

| Tier | Token range | Purpose |
| --- | --- | --- |
| **probe** | < 300 | Edge-case sensitivity. Percentage deltas are unstable; treat as illustrative. |
| **signal** | 300 – 4,000 | Where conclusions come from. Stable percentage deltas. Most fixtures live here. |
| **scaling** | > 4,000 | Confirms whether deltas grow, shrink, or stay constant with length. One per category is usually enough. |

## Adding a fixture

1. Drop the file into `fixtures/`. Use a descriptive prefix and a sensible extension. The harness only picks up files whose extensions are in `FIXTURE_EXTENSIONS` (see `compare_tokens.py`).
2. Re-run the verification script. Your fixture will appear in the report automatically.
3. If the new fixture stresses a content category that was not previously covered, add a one-line entry to the **Fixtures** section of the README.

## Common questions

**Does the verification call cost anything?**
No. Both providers document their count endpoints as free of charge. You can run `verify_token_counts.py` as often as you like.

**Why is the benchmark script kept around at all?**
Because the count endpoints are documented as estimates by at least one provider. The benchmark script measures actual billed input tokens, which is the only way to confirm the count endpoint matches reality. You do not need it for the article-grade comparison; you do need it for an audit-grade comparison.

**What happens if a tokenizer changes?**
You will see a delta on a fixture that was previously stable. The harness will not alert you; that is the operator's responsibility. The right cadence is weekly for a publishing project, monthly for an internal one.

## See also

- The [`README.md`](./README.md) at the project root for an overview and the canonical fixture list.
- Each provider's count-endpoint documentation for authoritative behavior.
- A note on size tiers in the README, which explains how to interpret the printed delta table.
