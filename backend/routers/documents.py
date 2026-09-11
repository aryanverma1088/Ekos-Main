import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from db import get_session
from models import Document, Chunk
from document_parser import parse_document
from chunking import chunk_document
from schemas import DocumentListItem, DocumentDetail, UploadResponse

router = APIRouter()


def db_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), session: Session = Depends(db_dep)):
    """
    Ingests a single markdown document (with YAML frontmatter, same format as
    the seed dataset). Reuses the same parse -> chunk -> store logic as
    scripts/ingest.py so there is exactly one code path for ingestion.
    """
    if not file.filename.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files with YAML frontmatter are supported in Phase 1-2.")

    contents = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="wb") as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        meta, body = parse_document(tmp_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    existing = session.query(Document).filter_by(doc_key=meta["doc_key"]).first()
    if existing:
        return UploadResponse(doc_key=meta["doc_key"], id=existing.id, chunks_created=0, status="skipped_duplicate")

    document = Document(
        doc_key=meta["doc_key"],
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
        source_path=f"uploaded/{file.filename}",
    )
    session.add(document)
    session.flush()

    chunk_texts = chunk_document(body)
    for idx, ctext in enumerate(chunk_texts):
        session.add(Chunk(document_id=document.id, chunk_index=idx, chunk_text=ctext, token_count=len(ctext.split())))

    session.commit()

    return UploadResponse(doc_key=document.doc_key, id=document.id, chunks_created=len(chunk_texts), status="ingested")


@router.get("", response_model=list[DocumentListItem])
def list_documents(
    session: Session = Depends(db_dep),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
):
    q = session.query(Document)
    if department:
        q = q.filter(Document.department == department)
    if status:
        q = q.filter(Document.status == status)
    if doc_type:
        q = q.filter(Document.doc_type == doc_type)
    return q.order_by(Document.department, Document.title).all()


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: int, session: Session = Depends(db_dep)):
    doc = session.query(Document).filter_by(id=doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return doc
