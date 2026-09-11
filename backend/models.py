"""
EKOS database models.

Design notes (see docs/architecture.md for full rationale):
- SQLite for Phase 1-9 (course project timeline). Swappable to Postgres later
  since we only use SQLAlchemy Core types, no SQLite-specific features.
- Embeddings themselves are NOT stored here — they live in a FAISS index on
  disk. `Chunk.embedding_id` is the integer row-id used to look them up in
  that index. This table is the source of truth for text + metadata; FAISS
  is a derived index that can always be rebuilt from this table.
"""
from datetime import datetime, date

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Float, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    doc_key = Column(String(64), unique=True, nullable=False)  # human-readable slug, e.g. "hr-remote-work-v4"
    title = Column(String(256), nullable=False)
    department = Column(String(64), nullable=False)            # HR / IT-Security / Finance / Engineering / Projects
    doc_type = Column(String(64), nullable=False)               # Policy / SOP / Handbook / MeetingNotes / ...
    version = Column(String(16), default="1.0")
    created_date = Column(Date, nullable=True)
    effective_date = Column(Date, nullable=True)
    updated_date = Column(Date, nullable=True)
    author = Column(String(128), nullable=True)
    owner = Column(String(128), nullable=True)                  # owning department/team, feeds knowledge graph "owned_by"
    authority_level = Column(Integer, nullable=False, default=3)
    # 1 = Official approved policy (highest) ... 6 = informal/internal notes (lowest)
    status = Column(String(32), default="current")              # current / superseded / draft
    supersedes_doc_key = Column(String(64), nullable=True)       # points to doc_key of the older version, if any
    tags = Column(String(256), nullable=True)                    # comma-separated for simplicity in Phase 1
    raw_text = Column(Text, nullable=False)
    source_path = Column(String(256), nullable=True)             # path under data/raw/

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document {self.doc_key} v{self.version} ({self.status})>"


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)   # position within the document, 0-based
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    embedding_id = Column(Integer, nullable=True, unique=True)  # row-id in the FAISS index (set in Phase 4)

    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk doc={self.document_id} idx={self.chunk_index}>"


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    entity_type = Column(String(64), nullable=False)  # Person/Department/Policy/Project/Product/Process/Regulation/...
    first_seen_chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=True)
    canonical = Column(Boolean, default=True)  # false if this is a known alias merged into another entity

    def __repr__(self):
        return f"<Entity {self.entity_type}:{self.name}>"


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    target_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    relation_type = Column(String(64), nullable=False)  # owns/defines/applies_to/supersedes/conflicts_with/...
    evidence_chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=True)
    confidence = Column(Float, default=1.0)  # 1.0 for metadata-derived relations, <1.0 for LLM-extracted ones


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(Integer, primary_key=True)
    concept = Column(String(256), nullable=False)         # e.g. "Password Expiration"
    conflict_type = Column(String(32), nullable=False)     # "contradiction" | "definition"
    chunk_a_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    chunk_b_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    value_a = Column(String(256), nullable=True)            # e.g. "90 days"
    value_b = Column(String(256), nullable=True)            # e.g. "180 days"
    severity = Column(String(16), default="medium")         # low/medium/high
    resolved_doc_key = Column(String(64), nullable=True)     # which source wins per authority model
    detected_at = Column(DateTime, default=datetime.utcnow)
    detection_method = Column(String(32), default="rule")    # rule / llm


class Duplicate(Base):
    __tablename__ = "duplicates"

    id = Column(Integer, primary_key=True)
    chunk_a_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    chunk_b_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    cluster_id = Column(Integer, nullable=True)  # union-find group id, assigned in integrity/duplicates


class EvalQuery(Base):
    """Ground-truth query set used by evaluation/ scripts. Loaded from
    data/ground_truth/queries.json, mirrored here so retrieval evaluation
    can join against real chunk ids after ingestion."""
    __tablename__ = "eval_queries"

    id = Column(Integer, primary_key=True)
    query_text = Column(Text, nullable=False)
    relevant_chunk_ids = Column(Text, nullable=False)  # JSON-encoded list[int]
    category = Column(String(64), nullable=True)        # e.g. "policy_lookup", "ownership", "numeric_fact"
