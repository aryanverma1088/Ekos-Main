from typing import Optional

from pydantic import BaseModel, ConfigDict


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    entity_type: str
    canonical: bool


class RelationshipOut(BaseModel):
    source_entity_id: int
    target_entity_id: int
    relation_type: str
    confidence: float


class GraphNode(BaseModel):
    id: int
    name: str
    entity_type: str


class GraphEdge(BaseModel):
    source: int
    target: int
    relation_type: str
    confidence: float


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    note: Optional[str] = None