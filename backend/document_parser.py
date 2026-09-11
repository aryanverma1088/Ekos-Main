"""
Parses EKOS source documents (markdown with YAML frontmatter) into
(metadata_dict, body_text) pairs.

Phase 1 only needs markdown. PyMuPDF/python-docx support can be added later
(see architecture doc) behind the same parse_document() interface so the
rest of the pipeline never needs to know the source format.
"""
from datetime import date, datetime
from pathlib import Path

import yaml

FRONTMATTER_DELIM = "---"


def _parse_date(value):
    if value is None or value == "" or value == "null":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def parse_markdown(path: Path) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter_dict, body_markdown)."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError(f"{path} is missing YAML frontmatter (expected leading '---')")

    try:
        end_idx = lines[1:].index(FRONTMATTER_DELIM) + 1
    except ValueError:
        raise ValueError(f"{path} has an unterminated frontmatter block")

    frontmatter_raw = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()

    meta = yaml.safe_load(frontmatter_raw) or {}

    normalized = {
        "doc_key": meta.get("doc_key"),
        "title": meta.get("title"),
        "department": meta.get("department"),
        "doc_type": meta.get("doc_type"),
        "version": str(meta.get("version", "1.0")),
        "created_date": _parse_date(meta.get("created_date")),
        "effective_date": _parse_date(meta.get("effective_date")),
        "updated_date": _parse_date(meta.get("updated_date")),
        "author": meta.get("author"),
        "owner": meta.get("owner"),
        "authority_level": int(meta.get("authority_level", 3)),
        "status": meta.get("status", "current"),
        "supersedes_doc_key": meta.get("supersedes") if meta.get("supersedes") not in (None, "null") else None,
        "tags": meta.get("tags"),
    }

    required = ["doc_key", "title", "department", "doc_type"]
    missing = [f for f in required if not normalized.get(f)]
    if missing:
        raise ValueError(f"{path} frontmatter missing required fields: {missing}")

    return normalized, body


def parse_document(path: Path) -> tuple[dict, str]:
    """Dispatch on file extension. Only .md supported in Phase 1."""
    if path.suffix.lower() == ".md":
        return parse_markdown(path)
    raise ValueError(f"Unsupported document format: {path.suffix} ({path})")
