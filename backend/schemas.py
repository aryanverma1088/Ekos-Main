import sys
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from authority import authority_label  # noqa: E402


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_index: int
    chunk_text: str
    token_count: Optional[int] = None


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_key: str
    title: str
    department: str
    doc_type: str
    version: str
    status: str
    authority_level: int
    owner: Optional[str] = None
    updated_date: Optional[date] = None
    supersedes_doc_key: Optional[str] = None

    @computed_field
    @property
    def authority_label(self) -> str:
        return authority_label(self.authority_level)


class DocumentDetail(DocumentListItem):
    model_config = ConfigDict(from_attributes=True)

    created_date: Optional[date] = None
    effective_date: Optional[date] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    raw_text: str
    chunks: list[ChunkOut] = []


class UploadResponse(BaseModel):
    doc_key: str
    id: int
    chunks_created: int
    status: str  # "ingested" | "skipped_duplicate"


class DashboardMetrics(BaseModel):
    documents: int
    documents_by_department: dict[str, int]
    documents_by_status: dict[str, int]
    knowledge_entities: int
    relationships: int
    duplicate_clusters: int
    conflicts: int
    potentially_outdated_documents: int
    knowledge_integrity_score: Optional[float] = None
    note: str


class SearchResultItem(BaseModel):
    chunk_id: int
    chunk_text: str
    score: float
    confidence_percent: float
    document_id: int
    doc_key: str
    title: str
    department: str
    version: str
    status: str
    authority_level: int
    ranking_explanation: str
    has_known_conflict: bool
    related_entities: list[dict]

    @computed_field
    @property
    def authority_label(self) -> str:
        return authority_label(self.authority_level)


class SearchResponse(BaseModel):
    query: str
    method: str  # "bm25" | "dense" | "hybrid" | "hybrid_rerank"
    results: list[SearchResultItem]
