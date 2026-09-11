"""
Minimal tokenizer for BM25. Deliberately dependency-free (no NLTK/spaCy) --
this is a course project over a small, controlled English corpus, not a
production multilingual system.
"""
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Small hand-picked stopword list. Kept short and conservative: BM25 already
# downweights high-frequency terms via IDF, so aggressive stopword removal
# isn't necessary and risks stripping meaningful short words (e.g. "who",
# which matters for ownership queries like "who owns X").
STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "this", "that",
    "these", "those", "it", "its", "as", "by", "with", "from",
}


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOPWORDS]
