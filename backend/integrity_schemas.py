import sys
from datetime import date as date_type
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, computed_field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from authority import authority_label  # noqa: E402


class ChunkRef(BaseModel):
    chunk_id: int
    chunk_text: str
    doc_key: str
    title: str
    department: str
    authority_level: int
    version: str
    status: str
    effective_date: Optional[date_type] = None

    @computed_field
    @property
    def authority_label(self) -> str:
        return authority_label(self.authority_level)


class DuplicateOut(BaseModel):
    id: int
    cluster_id: Optional[int]
    similarity_score: float
    chunk_a: ChunkRef
    chunk_b: ChunkRef


class ConflictOut(BaseModel):
    id: int
    concept: str
    conflict_type: str  # "contradiction" | "definition"
    value_a: Optional[str]
    value_b: Optional[str]
    severity: str
    resolved_doc_key: Optional[str]
    detection_method: str
    chunk_a: ChunkRef
    chunk_b: ChunkRef

    @computed_field
    @property
    def resolution_reason(self) -> str:
        """Explains WHY resolved_doc_key won, in plain language citing
        authority level, version, and date -- never a silent pick.
        For unresolved conflicts (definitions), explains why authority
        ranking doesn't apply instead of leaving it unexplained."""
        if self.resolved_doc_key is None:
            return (
                "Not resolved by authority ranking: both definitions may be "
                "legitimate within their own department's context rather than "
                "one being factually wrong."
            )

        winner = self.chunk_a if self.chunk_a.doc_key == self.resolved_doc_key else self.chunk_b
        loser = self.chunk_b if winner is self.chunk_a else self.chunk_a

        parts = [
            f"{winner.doc_key} ({winner.authority_label}, level {winner.authority_level}) "
            f"outranks {loser.doc_key} ({loser.authority_label}, level {loser.authority_level})."
        ]
        if winner.effective_date and loser.effective_date and winner.effective_date != loser.effective_date:
            more_recent = winner.doc_key if winner.effective_date > loser.effective_date else loser.doc_key
            if more_recent != winner.doc_key:
                parts.append(
                    f"Note: {loser.doc_key} is the more recently effective document "
                    f"({loser.effective_date} vs {winner.effective_date}) but has lower authority."
                )
        return " ".join(parts)


class OutdatedOut(BaseModel):
    outdated_doc_key: str
    outdated_title: str
    outdated_version: str
    outdated_effective_date: Optional[date_type] = None
    current_doc_key: str
    current_title: str
    current_version: str
    current_effective_date: Optional[date_type] = None
    concept: str

    @computed_field
    @property
    def reason(self) -> str:
        return (
            f"{self.current_doc_key} (v{self.current_version}) explicitly supersedes "
            f"{self.outdated_doc_key} (v{self.outdated_version}) per document metadata."
        )
