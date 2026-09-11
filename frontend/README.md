# EKOS Frontend

React + Vite. Talks to the FastAPI backend (`../backend`) via a dev-time
proxy — no separate API URL configuration needed.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Requires the backend running on `http://127.0.0.1:8000` (see `../README.md`)
and all indexes/graph/integrity data already built (`scripts/build_*.py`).
Vite's dev server proxies `/api/*` to the backend (see `vite.config.js`).

Visit `http://localhost:5173`.

## Build

```bash
npm run build
```

Outputs to `dist/`. This is a static build — serve it with any static file
server, pointed at a deployed instance of the backend (you'd need to swap
the `/api` proxy for a real backend URL outside of local dev).

## Pages

- **Dashboard** (`/`) — live integrity score, document/entity/relationship
  counts, department breakdown, recent conflict findings
- **Search** (`/search`) — query input with a live retrieval-method
  selector (BM25 / Dense / Hybrid / Hybrid+Rerank)
- **Knowledge Graph** (`/graph`) — force-directed graph (d3-force layout,
  rendered as static SVG), click a node to inspect its relationships;
  search by entity name for a neighborhood view
- **Integrity Center** (`/integrity`) — tabbed view of contradictions,
  definition conflicts, duplicates, and outdated documents, each with full
  evidence
- **Documents** (`/documents`, `/documents/:id`) — filterable document
  library and detail view

## Design system

See `docs/architecture.md` in the repo root for the full design brief.
Summary: IBM Plex type family used across three roles (Serif for
titles/display, Sans for UI, Mono for data/status), ink-navy background
with warm-paper surfaces, and three semantic accent colors (verified
green / conflict red / outdated amber) that carry real meaning rather than
decoration. The signature element is the "Conflict Card"
(`src/components/ConflictCard.jsx`) — a redline-style two-source diff with
an authority-based verdict, used on both the Dashboard and Integrity
Center.

Responsive down to a 390px mobile viewport (tested): the sidebar becomes a
hamburger-triggered drawer below the `md` breakpoint.

## Known limitations

- No loading skeletons — uses a simple pulse indicator for all async states.
- Knowledge graph layout re-simulates from scratch on every page load /
  neighborhood search (positions aren't stable across navigations). Fine
  at this corpus size (tens of nodes); would need a persisted layout for a
  much larger graph.
- No client-side caching of API responses — every page navigation re-fetches.
- Document upload (`POST /documents/upload`, implemented in the backend)
  has no UI yet — only upload-then-view was in scope for this phase.
