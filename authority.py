"""
Enterprise authority model — single source of truth for the 6-level
document authority hierarchy used across ingestion, integrity resolution,
and every API response that surfaces authority_level.

This existed as bare integers (1-6) before, correct but illegible: the
frontend only ever rendered a dot ladder and "L1", never what L1 *means*.
A reviewer shouldn't have to reverse-engineer the hierarchy from a filled
circle count. This module is imported everywhere authority is displayed or
reasoned about, so the mapping only needs to be correct in one place.
"""

AUTHORITY_LEVELS: dict[int, dict[str, str]] = {
    1: {
        "label": "Official Policy",
        "description": "Formally approved, board- or executive-level policy. Binding.",
    },
    2: {
        "label": "Approved SOP",
        "description": "Standard operating procedure, signed off by the owning department.",
    },
    3: {
        "label": "Official Documentation",
        "description": "Reference documentation maintained by a team (handbooks, runbooks).",
    },
    4: {
        "label": "Project Documentation",
        "description": "Scoped to a specific project or initiative; not company-wide policy.",
    },
    5: {
        "label": "Meeting Notes",
        "description": "Informal record of a discussion or decision, not independently authoritative.",
    },
    6: {
        "label": "Informal Notes",
        "description": "Personal or unreviewed notes. Lowest authority; verify before relying on it.",
    },
}

DEFAULT_LEVEL = 3
MIN_LEVEL = 1
MAX_LEVEL = 6


def authority_label(level: int) -> str:
    entry = AUTHORITY_LEVELS.get(level)
    return entry["label"] if entry else f"Level {level}"


def authority_description(level: int) -> str:
    entry = AUTHORITY_LEVELS.get(level)
    return entry["description"] if entry else "Unrecognized authority level."


def higher_authority(level_a: int, level_b: int) -> int:
    """Returns whichever level is MORE authoritative. Lower integer = higher
    authority (1 = Official Policy outranks 6 = Informal Notes) -- this
    helper exists so that inversion is never re-derived ad hoc at a call site."""
    return min(level_a, level_b)
