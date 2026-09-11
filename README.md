# EKOS — Enterprise Knowledge Operating System

An IR-first enterprise knowledge discovery and integrity platform.


See `docs/architecture.md` for the full design rationale and phase plan.

## Status

**All 9 phases complete.** Foundation through submission prep. See
`docs/architecture.md` for the full phase-by-phase development log.

**Submission materials** (`docs/submission/`):
- `EKOS_Report.docx` — full written technical report (architecture, IR
  evaluation, knowledge graph, integrity engine, honest findings)
- `EKOS_Presentation.pptx` — 16-slide presentation deck
- `DEMO_SCRIPT.md` — walkthrough of the 5 required demo scenarios with
  exact steps and expected results
- `architecture.png`, `comparison_chart.png`, `integrity_results_chart.png`
  — figures used in the report/deck, generated from real project data

**Important:** this sandboxed dev environment cannot reach huggingface.co,
so the dense encoder and reranker currently run on no-network fallbacks
(LSA and TF-IDF cosine reranking, respectively) rather than the real
`sentence-transformers` models. Both are swappable to the real
implementations via one-line config changes once running with internet
access — see `evaluation/FINDINGS.md` for details and why this matters
for the final numbers. The integrity engine's duplicate/contradiction
detectors have the same network constraint and the same honest,
validated limitations — see `integrity/FINDINGS.md`.

What exists right now:
- SQLite schema for documents, chunks, entities, relationships, conflicts,
  duplicates, and eval queries
- Markdown+frontmatter document parser and sentence-boundary-aware chunker
- 21-document fictional enterprise dataset (Aurelia Technologies) across
  HR, IT-Security, Finance, Engineering, and Projects, with intentionally
  engineered duplicate/contradiction/outdated/definition-conflict cases
  (24 chunks total — 3 documents split into 2 chunks, exercising
  multi-chunk retrieval)
- Ground truth files for retrieval evaluation and integrity detection,
  verified byte-exact against the actual chunked text (see tests)
- FastAPI backend: document upload/list/detail, live (non-fabricated)
  dashboard metrics, `/search` supporting all 4 retrieval methods,
  `/knowledge/entities` and `/knowledge/graph`, `/integrity/conflicts`,
  `/integrity/duplicates`, `/integrity/outdated`, `/integrity/definitions`
- **Full IR evaluation**: BM25 (System A), LSA dense retrieval (System B),
  Hybrid RRF fusion (System C), and Hybrid + rerank (System D), each with
  real Precision@K/Recall@K/MRR/nDCG@K numbers and a generated comparison
  table — see `evaluation/FINDINGS.md`
- **Knowledge graph**: 34 entities, 73 relationships, built entirely from
  document metadata plus rule-based cross-reference detection — see
  `docs/architecture.md` §Phase 5 for four real bugs caught and fixed by
  manually inspecting the extracted graph
- **Integrity engine**: outdated detection (2/2 ground-truth cases,
  metadata-driven, ~100% precision by construction), contradiction
  detection (1/2 ground-truth cases — catches numeric-value contradictions
  like password expiration, documented miss on qualitative contradictions),
  duplicate detection (0/2 ground-truth cases — a real, validated finding
  that paraphrase-level duplication needs semantic embeddings, not lexical
  similarity, not a bug), definition conflict detection (1/1 ground-truth
  case). Every result manually validated against source text and ground
  truth, not just "it ran" — see `integrity/FINDINGS.md` for the full,
  honest investigation behind each number
- **Frontend**: React + Vite app with 6 pages (Dashboard, Search,
  Knowledge Graph, Integrity Center, Documents, Document Detail), wired
  to the live backend (no mock data). Deliberate design system (IBM Plex
  type family, ink-navy/paper palette with semantic accent colors); the
  "Conflict Card" signature element renders the integrity engine's
  contradiction/definition findings as a redline-style two-source diff
  with an authority verdict. Verified end-to-end with real screenshots
  (not just "it compiles") — including catching and fixing a real bug
  (definition text rendering in a callout meant for short numeric facts)
  and a mobile-responsiveness gap (fixed with a hamburger-drawer nav,
  confirmed working down to a 390px viewport) — see `frontend/README.md`
- 110 passing backend tests
- **Integration-tested**: verified the whole system (fresh backend +
  fresh frontend, zero setup) degrades gracefully rather than crashing —
  every page shows honest empty/error states instead of blank screens or
  unhandled exceptions, confirmed via real `uvicorn` + Playwright, not
  just individual unit tests. Fixed several integration-only gaps this
  surfaced (missing 404 route, inconsistent error-state navigation) — see
  `docs/architecture.md` §Phase 8 for the full list

## Setup

```bash
cd ekos
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
```

## Load the dataset and build the retrieval indexes

```bash
python scripts/ingest.py --reset          # parses data/raw/**/*.md into SQLite
python scripts/resolve_ground_truth.py    # maps ground truth to real chunk_ids
python scripts/build_bm25_index.py        # builds data/processed/bm25_index.pkl
python scripts/build_dense_index.py       # builds data/processed/dense_index/ (LSA by default)
python scripts/build_knowledge_graph.py --reset  # builds entities/relationships + data/processed/knowledge_graph.json
python scripts/build_integrity_engine.py --reset  # runs all 4 integrity detectors, persists duplicates/conflicts
```

Re-run all six any time the dataset in `data/raw/` changes.

## Run the retrieval evaluation

```bash
python evaluation/evaluate_bm25.py           # System A
python evaluation/evaluate_dense.py          # System B
python evaluation/evaluate_hybrid.py         # System C
python evaluation/evaluate_hybrid_rerank.py  # System D
python evaluation/compare_systems.py         # combined comparison table
```

Each `evaluate_*.py` prints Precision@5/10, Recall@5/10, MRR, and nDCG@5/10
over the 18-query ground truth set and writes a per-query breakdown to
`evaluation/results_*.json`. `compare_systems.py` combines all four into
`evaluation/comparison_table.json`. **Read `evaluation/FINDINGS.md`** before
treating the numbers as final — it documents an important caveat about the
fallback encoder/reranker and a traced-through ranking issue involving
superseded document versions.

## Run the API

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Then visit `http://127.0.0.1:8000/docs` for interactive API docs.

Endpoints implemented so far:
- `GET /health`
- `POST /documents/upload` — upload a new `.md` doc with YAML frontmatter
- `GET /documents` — list, filterable by `department`, `status`, `doc_type`
- `GET /documents/{id}` — full detail including chunks
- `GET /dashboard/metrics` — live counts; entity/relationship/conflict
  fields are genuinely 0 until Phase 5-6 are built (not placeholders)
- `GET /search?q=...&top_k=10&method=hybrid_rerank` — retrieval over all
  chunks. `method` is one of `bm25` | `dense` | `hybrid` | `hybrid_rerank`
  (default `hybrid_rerank`)
- `GET /knowledge/entities?entity_type=...` — list extracted entities
  (Document/Policy/Process/Documentation, Department, Person, Group)
- `GET /knowledge/entities/{id}` — single entity detail
- `GET /knowledge/graph` — full graph export (`{nodes, edges}`)
- `GET /knowledge/graph?entity_name=...&depth=1` — neighborhood subgraph
  around a named entity (case-insensitive exact match), e.g.
  `?entity_name=hr-remote-work-policy-v4` surfaces its owning department,
  applies-to scope, cross-referenced security policy, and superseded
  version — this is the Demo 4 scenario from the project spec
- `GET /integrity/outdated` — supersession chains (metadata-driven)
- `GET /integrity/conflicts?conflict_type=...&severity=...` — detected
  contradictions and definition conflicts, with full chunk evidence
- `GET /integrity/duplicates` — detected near-duplicate chunk pairs
  (currently empty — see `integrity/FINDINGS.md` for why that's an honest
  result, not a bug)
- `GET /integrity/definitions` — convenience alias for
  `/integrity/conflicts?conflict_type=definition`

Note: `/search` loads and caches each index/pipeline in-process on first
use. If you rebuild an index (`scripts/build_*_index.py`) while the API is
already running, restart the server to pick up the change. `/knowledge/*`
and `/integrity/*` do NOT need a restart — they read live from the DB on
every request (cheap at this corpus size).

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. Requires the backend running on port 8000
(Vite proxies `/api/*` to it — see `frontend/vite.config.js`) and all data
already built per the steps above. See `frontend/README.md` for page-by-page
details and the design system notes.

## Run the tests

```bash
pytest tests/ -v
```

Covers: document parsing, chunking, ground-truth integrity (including a
check that every hand-labeled snippet is a verbatim substring of the real
chunked text), and the FastAPI endpoints.

## Repository structure

```
ekos/
├── backend/          FastAPI app, models, routers, ingestion logic
├── frontend/          React + Vite app (Dashboard, Search, Knowledge Graph,
│                      Integrity Center, Documents) — see frontend/README.md
├── ir/                 BM25 / embeddings / hybrid / reranking (Phase 3-4)
├── knowledge/         entity/relation extraction, graph (Phase 5)
├── integrity/          duplicates / contradictions / versions / definitions (Phase 6)
├── data/
│   ├── raw/            seed dataset (markdown + YAML frontmatter, by department)
│   ├── processed/       SQLite DB (gitignored) + built indexes/graph/results
│   └── ground_truth/    hand-authored duplicates/contradictions/outdated/definitions/queries
├── evaluation/         retrieval evaluation scripts + FINDINGS.md (Phase 3-4)
├── tests/
├── docs/
└── scripts/            ingest.py, build_*.py, resolve_ground_truth.py
```

## Known limitations (Phase 1-8)

- Every seed document currently chunks to exactly 1 chunk except 3 that
  are long enough to split into 2 (24 chunks / 21 docs total). This is
  correct behavior, not a bug.
- No authentication on any endpoint (documented, intentional scope cut —
  see architecture doc).
- Upload endpoint only accepts `.md` with YAML frontmatter; PDF/DOCX
  parsing is out of scope for this project (dataset is authored directly
  in markdown).
- **Dense encoder and reranker run on no-network fallbacks** (LSA;
  TF-IDF cosine reranking) because this sandboxed dev environment cannot
  reach huggingface.co. Swap to real `sentence-transformers` models via
  `ir/embeddings/config.py` / `ir/reranking/config.py` once running with
  internet access, then re-run the evaluation scripts — see
  `evaluation/FINDINGS.md` for full detail and why the comparison table
  should be re-verified with real models before submission.
- Retrieval evaluation currently sits at recall@5/10 = 1.000 across all
  four systems — a property of the small corpus / paraphrase-style query
  set, not evidence of unusually strong retrieval. See
  `evaluation/FINDINGS.md` for a recommended fix (harder/adversarial
  queries) before treating this as a final result.
- Knowledge graph entity/relationship extraction is entirely rule-based
  (metadata + text substring matching), not LLM-assisted, for the same
  network-access reason as the encoder/reranker above. The spec's harder
  relation types (`conflicts_with`, `related_to` beyond tag/text overlap)
  are intentionally deferred — `conflicts_with` edges will be added in
  Phase 6 once the integrity engine actually detects conflicts, rather
  than guessed at now.
- `/knowledge/graph` neighborhood search (`?entity_name=`) requires an
  exact (case-insensitive) name match — no fuzzy search yet.
- **Integrity engine duplicate detection currently finds 0/2 labeled
  ground-truth cases** — validated and explained in `integrity/FINDINGS.md`,
  not a bug: the two labeled cases are paraphrases with low lexical
  overlap, and no threshold value separates them from unrelated same-topic
  chunk pairs using TF-IDF/LSA. Real embeddings would very likely close
  this gap.
- **Contradiction detection catches 1/2 labeled cases** (numeric-value
  contradictions like password expiration; misses qualitative
  contradictions like differing access-approval rules by design — see
  `integrity/FINDINGS.md`). Closing this gap needs semantic/NLI reasoning
  (an LLM step, per the original architecture plan), unavailable in this
  sandboxed environment.
- Integrity detectors were validated by hand against ground truth and
  source text at each step (see `integrity/FINDINGS.md` and
  `tests/test_integrity_engine.py`), but the corpus is only 24 chunks —
  false-positive rates at larger scale haven't been tested.
- Frontend has no automated tests (manual + Playwright-screenshot
  verification only — see `frontend/README.md` for what was checked).
  No document upload UI, no client-side caching, no persisted graph
  layout across navigations — see `frontend/README.md` for the full list.
