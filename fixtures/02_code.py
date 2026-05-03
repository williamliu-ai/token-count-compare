#!/usr/bin/env python3
"""Small everyday Python module fixture: text utilities and a Document type.

This file is intentionally ordinary. It uses common patterns a working
engineer would write or read on any given day: string handling, light
Unicode work, a dataclass, a generator, and a small CLI demo. It is not
trying to be clever; the goal is realistic surface area for a tokenizer.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Optional

_PUNCT_TO_STRIP = "_.,:;!?()[]{}'\"‘’“”"
_WHITESPACE_RE = re.compile(r"\s+")
_HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_]*)")


def normalize_title(title: str) -> str:
    """Convert a human title into a stable lowercase slug."""
    return "-".join(
        token.strip(_PUNCT_TO_STRIP).lower()
        for token in title.split()
        if token.strip()
    )


def slugify(text: str, max_length: int = 80) -> str:
    """A more thorough slug: NFKD-folds accents, drops non-ASCII, then normalizes."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(
        ch for ch in folded if not unicodedata.combining(ch) and ord(ch) < 128
    )
    cleaned = _WHITESPACE_RE.sub(" ", ascii_only).strip()
    slug = normalize_title(cleaned)
    return slug[:max_length].rstrip("-")


def extract_hashtags(text: str) -> list[str]:
    """Pull out hashtag-like tokens, lowercased and deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _HASHTAG_RE.finditer(text):
        tag = match.group(1).lower()
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


@dataclass
class Document:
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    author: Optional[str] = None

    @property
    def slug(self) -> str:
        return slugify(self.title)

    def excerpt(self, max_chars: int = 280) -> str:
        if len(self.body) <= max_chars:
            return self.body
        cutoff = self.body.rfind(" ", 0, max_chars)
        if cutoff <= 0:
            cutoff = max_chars
        return self.body[:cutoff].rstrip() + "..."

    def with_inferred_tags(self) -> "Document":
        """Return a copy with hashtags pulled in from the body."""
        merged = list(self.tags)
        for tag in extract_hashtags(self.body):
            if tag not in merged:
                merged.append(tag)
        return Document(self.title, self.body, merged, self.author)


def deduplicate(items: Iterable[str]) -> list[str]:
    """Return items in original order, removing case-insensitive duplicates."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def find_first(
    predicate, iterable: Iterable[str], default: Optional[str] = None
) -> Optional[str]:
    """Return the first item matching predicate, or default."""
    for item in iterable:
        if predicate(item):
            return item
    return default


def chunk_paragraphs(text: str, paragraphs_per_chunk: int = 3) -> Iterator[str]:
    """Yield text in chunks of N paragraphs, preserving order."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for i in range(0, len(paragraphs), paragraphs_per_chunk):
        yield "\n\n".join(paragraphs[i : i + paragraphs_per_chunk])


def word_count(text: str) -> int:
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def estimate_reading_time(text: str, words_per_minute: int = 220) -> float:
    return round(word_count(text) / words_per_minute, 2)


if __name__ == "__main__":
    samples = [
        "Token Counts: Claude vs GPT, Round #1!",
        "  Hello, World!  ",
        "Cafe Resume Naivete",
        "12 Angry Men (1957)",
    ]
    for raw in samples:
        print(f"{raw!r:48} -> {slugify(raw)!r}")

    doc = Document(
        title="A Practical Note on Tokenization",
        body=(
            "Tokenization is the quiet plumbing of every modern language model. "
            "Most users never think about it, but it shapes cost, latency, and "
            "the boundaries of what fits in a request. This module exists to "
            "make small text-handling utilities easy to reason about, and to "
            "give a tokenization benchmark something concrete to chew on. "
            "We use #tokenization #benchmarks #python tags only as a small demo."
        ),
        tags=["fixtures"],
        author="example",
    )
    enriched = doc.with_inferred_tags()
    print(enriched.slug)
    print(enriched.tags)
    print(enriched.excerpt(max_chars=140))
    print(deduplicate(["alpha", "Alpha", "beta", "  beta  ", "gamma", ""]))
    print(estimate_reading_time(doc.body))
    print(list(chunk_paragraphs("alpha\n\nbeta\n\ngamma\n\ndelta\n\nepsilon", 2)))
