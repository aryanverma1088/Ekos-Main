from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_session
from models import Document, Entity, Relationship, Conflict, Duplicate
from schemas import DashboardMetrics

router = APIRouter()


def db_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics(session: Session = Depends(db_dep)):
    """
    Per project Rule 4 (no hard-coded dashboard numbers), every field here is
    computed live from the database. Entity/relationship/conflict/duplicate
    counts are genuinely 0 until Phase 5 (knowledge graph) and Phase 6
    (integrity engine) are implemented -- they are not placeholders, they
    reflect that those tables are not yet populated.
    """
    docs = session.query(Document).all()

    by_dept = Counter(d.department for d in docs)
    by_status = Counter(d.status for d in docs)

    entity_count = session.query(Entity).count()
    relationship_count = session.query(Relationship).count()
    conflict_count = session.query(Conflict).count()
    duplicate_cluster_count = len({d.cluster_id for d in session.query(Duplicate).all() if d.cluster_id is not None})
    outdated_count = by_status.get("superseded", 0)

    integrity_score = None
    note = ("Documents, metadata, knowledge graph, and duplicate/contradiction/definition counts are "
            "all live, computed from the DB. Outdated detection is pure metadata (100% precision by "
            "construction); duplicate/contradiction/definition detection are rule-based fallbacks with "
            "documented, validated recall gaps -- see integrity/FINDINGS.md before treating these counts "
            "as a complete picture of the corpus's actual issues.")
    # Only compute a score once the integrity engine has actually found something
    # (a conflict or a duplicate cluster) -- entity_count > 0 alone just means
    # Phase 5 ran, not that anything has been checked for integrity issues.
    # Showing "100%" before any check has run would misleadingly read as "all clear".
    if conflict_count > 0 or duplicate_cluster_count > 0:
        total_checks = max(len(docs), 1)
        integrity_score = round(100 * (1 - (conflict_count / total_checks)), 1)

    return DashboardMetrics(
        documents=len(docs),
        documents_by_department=dict(by_dept),
        documents_by_status=dict(by_status),
        knowledge_entities=entity_count,
        relationships=relationship_count,
        duplicate_clusters=duplicate_cluster_count,
        conflicts=conflict_count,
        potentially_outdated_documents=outdated_count,
        knowledge_integrity_score=integrity_score,
        note=note,
    )
