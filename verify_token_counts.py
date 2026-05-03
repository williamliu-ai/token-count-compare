#!/usr/bin/env python3
"""Verify token-count methods for controlled text fixtures.

Primary evidence:
- Anthropic: messages.count_tokens for Claude Opus 4.7.
- OpenAI: responses.input_tokens.count for GPT-5.5.

Secondary evidence:
- OpenAI: local tiktoken count for raw text, when the model encoding is known.
- Benchmark JSON: optional comparison against actual API usage.input_tokens from a run.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from compare_tokens import (
    FIXTURE_EXTENSIONS,
    PROJECT_ENV_PATH,
    build_prompt,
    classify_size_tier,
    load_project_env,
)


@dataclass
class Baseline:
    kind: str
    tokenizer_or_api: str
    tokens: int | None
    exactness: str
    error: str | None = None


def anthropic_count_tokens(model: str, text: str, api_key: str | None) -> Baseline:
    try:
        import anthropic

        if not api_key:
            return Baseline("provider_count_tokens", "anthropic.messages.count_tokens", None, "unavailable", f"ANTHROPIC_API_KEY missing in {PROJECT_ENV_PATH}")
        client = anthropic.Anthropic(api_key=api_key)
        result = client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}],
        )
        return Baseline(
            "provider_count_tokens",
            "anthropic.messages.count_tokens",
            getattr(result, "input_tokens", None),
            "official provider-side count for the same Messages request shape; Anthropic docs call counts estimates that can differ slightly from create-message usage",
        )
    except Exception as exc:
        return Baseline("provider_count_tokens", "anthropic.messages.count_tokens", None, "unavailable", str(exc))


def openai_input_tokens_count(model: str, text: str, api_key: str | None) -> Baseline:
    try:
        from openai import OpenAI

        if not api_key:
            return Baseline("provider_count_tokens", "openai.responses.input_tokens.count", None, "unavailable", f"OPENAI_API_KEY missing in {PROJECT_ENV_PATH}")
        client = OpenAI(api_key=api_key)
        result = client.responses.input_tokens.count(model=model, input=text)
        return Baseline(
            "provider_count_tokens",
            "openai.responses.input_tokens.count",
            getattr(result, "input_tokens", None),
            "official provider-side count; OpenAI docs say it accepts Responses API input format and returns the exact count the model will receive",
        )
    except Exception as exc:
        return Baseline("provider_count_tokens", "openai.responses.input_tokens.count", None, "unavailable", str(exc))


def openai_tiktoken_count(model: str, text: str) -> Baseline:
    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
            exactness = "local tokenizer selected by model name; useful exact local baseline if tiktoken knows this model"
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
            exactness = "fallback o200k_base; useful plain-text evidence, not an exact GPT-5.5 guarantee"
        return Baseline("local_tokenizer", encoding.name, len(encoding.encode(text)), exactness)
    except Exception as exc:
        return Baseline("local_tokenizer", "tiktoken", None, "unavailable", str(exc))


def load_report(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def reported_input(report: dict[str, Any] | None, case_name: str, provider: str) -> int | None:
    if not report:
        return None
    for case in report.get("cases", []):
        if case.get("case") == case_name:
            return case.get("results", {}).get(provider, {}).get("input_tokens")
    return None


def compare(observed: int | None, baseline: int | None, tolerance: int) -> dict[str, Any]:
    if observed is None or baseline is None:
        return {"status": "skip", "delta": None, "within_tolerance": None}
    delta = observed - baseline
    return {
        "status": "pass" if abs(delta) <= tolerance else "fail",
        "delta": delta,
        "within_tolerance": abs(delta) <= tolerance,
    }


def provider_counts_for_text(claude_model: str, openai_model: str, text: str, anthropic_api_key: str | None, openai_api_key: str | None) -> dict[str, Any]:
    claude = anthropic_count_tokens(claude_model, text, anthropic_api_key)
    openai = openai_input_tokens_count(openai_model, text, openai_api_key)
    tiktoken = openai_tiktoken_count(openai_model, text)
    return {
        "claude": asdict(claude),
        "openai": asdict(openai),
        "openai_tiktoken_secondary": asdict(tiktoken),
        "openai_provider_vs_tiktoken": compare(openai.tokens, tiktoken.tokens, 0),
    }


def verify(
    fixtures_dir: Path,
    report_path: Path | None,
    out: Path,
    tolerance: int,
    counts_only: bool = False,
) -> dict[str, Any]:
    env = load_project_env()
    report = load_report(report_path)
    claude_model = (report or {}).get("models", {}).get("claude") or env.get("CLAUDE_MODEL", "claude-opus-4-7")
    openai_model = (report or {}).get("models", {}).get("openai") or env.get("OPENAI_MODEL", "gpt-5.5")
    anthropic_api_key = env.get("ANTHROPIC_API_KEY")
    openai_api_key = env.get("OPENAI_API_KEY")
    # The full-prompt provider calls are only meaningful when we are validating
    # a previous benchmark run. Without a report, or when the operator passes
    # --counts-only, skip them so the workflow stays purely count-only.
    skip_full_prompt = counts_only or report is None

    cases = []
    for fixture in sorted(p for p in fixtures_dir.iterdir() if p.is_file() and p.suffix in FIXTURE_EXTENSIONS):
        text = fixture.read_text(encoding="utf-8")
        full_prompt = build_prompt(text)
        text_counts = provider_counts_for_text(claude_model, openai_model, text, anthropic_api_key, openai_api_key)
        prompt_counts = (
            None
            if skip_full_prompt
            else provider_counts_for_text(
                claude_model, openai_model, full_prompt, anthropic_api_key, openai_api_key
            )
        )
        claude_reported = reported_input(report, fixture.name, "claude")
        openai_reported = reported_input(report, fixture.name, "openai")
        size_tier = classify_size_tier(text_counts["claude"]["tokens"])
        controlled_block = {
            "characters": len(text),
            "bytes_utf8": len(text.encode("utf-8")),
            "counts": text_counts,
            "note": "This is the cleanest cross-model comparison surface: the fixture text only, no benchmark prompt and no generated output.",
        }
        full_prompt_block = (
            None
            if skip_full_prompt
            else {
                "characters": len(full_prompt),
                "bytes_utf8": len(full_prompt.encode("utf-8")),
                "counts": prompt_counts,
                "note": "Use this only to validate a benchmark run that sent the ingest-only prompt. It intentionally includes prompt/template overhead.",
            }
        )
        usage_check = (
            None
            if skip_full_prompt
            else {
                "claude_reported_input_tokens": claude_reported,
                "claude_vs_full_prompt_count_tokens": compare(
                    claude_reported, prompt_counts["claude"]["tokens"], tolerance
                ),
                "openai_reported_input_tokens": openai_reported,
                "openai_vs_full_prompt_input_tokens_count": compare(
                    openai_reported, prompt_counts["openai"]["tokens"], tolerance
                ),
            }
        )
        cases.append(
            {
                "case": fixture.name,
                "size_tier": size_tier,
                "controlled_text": controlled_block,
                "full_benchmark_prompt": full_prompt_block,
                "reported_usage_check_for_existing_benchmark_json": usage_check,
            }
        )

    checks: list[str] = []
    for case in cases:
        usage = case.get("reported_usage_check_for_existing_benchmark_json")
        if not usage:
            continue
        checks.extend(
            [
                usage["claude_vs_full_prompt_count_tokens"]["status"],
                usage["openai_vs_full_prompt_input_tokens_count"]["status"],
            ]
        )
    result = {
        "models": {"claude": claude_model, "openai": openai_model},
        "report_compared": str(report_path) if report_path else None,
        "tolerance_tokens": tolerance,
        "summary": {"pass": checks.count("pass"), "fail": checks.count("fail"), "skip": checks.count("skip")},
        "recommendation": {
            "claude_opus_4_7": "Use Anthropic's official /v1/messages/count_tokens (SDK: client.messages.count_tokens) as the provider-side baseline for controlled text. It supports active models including claude-opus-4-7.",
            "gpt_5_5": "Use OpenAI's official Responses input token count endpoint (SDK: client.responses.input_tokens.count) as the provider-side baseline. Use actual Responses usage.input_tokens after a run as a second check; use tiktoken only as a local/secondary plain-text sanity check.",
            "cross_model_comparison": "For the article, compare provider count-token results on the raw fixture text only. Separately compare full prompt counts only when validating the benchmark script's actual request overhead.",
        },
        "validation_scope": {
            "exact_token_count": "Provider count endpoints are the best authoritative accounting surfaces. OpenAI documents exact count for Responses input; Anthropic documents count_tokens but notes counts are estimates and may differ slightly from create-message usage.",
            "input_token_accounting": "Actual API usage.input_tokens remains the final billing/usage observation after an inference request, but it includes the exact request payload and any provider request formatting.",
            "prompt_output_noise": "Controlled-text counts use fixture text only and make no generation request. Full-prompt checks are reported separately so prompt template overhead is not mistaken for text-tokenization behavior.",
        },
        "cases": cases,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    if summary["pass"] == 0 and summary["fail"] == 0 and summary["skip"] == 0:
        print("Counts-only run: no benchmark report supplied, no pass/fail checks performed.")
    else:
        print(f"Verification summary for benchmark usage checks: {summary} tolerance=±{result['tolerance_tokens']} token(s)")
    print(f"{'case':40} {'tier':9} {'claude_text':>11} {'openai_text':>12} {'openai_tiktoken':>16}")
    print("-" * 96)
    has_probe = False
    for case in result["cases"]:
        counts = case["controlled_text"]["counts"]
        tier = case.get("size_tier", "unknown")
        if tier == "probe":
            has_probe = True
        print(
            f"{case['case'][:40]:40} "
            f"{tier:9} "
            f"{str(counts['claude']['tokens']):>11} "
            f"{str(counts['openai']['tokens']):>12} "
            f"{str(counts['openai_tiktoken_secondary']['tokens']):>16}"
        )
    if has_probe:
        print()
        print("Note: probe-tier fixtures are too small for stable percentage deltas. "
              "Use them as illustrative edge-case probes, not as measurements.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    parser.add_argument("--report", type=Path, default=Path("results/latest.json"), help="optional benchmark JSON to compare against full-prompt provider counts")
    parser.add_argument("--out", type=Path, default=Path("results/verification.json"))
    parser.add_argument("--tolerance", type=int, default=0, help="allowed absolute token delta for benchmark usage pass/fail")
    parser.add_argument(
        "--counts-only",
        action="store_true",
        help=(
            "Skip the full-prompt provider calls. The default workflow already "
            "skips them when no --report is supplied; pass this flag to make "
            "the count-only intent explicit even when a report exists."
        ),
    )
    args = parser.parse_args()
    report_path = args.report if args.report.exists() else None
    result = verify(args.fixtures, report_path, args.out, args.tolerance, args.counts_only)
    print_summary(result)
    print(f"\nJSON verification report: {args.out}")
    return 1 if result["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
