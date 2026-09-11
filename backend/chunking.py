"""
Sentence-boundary-aware chunking for EKOS documents.

Approach (deliberately simple for Phase 1 -- see docs/architecture.md):
1. Strip markdown heading markers but keep heading text as part of the flow
   (headings carry real topical signal, e.g. "## Password Requirements").
2. Split into sentences with a lightweight regex (good enough for the
   controlled synthetic dataset; not a general-purpose sentence splitter).
3. Greedily pack sentences into chunks up to TARGET_TOKENS, breaking only at
   sentence boundaries (never mid-sentence).
4. Carry the last OVERLAP_SENTENCES sentences of a chunk into the start of
   the next chunk, so passages spanning a chunk boundary are still
   retrievable in one piece.

Token count is approximated as whitespace-split word count. This is
intentionally a rough proxy -- good enough for chunk-sizing decisions, not
used for anything requiring exact token accounting.
"""
import re

TARGET_TOKENS = 220
OVERLAP_SENTENCES = 1

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z#*])")
_HEADING_RE = re.compile(r"^#{1,6}\s*")


def _approx_tokens(text: str) -> int:
    return len(text.split())


def _clean_line(line: str) -> str:
    line = _HEADING_RE.sub("", line).strip()
    line = line.replace("**", "")
    return line


def split_into_sentences(body_markdown: str) -> list[str]:
    sentences = []
    for raw_line in body_markdown.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        # Heading lines (short, no terminal punctuation) become their own unit
        # so they can prefix the chunk that follows without being merged
        # mid-sentence with body text.
        for piece in _SENTENCE_SPLIT_RE.split(line):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


def chunk_document(body_markdown: str) -> list[str]:
    """Returns a list of chunk_text strings for one document."""
    sentences = split_into_sentences(body_markdown)
    if not sentences:
        return []

    chunks = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _approx_tokens(sentence)

        if current and current_tokens + sentence_tokens > TARGET_TOKENS:
            chunks.append(" ".join(current))
            # start next chunk with overlap from the tail of this one
            current = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES else []
            current_tokens = sum(_approx_tokens(s) for s in current)

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks
