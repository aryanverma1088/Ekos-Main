"""
Builds the BM25 index from all chunks currently in SQLite and persists it
to data/processed/bm25_index.pkl.

Run this after every `python scripts/ingest.py` so the index stays in sync
with the database.
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from db import get_session          # noqa: E402
from models import Chunk            # noqa: E402
from ir.bm25.index import BM25Index  # noqa: E402

INDEX_PATH = ROOT / "data" / "processed" / "bm25_index.pkl"


def build():
    session = get_session()
    chunks = session.query(Chunk).order_by(Chunk.id).all()
    records = [(c.id, c.chunk_text) for c in chunks]
    session.close()

    if not records:
        print("No chunks found in the database. Run scripts/ingest.py first.")
        return

    index = BM25Index()
    index.build(records)
    index.save(INDEX_PATH)

    print(f"Built BM25 index over {len(records)} chunks -> {INDEX_PATH}")


if __name__ == "__main__":
    build()
