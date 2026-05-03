#!/usr/bin/env python3
"""Scaling-tier code fixture.

This is a deliberately long, single-file Python module so that the
token-count harness has a non-trivial code workload to count. The code
is plausible but is not intended to be wired into a real system. It
covers a mix of common patterns: dataclasses, generators, async I/O,
exception hierarchies, decorators, contextmanagers, simple parsing,
and a small CLI.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import json
import logging
import math
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Generic, Optional, Protocol, TypeVar

T = TypeVar("T")
U = TypeVar("U")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HarnessError(Exception):
    """Base error for anything raised by this fixture."""


class ConfigurationError(HarnessError):
    """Raised when an input is malformed or a required setting is missing."""


class ProviderError(HarnessError):
    """Raised when an upstream provider call fails in a non-retriable way."""


class RateLimitError(ProviderError):
    """Raised when a provider has signalled a rate limit."""

    def __init__(self, message: str, retry_after_seconds: float = 1.0) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class SizeTier(Enum):
    PROBE = auto()
    SIGNAL = auto()
    SCALING = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class FixtureMeta:
    name: str
    path: Path
    bytes_utf8: int
    characters: int
    extension: str

    @classmethod
    def from_path(cls, path: Path) -> "FixtureMeta":
        text = path.read_text(encoding="utf-8")
        return cls(
            name=path.name,
            path=path,
            bytes_utf8=len(text.encode("utf-8")),
            characters=len(text),
            extension=path.suffix.lstrip("."),
        )


@dataclass
class CountResult:
    fixture: FixtureMeta
    provider: str
    model: str
    input_tokens: Optional[int]
    error: Optional[str] = None

    @property
    def successful(self) -> bool:
        return self.input_tokens is not None and self.error is None


@dataclass
class CaseSummary:
    fixture: FixtureMeta
    counts_by_provider: dict[str, Optional[int]] = field(default_factory=dict)
    deltas: dict[str, Optional[int]] = field(default_factory=dict)
    size_tier: SizeTier = SizeTier.UNKNOWN


# ---------------------------------------------------------------------------
# Provider protocol and concrete implementations
# ---------------------------------------------------------------------------


class CountProvider(Protocol):
    name: str
    model: str

    async def count(self, text: str) -> int: ...


class StaticProvider:
    """Deterministic in-memory provider used for tests and dry runs."""

    def __init__(
        self,
        name: str,
        model: str,
        ratio_chars_per_token: float = 4.0,
        bias_tokens: int = 0,
    ) -> None:
        self.name = name
        self.model = model
        self.ratio_chars_per_token = ratio_chars_per_token
        self.bias_tokens = bias_tokens

    async def count(self, text: str) -> int:
        await asyncio.sleep(0)
        if self.ratio_chars_per_token <= 0:
            raise ConfigurationError("ratio_chars_per_token must be positive")
        return int(round(len(text) / self.ratio_chars_per_token)) + self.bias_tokens


class FlakyProvider:
    """Wraps another provider and injects deterministic flakiness for testing."""

    def __init__(self, inner: CountProvider, fail_every_n: int = 3) -> None:
        self.name = f"flaky:{inner.name}"
        self.model = inner.model
        self._inner = inner
        self._call_index = 0
        self._fail_every_n = fail_every_n

    async def count(self, text: str) -> int:
        self._call_index += 1
        if self._call_index % self._fail_every_n == 0:
            raise RateLimitError("synthetic rate limit", retry_after_seconds=0.05)
        return await self._inner.count(text)


# ---------------------------------------------------------------------------
# Retry and backoff
# ---------------------------------------------------------------------------


async def with_retries(
    op: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    initial_backoff_seconds: float = 0.1,
    backoff_multiplier: float = 2.0,
    retriable: tuple[type[BaseException], ...] = (RateLimitError,),
) -> T:
    backoff = initial_backoff_seconds
    last_error: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await op()
        except retriable as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            wait_for = getattr(exc, "retry_after_seconds", backoff)
            await asyncio.sleep(max(wait_for, 0))
            backoff *= backoff_multiplier
    if last_error is not None:
        raise last_error
    raise HarnessError("with_retries: no attempts were made")


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------


_DEFAULT_FIXTURE_EXTENSIONS = frozenset(
    {
        "txt", "py", "js", "ts", "java", "cs", "cpp", "go", "rs", "swift",
        "php", "md", "json", "yaml", "yml", "sql", "patch", "log", "html", "csv",
    }
)


def discover_fixtures(
    root: Path,
    allowed_extensions: Iterable[str] = _DEFAULT_FIXTURE_EXTENSIONS,
) -> list[FixtureMeta]:
    if not root.exists():
        raise ConfigurationError(f"fixtures directory not found: {root}")
    if not root.is_dir():
        raise ConfigurationError(f"fixtures path is not a directory: {root}")
    allowed = {ext.lower().lstrip(".") for ext in allowed_extensions}
    out: list[FixtureMeta] = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext not in allowed:
            continue
        out.append(FixtureMeta.from_path(path))
    return out


# ---------------------------------------------------------------------------
# Counting orchestration
# ---------------------------------------------------------------------------


async def count_one(
    provider: CountProvider, fixture: FixtureMeta, *, max_attempts: int = 3
) -> CountResult:
    text = fixture.path.read_text(encoding="utf-8")

    async def _call() -> int:
        return await provider.count(text)

    try:
        tokens = await with_retries(_call, max_attempts=max_attempts)
        return CountResult(
            fixture=fixture, provider=provider.name, model=provider.model,
            input_tokens=tokens,
        )
    except RateLimitError as exc:
        return CountResult(
            fixture=fixture, provider=provider.name, model=provider.model,
            input_tokens=None, error=f"rate_limited: {exc}",
        )
    except ProviderError as exc:
        return CountResult(
            fixture=fixture, provider=provider.name, model=provider.model,
            input_tokens=None, error=str(exc),
        )
    except Exception as exc:
        return CountResult(
            fixture=fixture, provider=provider.name, model=provider.model,
            input_tokens=None, error=f"unexpected:{type(exc).__name__}:{exc}",
        )


async def count_all(
    providers: list[CountProvider],
    fixtures: list[FixtureMeta],
    *,
    concurrency: int = 4,
) -> list[CountResult]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(provider: CountProvider, fixture: FixtureMeta) -> CountResult:
        async with semaphore:
            return await count_one(provider, fixture)

    tasks = [
        asyncio.create_task(_bounded(p, f))
        for p in providers
        for f in fixtures
    ]
    return list(await asyncio.gather(*tasks))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


_PROBE_MAX_TOKENS = 300
_SCALING_MIN_TOKENS = 4_000


def classify_size_tier(tokens: Optional[int]) -> SizeTier:
    if tokens is None:
        return SizeTier.UNKNOWN
    if tokens < _PROBE_MAX_TOKENS:
        return SizeTier.PROBE
    if tokens >= _SCALING_MIN_TOKENS:
        return SizeTier.SCALING
    return SizeTier.SIGNAL


def summarize(results: list[CountResult]) -> list[CaseSummary]:
    by_fixture: dict[str, list[CountResult]] = defaultdict(list)
    for r in results:
        by_fixture[r.fixture.name].append(r)

    out: list[CaseSummary] = []
    for fixture_name in sorted(by_fixture):
        rows = by_fixture[fixture_name]
        case = CaseSummary(fixture=rows[0].fixture)
        for row in rows:
            case.counts_by_provider[row.provider] = row.input_tokens
        provider_names = sorted(case.counts_by_provider)
        for i, a in enumerate(provider_names):
            for b in provider_names[i + 1 :]:
                av, bv = case.counts_by_provider[a], case.counts_by_provider[b]
                case.deltas[f"{a}__minus__{b}"] = (
                    None if av is None or bv is None else av - bv
                )
        max_tokens = max((v or 0) for v in case.counts_by_provider.values()) or None
        case.size_tier = classify_size_tier(max_tokens)
        out.append(case)
    return out


def print_table(summaries: list[CaseSummary]) -> None:
    print(f"{'case':40} {'tier':9} {'providers':20} {'min_tokens':>10} {'max_tokens':>10}")
    print("-" * 96)
    for case in summaries:
        values = [v for v in case.counts_by_provider.values() if v is not None]
        if values:
            mn, mx = min(values), max(values)
        else:
            mn = mx = None
        print(
            f"{case.fixture.name[:40]:40} "
            f"{case.size_tier.name.lower():9} "
            f"{','.join(sorted(case.counts_by_provider))[:20]:20} "
            f"{str(mn):>10} {str(mx):>10}"
        )


def to_json_report(summaries: list[CaseSummary]) -> dict[str, Any]:
    cases = []
    for case in summaries:
        cases.append(
            {
                "case": case.fixture.name,
                "size_tier": case.size_tier.name.lower(),
                "characters": case.fixture.characters,
                "bytes_utf8": case.fixture.bytes_utf8,
                "counts_by_provider": case.counts_by_provider,
                "deltas": case.deltas,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "cases": cases,
    }


# ---------------------------------------------------------------------------
# Optional CSV / NDJSON outputs
# ---------------------------------------------------------------------------


def write_csv(summaries: list[CaseSummary], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        provider_names = sorted({p for s in summaries for p in s.counts_by_provider})
        writer = csv.writer(fh)
        writer.writerow(["case", "size_tier", "characters", "bytes_utf8", *provider_names])
        for case in summaries:
            writer.writerow(
                [
                    case.fixture.name,
                    case.size_tier.name.lower(),
                    case.fixture.characters,
                    case.fixture.bytes_utf8,
                    *[case.counts_by_provider.get(name, "") for name in provider_names],
                ]
            )


def write_ndjson(summaries: list[CaseSummary], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for case in summaries:
            fh.write(
                json.dumps(
                    {
                        "case": case.fixture.name,
                        "size_tier": case.size_tier.name.lower(),
                        "counts_by_provider": case.counts_by_provider,
                        "deltas": case.deltas,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# Lightweight statistical helpers
# ---------------------------------------------------------------------------


def safe_pct_delta(a: Optional[int], b: Optional[int]) -> Optional[float]:
    if a in (None, 0) or b is None:
        return None
    return round(((b - a) / a) * 100.0, 2)


def per_category_summary(
    summaries: list[CaseSummary],
    classifier: Callable[[FixtureMeta], str],
) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for case in summaries:
        category = classifier(case.fixture)
        values = [v for v in case.counts_by_provider.values() if v is not None]
        if not values:
            continue
        spread = (max(values) - min(values)) / max(values)
        grouped[category].append(spread)
    out: dict[str, dict[str, float]] = {}
    for category, spreads in grouped.items():
        if not spreads:
            continue
        out[category] = {
            "count": len(spreads),
            "spread_mean": round(statistics.fmean(spreads), 4),
            "spread_p95": round(_percentile(spreads, 95), 4),
        }
    return out


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return float(values[0])
    sorted_values = sorted(values)
    rank = (q / 100.0) * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = rank - lower
    return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaling-tier code fixture demo.")
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    parser.add_argument("--out", type=Path, default=Path("results/scaling-fixture-demo.json"))
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--ndjson-out", type=Path)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--include-flaky", action="store_true")
    return parser.parse_args(argv)


async def amain(args: argparse.Namespace) -> int:
    providers: list[CountProvider] = [
        StaticProvider(name="static-3.5", model="static", ratio_chars_per_token=3.5),
        StaticProvider(name="static-4.0", model="static", ratio_chars_per_token=4.0),
        StaticProvider(name="static-4.5", model="static", ratio_chars_per_token=4.5),
    ]
    if args.include_flaky:
        providers.append(FlakyProvider(StaticProvider("baseline", "static", 4.0)))
    fixtures = discover_fixtures(args.fixtures)
    log.info("discovered %d fixtures", len(fixtures))
    results = await count_all(providers, fixtures, concurrency=args.concurrency)
    summaries = summarize(results)
    print_table(summaries)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(to_json_report(summaries), indent=2), encoding="utf-8")
    if args.csv_out:
        write_csv(summaries, args.csv_out)
    if args.ndjson_out:
        write_ndjson(summaries, args.ndjson_out)
    failures = [r for r in results if not r.successful]
    return 1 if failures else 0


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    args = parse_args(argv)
    return asyncio.run(amain(args))


# ---------------------------------------------------------------------------
# Embedded smoke tests, runnable with `python -m fixture_module --self-test`.
# ---------------------------------------------------------------------------


def _self_test() -> None:
    assert classify_size_tier(None) is SizeTier.UNKNOWN
    assert classify_size_tier(0) is SizeTier.PROBE
    assert classify_size_tier(299) is SizeTier.PROBE
    assert classify_size_tier(300) is SizeTier.SIGNAL
    assert classify_size_tier(3_999) is SizeTier.SIGNAL
    assert classify_size_tier(4_000) is SizeTier.SCALING
    assert safe_pct_delta(None, 1) is None
    assert safe_pct_delta(0, 1) is None
    assert safe_pct_delta(100, 110) == 10.0
    assert safe_pct_delta(100, 90) == -10.0
    assert _percentile([1, 2, 3, 4, 5], 50) == 3.0
    assert _percentile([1, 2, 3, 4, 5], 100) == 5.0
    print("self-test ok")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--self-test":
        _self_test()
    else:
        sys.exit(main())
