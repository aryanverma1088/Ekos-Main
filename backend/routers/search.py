import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_session
from models import Chunk, Document, Conflict, Entity, Relationship
from schemas import SearchResponse, SearchResultItem
from search_enrichment import ranking_explanation, relative_confidence

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(ROOT))

from ir.bm25.index import BM25Index                              # noqa: E402
from ir.embeddings.config import get_encoder                      # noqa: E402
from ir.embeddings.dense_index import DenseIndex                  # noqa: E402
from ir.hybrid.hybrid_retriever import HybridRetriever            # noqa: E402
from ir.reranking.config import get_reranker                       # noqa: E402
from ir.reranking.reranked_retriever import HybridRerankRetriever  # noqa: E402

router = APIRouter()

BM25_INDEX_PATH = ROOT / "data" / "processed" / "bm25_index.pkl"
DENSE_INDEX_DIR = ROOT / "data" / "processed" / "dense_index"

SearchMethod = Literal["bm25", "dense", "hybrid", "hybrid_rerank"]

# In-process caches. Restart the API after rebuilding an index to pick up changes
# (no hot-reload in Phase 1-4 -- see README "Known limitations").
_bm25_cache: BM25Index | None = None
_dense_cache: DenseIndex | None = None
_hybrid_cache: HybridRetriever | None = None
_hybrid_rerank_cache: HybridRerankRetriever | None = None
_chunk_text_cache: dict[int, str] | None = None


def _require(path: Path, build_script: str):
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"{path.name} not built yet. Run {build_script}.")


def get_bm25() -> BM25Index:
    global _bm25_cache
    if _bm25_cache is None:
        _require(BM25_INDEX_PATH, "scripts/build_bm25_index.py")
        _bm25_cache = BM25Index.load(BM25_INDEX_PATH)
    return _bm25_cache


def get_dense() -> DenseIndex:
    global _dense_cache
    if _dense_cache is None:
        _require(DENSE_INDEX_DIR / "meta.json", "scripts/build_dense_index.py")
        _dense_cache = DenseIndex.load(DENSE_INDEX_DIR, get_encoder())
    return _dense_cache


def get_hybrid() -> HybridRetriever:
    global _hybrid_cache
    if _hybrid_cache is None:
        _hybrid_cache = HybridRetriever(get_bm25(), get_dense())
    return _hybrid_cache


def get_chunk_text_cache(session: Session) -> dict[int, str]:
    global _chunk_text_cache
    if _chunk_text_cache is None:
        rows = session.query(Chunk.id, Chunk.chunk_text).all()
        _chunk_text_cache = {cid: text for cid, text in rows}
    return _chunk_text_cache


def get_hybrid_rerank(session: Session) -> HybridRerankRetriever:
    global _hybrid_rerank_cache
    if _hybrid_rerank_cache is None:
        text_cache = get_chunk_text_cache(session)
        _hybrid_rerank_cache = HybridRerankRetriever(
            get_hybrid(), get_reranker(), lambda cid: text_cache[cid]
        )
    return _hybrid_rerank_cache


def db_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    method: SearchMethod = Query("hybrid_rerank", description="bm25 | dense | hybrid | hybrid_rerank"),
    session: Session = Depends(db_dep),
):
    """
    Retrieval over all chunks. `method` selects which of the four IR systems
    serves the request (see evaluation/FINDINGS.md for how they compare):
      - bm25: System A, lexical
      - dense: System B, LSA-based semantic (see ir/embeddings/config.py for
        swapping in a real sentence-transformer encoder)
      - hybrid: System C, BM25 + dense fused via Reciprocal Rank Fusion
      - hybrid_rerank: System D, hybrid candidates rescored by a reranker
        (default -- best system in the current evaluation, though see
        evaluation/FINDINGS.md for the near-duplicate-version caveat)
    """
    if method == "bm25":
        raw_results = get_bm25().search(q, top_k=top_k)
    elif method == "dense":
        raw_results = get_dense().search(q, top_k=top_k)
    elif method == "hybrid":
        raw_results = get_hybrid().search(q, top_k=top_k)
    elif method == "hybrid_rerank":
        raw_results = get_hybrid_rerank(session).search(q, top_k=top_k)
    else:
        raise HTTPException(status_code=422, detail=f"Unknown method: {method}")

    max_score = max((score for _, score in raw_results), default=0.0)

    # Batch-compute which documents have a known integrity conflict, rather
    # than querying per-result -- a document has a conflict if ANY of its
    # chunks appears on either side of ANY Conflict row (the conflicting
    # chunk isn't necessarily the exact chunk this query happened to match).
    conflicted_chunk_ids = set()
    for c in session.query(Conflict.chunk_a_id, Conflict.chunk_b_id).all():
        conflicted_chunk_ids.update(c)
    conflicted_document_ids = set()
    if conflicted_chunk_ids:
        for (doc_id,) in session.query(Chunk.document_id).filter(Chunk.id.in_(conflicted_chunk_ids)).distinct():
            conflicted_document_ids.add(doc_id)

    def related_entities_for(doc_key: str) -> list[dict]:
        entity = session.query(Entity).filter_by(name=doc_key).first()
        if entity is None:
            return []
        rels = (
            session.query(Relationship)
            .filter((Relationship.source_entity_id == entity.id) | (Relationship.target_entity_id == entity.id))
            .filter(Relationship.relation_type != "created_by")  # too granular to be useful at a glance here
            .all()
        )
        # surface the most decision-relevant relations first
        priority = {"conflicts_with": 0, "supersedes": 1, "duplicate_of": 2, "owned_by": 3, "applies_to": 4}
        rels.sort(key=lambda r: priority.get(r.relation_type, 9))

        results = []
        for r in rels[:4]:
            other_id = r.target_entity_id if r.source_entity_id == entity.id else r.source_entity_id
            other = session.get(Entity, other_id)
            if other is None:
                continue
            results.append({"name": other.name, "entity_type": other.entity_type, "relation_type": r.relation_type})
        return results

    items = []
    for chunk_id, score in raw_results:
        chunk = session.get(Chunk, chunk_id)
        if chunk is None:
            continue
        doc = session.get(Document, chunk.document_id)
        items.append(SearchResultItem(
            chunk_id=chunk.id,
            chunk_text=chunk.chunk_text,
            score=score,
            confidence_percent=relative_confidence(score, max_score),
            document_id=doc.id,
            doc_key=doc.doc_key,
            title=doc.title,
            department=doc.department,
            version=doc.version,
            status=doc.status,
            authority_level=doc.authority_level,
            ranking_explanation=ranking_explanation(method, q, chunk.chunk_text),
            has_known_conflict=doc.id in conflicted_document_ids,
            related_entities=related_entities_for(doc.doc_key),
        ))

    return SearchResponse(query=q, method=method, results=items)
