"""
EKOS ingestion pipeline (Phase 1).

Usage:
    python scripts/ingest.py [--reset]

Walks data/raw/**/*.md, parses frontmatter + body, chunks the body text,
and loads everything into SQLite (documents + chunks tables).

--reset drops and recreates all tables first (use during development when
the schema or dataset changes; do NOT use once embedding_id references
from Phase 4 exist unless you intend to rebuild the FAISS index too).
"""
import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from db import get_session, init_db, engine          # noqa: E402
from models import Base, Document, Chunk              # noqa: E402
from document_parser import parse_document             # noqa: E402
from chunking import chunk_document                    # noqa: E402

DATA_RAW_DIR = SCRIPT_DIR.parent / "data" / "raw"


def find_source_files() -> list[Path]:
    return sorted(DATA_RAW_DIR.rglob("*.md"))


def ingest(reset: bool = False):
    if reset:
        print("Dropping and recreating all tables...")
        Base.metadata.drop_all(bind=engine)
    init_db()

    session = get_session()
    files = find_source_files()

    if not files:
        print(f"No .md files found under {DATA_RAW_DIR}")
        return

    doc_count = 0
    chunk_count = 0
    seen_keys = set()

    for path in files:
        meta, body = parse_document(path)
        doc_key = meta["doc_key"]

        if doc_key in seen_keys:
            raise ValueError(f"Duplicate doc_key '{doc_key}' found at {path}")
        seen_keys.add(doc_key)

        existing = session.query(Document).filter_by(doc_key=doc_key).first()
        if existing:
            print(f"  skip (already ingested): {doc_key}")
            continue

        rel_path = str(path.relative_to(SCRIPT_DIR.parent))
        document = Document(
            doc_key=doc_key,
            title=meta["title"],
            department=meta["department"],
            doc_type=meta["doc_type"],
            version=meta["version"],
            created_date=meta["created_date"],
            effective_date=meta["effective_date"],
            updated_date=meta["updated_date"],
            author=meta["author"],
            owner=meta["owner"],
            authority_level=meta["authority_level"],
            status=meta["status"],
            supersedes_doc_key=meta["supersedes_doc_key"],
            tags=meta["tags"],
            raw_text=body,
            source_path=rel_path,
        )
        session.add(document)
        session.flush()  # populate document.id before creating chunks

        chunk_texts = chunk_document(body)
        for idx, ctext in enumerate(chunk_texts):
            chunk = Chunk(
                document_id=document.id,
                chunk_index=idx,
                chunk_text=ctext,
                token_count=len(ctext.split()),
            )
            session.add(chunk)
            chunk_count += 1

        doc_count += 1
        print(f"  ingested: {doc_key}  ({len(chunk_texts)} chunks)")

    session.commit()
    session.close()

    print(f"\nDone. Ingested {doc_count} documents, {chunk_count} chunks total.")
    if doc_count:
        print(f"Average chunks/document: {chunk_count / doc_count:.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before ingesting")
    args = parser.parse_args()
    ingest(reset=args.reset)
