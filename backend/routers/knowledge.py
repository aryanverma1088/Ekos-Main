from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_session
from models import Entity, Relationship
from knowledge_schemas import EntityOut, GraphResponse, GraphNode, GraphEdge

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from knowledge.graph.graph_builder import build_graph, to_node_link_json, get_neighborhood, find_entity_id_by_name  # noqa: E402

router = APIRouter()


def db_dep():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def load_graph(session: Session):
    """Builds the NetworkX graph fresh from the DB on every call. The corpus
    is small (tens of entities/edges) so this is cheap -- no caching needed,
    and it guarantees the API never serves a stale graph after
    scripts/build_knowledge_graph.py is re-run (unlike the /search indexes,
    which do need an API restart to pick up changes -- see README)."""
    entities = session.query(Entity).all()
    relationships = session.query(Relationship).all()

    if not entities:
        return None

    entity_dicts = [{"id": e.id, "name": e.name, "entity_type": e.entity_type} for e in entities]
    rel_dicts = [
        {"source_entity_id": r.source_entity_id, "target_entity_id": r.target_entity_id,
         "relation_type": r.relation_type, "confidence": r.confidence}
        for r in relationships
    ]
    return build_graph(entity_dicts, rel_dicts)


@router.get("/entities", response_model=list[EntityOut])
def list_entities(
    entity_type: Optional[str] = Query(None),
    session: Session = Depends(db_dep),
):
    q = session.query(Entity)
    if entity_type:
        q = q.filter(Entity.entity_type == entity_type)
    return q.order_by(Entity.entity_type, Entity.name).all()


@router.get("/entities/{entity_id}", response_model=EntityOut)
def get_entity(entity_id: int, session: Session = Depends(db_dep)):
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return entity


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    entity_name: Optional[str] = Query(None, description="If given, return only the neighborhood around this entity (case-insensitive exact match)"),
    depth: int = Query(1, ge=1, le=3, description="Hops from entity_name to include (ignored if entity_name is not given)"),
    session: Session = Depends(db_dep),
):
    """
    Full graph export, or -- if entity_name is given -- the neighborhood
    subgraph around that entity (Demo 4: searching "Remote Work Policy"
    should show its owning department, applies_to scope, related security
    policy, and superseded versions).
    """
    g = load_graph(session)
    if g is None:
        return GraphResponse(
            nodes=[], edges=[],
            note="No entities yet. Run scripts/build_knowledge_graph.py after ingesting documents.",
        )

    if entity_name:
        entity_id = find_entity_id_by_name(g, entity_name)
        if entity_id is None:
            raise HTTPException(status_code=404, detail=f"No entity found matching name '{entity_name}'")
        data = get_neighborhood(g, entity_id, depth=depth)
    else:
        data = to_node_link_json(g)

    return GraphResponse(
        nodes=[GraphNode(**n) for n in data["nodes"]],
        edges=[GraphEdge(**e) for e in data["edges"]],
    )
