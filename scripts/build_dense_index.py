"""
Builds the dense retrieval index from all chunks currently in SQLite and
persists it to data/processed/dense_index/.

Uses the encoder configured in ir/embeddings/config.py (LSA by default --
see that file and ir/embeddings/base.py for how to switch to a real
sentence-transformers encoder once running with internet access).

Run this after every `python scripts/ingest.py`.
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from db import get_session                    # noqa: E402
from models import Chunk                      # noqa: E402
from ir.embeddings.config import get_encoder  # noqa: E402
from ir.embeddings.dense_index import DenseIndex  # noqa: E402

INDEX_DIR = ROOT / "data" / "processed" / "dense_index"


def build():
    session = get_session()
    chunks = session.query(Chunk).order_by(Chunk.id).all()
    records = [(c.id, c.chunk_text) for c in chunks]
    session.close()

    if not records:
        print("No chunks found in the database. Run scripts/ingest.py first.")
        return

    encoder = get_encoder()
    print(f"Building dense index with encoder: {encoder.name}")

    index = DenseIndex(encoder)
    index.build(records)
    index.save(INDEX_DIR)

    print(f"Built dense index over {len(records)} chunks -> {INDEX_DIR}")


if __name__ == "__main__":
    build()
