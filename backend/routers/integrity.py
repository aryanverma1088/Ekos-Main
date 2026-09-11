from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_session
from models import Document, Chunk, Duplicate, Conflict
from integrity_schemas import ChunkRef, DuplicateOut, ConflictOut, OutdatedOut

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from integrity.versions.outdated_detector import detect_outdated  # noqa: E402

router = APIRouter()


def db_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def _chunk_ref(session: Session, chunk_id: int) -> ChunkRef:
    chunk = session.get(Chunk, chunk_id)
    doc = session.get(Document, chunk.document_id)
    return ChunkRef(
        chunk_id=chunk.id, chunk_text=chunk.chunk_text,
        doc_key=doc.doc_key, title=doc.title,
        department=doc.department, authority_level=doc.authority_level,
        version=doc.version, status=doc.status, effective_date=doc.effective_date,
    )


@router.get("/duplicates", response_model=list[DuplicateOut])
def list_duplicates(session: Session = Depends(db_dep)):
    dups = session.query(Duplicate).order_by(Duplicate.similarity_score.desc()).all()
    return [
        DuplicateOut(
            id=d.id, cluster_id=d.cluster_id, similarity_score=d.similarity_score,
            chunk_a=_chunk_ref(session, d.chunk_a_id),
            chunk_b=_chunk_ref(session, d.chunk_b_id),
        )
        for d in dups
    ]


@router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(
    conflict_type: Optional[str] = Query(None, description="contradiction | definition"),
    severity: Optional[str] = Query(None, description="low | medium | high"),
    session: Session = Depends(db_dep),
):
    q = session.query(Conflict)
    if conflict_type:
        q = q.filter(Conflict.conflict_type == conflict_type)
    if severity:
        q = q.filter(Conflict.severity == severity)
    conflicts = q.order_by(Conflict.detected_at.desc()).all()

    return [
        ConflictOut(
            id=c.id, concept=c.concept, conflict_type=c.conflict_type,
            value_a=c.value_a, value_b=c.value_b, severity=c.severity,
            resolved_doc_key=c.resolved_doc_key, detection_method=c.detection_method,
            chunk_a=_chunk_ref(session, c.chunk_a_id),
            chunk_b=_chunk_ref(session, c.chunk_b_id),
        )
        for c in conflicts
    ]


@router.get("/outdated", response_model=list[OutdatedOut])
def list_outdated(session: Session = Depends(db_dep)):
    """Computed live from Document metadata (supersedes_doc_key chain) --
    no separate table needed, this detector is metadata-only (see
    integrity/versions/outdated_detector.py)."""
    docs = session.query(Document).all()
    doc_dicts = [{
        "doc_key": d.doc_key, "title": d.title, "status": d.status,
        "supersedes_doc_key": d.supersedes_doc_key,
    } for d in docs]
    by_key = {d.doc_key: d for d in docs}

    results = detect_outdated(doc_dicts)
    return [
        OutdatedOut(
            outdated_doc_key=r["outdated_doc_key"],
            outdated_title=by_key[r["outdated_doc_key"]].title,
            outdated_version=by_key[r["outdated_doc_key"]].version,
            outdated_effective_date=by_key[r["outdated_doc_key"]].effective_date,
            current_doc_key=r["current_doc_key"],
            current_title=by_key[r["current_doc_key"]].title,
            current_version=by_key[r["current_doc_key"]].version,
            current_effective_date=by_key[r["current_doc_key"]].effective_date,
            concept=r["concept"],
        )
        for r in results
    ]


@router.get("/definitions", response_model=list[ConflictOut])
def list_definition_conflicts(session: Session = Depends(db_dep)):
    """Convenience alias for GET /integrity/conflicts?conflict_type=definition."""
    return list_conflicts(conflict_type="definition", severity=None, session=session)
