"""
Builds a NetworkX directed graph from Entity/Relationship rows and provides
query helpers (full export, neighborhood-around-a-node) used by the
/knowledge/graph API endpoint and, eventually, the frontend graph view.

Kept independent of SQLAlchemy: build_graph() takes plain dicts so it can
be unit tested without a DB session.
"""
import networkx as nx


def build_graph(entities: list[dict], relationships: list[dict]) -> nx.MultiDiGraph:
    """
    entities: [{id, name, entity_type}, ...]
    relationships: [{source_entity_id, target_entity_id, relation_type, confidence}, ...]

    Uses MultiDiGraph, not DiGraph: two entities can be connected by more
    than one relation_type (e.g. a department-owned SOP is both owned_by
    and applies_to the same department) -- a plain DiGraph silently
    collapses those into a single edge, which was caught by comparing
    relationships-created counts against exported-edge counts during
    development (see scripts/build_knowledge_graph.py output).
    """
    g = nx.MultiDiGraph()

    for e in entities:
        g.add_node(e["id"], name=e["name"], entity_type=e["entity_type"])

    for r in relationships:
        g.add_edge(
            r["source_entity_id"],
            r["target_entity_id"],
            relation_type=r["relation_type"],
            confidence=r.get("confidence", 1.0),
        )

    return g


def to_node_link_json(g: nx.MultiDiGraph) -> dict:
    """Full graph export in a simple {nodes, edges} shape (deliberately not
    nx.node_link_data's default shape, which is more verbose than the
    frontend needs)."""
    nodes = [
        {"id": n, "name": data["name"], "entity_type": data["entity_type"]}
        for n, data in g.nodes(data=True)
    ]
    edges = [
        {
            "source": u, "target": v,
            "relation_type": data["relation_type"], "confidence": data["confidence"],
        }
        for u, v, data in g.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def get_neighborhood(g: nx.MultiDiGraph, entity_id: int, depth: int = 1) -> dict:
    """
    Returns the node-link subgraph of all nodes reachable within `depth`
    hops of entity_id, in EITHER direction (a document's owner and the
    documents that reference it are both relevant context for "explore
    this node").
    """
    if entity_id not in g:
        return {"nodes": [], "edges": []}

    undirected = g.to_undirected(as_view=True)
    reachable = nx.single_source_shortest_path_length(undirected, entity_id, cutoff=depth)
    node_ids = set(reachable.keys())

    subgraph = g.subgraph(node_ids)
    return to_node_link_json(subgraph)


def find_entity_id_by_name(g: nx.MultiDiGraph, name: str) -> int | None:
    """Case-insensitive exact-name lookup, used to resolve a search query
    like 'Remote Work Policy' to a graph node (used by Demo 4)."""
    name_lower = name.lower()
    for n, data in g.nodes(data=True):
        if data["name"].lower() == name_lower:
            return n
    return None
