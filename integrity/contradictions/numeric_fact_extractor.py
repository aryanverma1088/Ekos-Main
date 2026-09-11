"""
Extracts numeric facts (a value, a unit, and a short context key) from text.
This is the core signal for the fallback contradiction detector: it looks
for the SAME concept (unit + surrounding phrase) stated with DIFFERENT
values across chunks from different documents.

This deliberately does not attempt to catch qualitative/non-numeric
contradictions (e.g. differing access-approval rules that don't hinge on a
number) -- see integrity/FINDINGS.md for why, and what a real system would
need (semantic/NLI reasoning via an LLM, per the original architecture
plan) to close that gap.
"""
import re

UNIT_PATTERNS = [
    ("days", re.compile(r"\b(\d+)\s*days?\b")),
    ("weeks", re.compile(r"\b(\d+)\s*weeks?\b")),
    ("months", re.compile(r"\b(\d+)\s*months?\b")),
    ("years", re.compile(r"\b(\d+)\s*years?\b")),
    ("dollars", re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*)")),
    ("percent", re.compile(r"\b(\d+)\s*%")),
]

CONTEXT_WINDOW_WORDS = 4
CONTEXT_STOPWORDS = {"a", "an", "the", "is", "are", "of", "in", "on", "at", "to", "for"}


def _context_key(text: str, match_start: int, unit: str) -> str:
    """Takes the few words immediately before the number as a normalized
    'concept key'. Two facts with the same unit + context key are treated
    as describing the same concept (candidates for contradiction if their
    values differ)."""
    before = text[:match_start]
    words = re.findall(r"[a-z]+", before.lower())
    words = [w for w in words if w not in CONTEXT_STOPWORDS]
    context = " ".join(words[-CONTEXT_WINDOW_WORDS:])
    return f"{unit}::{context}"


def extract_numeric_facts(text: str) -> list[dict]:
    """Returns [{value, unit, context_key, raw_match}, ...]."""
    facts = []
    text_lower = text.lower()

    for unit, pattern in UNIT_PATTERNS:
        for m in pattern.finditer(text_lower):
            raw_value = m.group(1).replace(",", "")
            value = int(raw_value)
            context_key = _context_key(text_lower, m.start(), unit)
            facts.append({
                "value": value,
                "unit": unit,
                "context_key": context_key,
                "raw_match": m.group(0),
            })

    return facts
