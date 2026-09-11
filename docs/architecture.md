# EKOS Architecture

This document captures the architecture decisions made in the Phase 0
review, for reference as the project progresses. See the master prompt
for full context.

## Scope reality check

The original spec describes roughly a 6-8 week product. Built in 9 days,
priority order is: **IR pipeline → evaluation → integrity engine → search
UI → knowledge graph → dashboard polish.** Anything not in that list gets
a simplified, honestly-documented version rather than a "proper" one.

## Simplifications from the original spec (and why)

| Component | Simplification |
|---|---|
| Knowledge graph entities | Rule-based extraction from structured metadata (department, policy names, versions) rather than a trained NER model. LLM only for harder relation types (`conflicts_with`, `related_to`). |
| Contradiction detection | Retrieval finds candidate pairs on the same concept; one LLM call per pair classifies + extracts the factual delta. No NLI fine-tuning. |
| Duplicate detection | Cosine similarity on dense embeddings + threshold + union-find clustering. Not a separate subsystem from dense retrieval. |
| Reranking | Off-the-shelf cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`), not custom-trained. |
| Auth | Out of scope. Documented as a known limitation with a one-paragraph design sketch (JWT + RBAC) for how it would be added. |
| Database | SQLite, not Postgres. Zero setup, trivial to version/reset, sufficient for course-project scale. Postgres migration path documented but not built. |
| Document formats | Markdown only for the seed dataset (we're authoring it anyway). PDF/DOCX parsing out of scope. |
| LLM | Local model via Ollama, used only for extraction/reasoning. Retrieval is fully functional with `LLM_ENABLED=false`. |

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLite via SQLAlchemy
- **IR:** `rank_bm25`, `sentence-transformers` (`all-MiniLM-L6-v2`), FAISS (flat index)
- **Reranking:** `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Knowledge graph:** NetworkX, exported as JSON for the frontend
- **LLM:** Ollama + local 7-8B model (extraction/reasoning only, never retrieval)
- **Frontend:** React + Vite, React Flow (graph), Recharts (dashboard), Tailwind
- **Testing:** pytest, httpx / FastAPI TestClient

## Database schema (implemented in `backend/models.py`)

```
documents(id, doc_key, title, department, doc_type, version, created_date,
          effective_date, updated_date, author, owner, authority_level,
          status, supersedes_doc_key, tags, raw_text, source_path)

chunks(id, document_id, chunk_index, chunk_text, token_count, embedding_id)

entities(id, name, entity_type, first_seen_chunk_id, canonical)

relationships(id, source_entity_id, target_entity_id, relation_type,
              evidence_chunk_id, confidence)

conflicts(id, concept, conflict_type, chunk_a_id, chunk_b_id, value_a,
          value_b, severity, resolved_doc_key, detected_at, detection_method)

duplicates(id, chunk_a_id, chunk_b_id, similarity_score, cluster_id)

eval_queries(id, query_text, relevant_chunk_ids, category)
```

`embedding_id` is the only link to FAISS — SQLite is the source of truth
for text + metadata, FAISS is a derived index rebuildable from it.

## IR pipeline (design; implementation starts Phase 3-4)

1. **Ingestion**: parse → clean → chunk (~220 tokens, sentence-boundary
   aware, 1-sentence overlap) → attach document metadata to every chunk.
2. **BM25**: `rank_bm25.BM25Okapi` over chunk text, lowercase + stopword removal.
3. **Dense**: `all-MiniLM-L6-v2` embeddings, FAISS flat IP index (normalized
   vectors → cosine).
4. **Hybrid fusion**: Reciprocal Rank Fusion (RRF) across BM25 and dense
   top-k. Chosen over a tuned linear weight because RRF has no
   hyperparameters to overfit to a 15-doc eval set, and it's a citable,
   defensible IR technique for the report.
5. **Reranking**: cross-encoder rescoring of top ~20 hybrid candidates.
6. **Metadata-aware adjustment**: authority-level and recency boost applied
   *after* reranking and logged as a separate step, so its effect on
   evaluation metrics is isolated from retrieval quality itself.

## Integrity detection mechanisms

- **Outdated/superseded**: pure metadata — walk the `supersedes_doc_key`
  chain. No ML, no ambiguity, ~100% precision/recall by construction.
- **Duplicates**: pairwise cosine similarity across chunk embeddings above
  threshold (~0.88), grouped via union-find.
- **Contradictions**: (1) cluster chunks by shared concept/entity, (2)
  within a cluster, LLM checks pairs for factual disagreement and extracts
  the conflicting values, (3) severity heuristic by concept category
  (security/finance = high).
- **Definition conflicts**: same mechanism as contradictions, scoped to
  "X is defined as" / "X means" patterns per department. Flagged as
  `conflict_type='definition'`, not resolved via authority ranking —
  differing definitions across departments (e.g. Finance vs Marketing's
  "Customer") aren't necessarily errors.

## Evaluation methodology

Fixed 15-query set (`data/ground_truth/queries.json`) with hand-labeled
relevant `doc_key`s, resolved to real `chunk_id`s post-ingestion via
`scripts/resolve_ground_truth.py`. Compare BM25 / Dense / Hybrid-RRF /
Hybrid+Rerank on Precision@5/10, Recall@5/10, MRR, nDCG@10. Results stored
as checked-in JSON/CSV, not fabricated.

## Risks and fallbacks

| Risk | Fallback |
|---|---|
| Local LLM extraction slow/flaky | Pre-run once during dataset build, cache to JSON; live `/ask` is the only runtime LLM call |
| Graph visualization eats a day | Static NetworkX → JSON → fixed-layout React Flow render, skip interactivity polish |
| Hybrid fusion tuning rabbit hole | RRF has no weights to tune — sidesteps this |
| Time pressure by Day 7 | Cut order: dashboard polish → graph interactivity → definition-conflict detector → frontend polish. IR + eval + duplicate/outdated/contradiction detection + search UI are non-negotiable. |

## Network constraint (discovered during Phase 4)

The sandboxed dev environment this project has been built in cannot reach
`huggingface.co` (only pypi/npm/github-adjacent domains are allowlisted).
Since `sentence-transformers` downloads model weights from the HF Hub on
first use, this blocks the real dense encoder and cross-encoder reranker
described in the original tech-stack section below. Resolution: every
dense/rerank component is written against an abstract interface
(`ir/embeddings/base.py`, `ir/reranking/base.py`) with two implementations
each -- a no-network fallback (LSA; TF-IDF cosine reranking) used as the
default everywhere in this repo, and the real sentence-transformers-based
implementation, selectable via a one-line change in `ir/embeddings/config.py`
/ `ir/reranking/config.py`. All evaluation results in this repo were
produced with the fallback; see `evaluation/FINDINGS.md` for what that
means for the numbers and what to re-verify once running with internet
access.

## Phase log

- **Phase 1 (Foundation)**: repo skeleton, SQLite schema, 18-document seed
  dataset with engineered ground truth, markdown parser + chunker,
  ingestion script. ✅ Complete, 17 tests passing.
- **Phase 2 (Ingestion API)**: FastAPI app, document upload/list/detail,
  live dashboard metrics. ✅ Complete, 26 tests passing (9 new API tests).
- **Phase 3 (BM25)**: dataset expanded to 21 docs / 24 chunks (added 3
  longer documents to exercise multi-chunk retrieval); `ir/bm25/` module
  (tokenizer + `BM25Index` build/search/persist); `evaluation/metrics.py`
  (Precision@K, Recall@K, MRR, nDCG@K, unit-tested against hand-computed
  values); `evaluation/evaluate_bm25.py` producing real results
  (MRR 0.972, Recall@5 1.000, nDCG@5 0.975 over 18 queries); `/search` API
  endpoint. ✅ Complete, 41 tests passing (6 new search tests, 9 new metrics
  tests).
- **Phase 4 (Dense + Hybrid + Rerank)**: discovered the huggingface.co
  network constraint (see above) and built the encoder/reranker interfaces
  around it; `ir/embeddings/` (LSA + sentence-transformer encoders,
  `DenseIndex` over FAISS flat IP); `ir/hybrid/` (Reciprocal Rank Fusion,
  `HybridRetriever`); `ir/reranking/` (TF-IDF fallback + cross-encoder
  rerankers, `HybridRerankRetriever`); evaluation scripts for Systems B/C/D
  plus `compare_systems.py` generating the full comparison table; `/search`
  extended to support all 4 methods via a `method` query param; honest
  findings write-up (`evaluation/FINDINGS.md`) including a traced-through
  case where lexical-only reranking mis-ranks a superseded document above
  the current one. ✅ Complete, 54 tests passing (11 new IR component tests,
  3 new search-method tests).
- **Phase 5 (Knowledge graph)**: rule-based entity extraction
  (`knowledge/entities/`) from document metadata -- Document/Policy/
  Process/Documentation, Department, Person (skipping generic "X Team"
  authors), and a synthetic "Employees" group; rule-based relationship
  extraction (`knowledge/extraction/`) split into metadata-derived
  relations (`owned_by`, `belongs_to`, `created_by`, `supersedes`,
  `applies_to` -- confidence 1.0, directly from frontmatter) and
  text-reference relations (`references` -- confidence 0.9, detected by
  scanning document bodies for other documents' titles); NetworkX
  `MultiDiGraph` construction and neighborhood-query helpers
  (`knowledge/graph/`); `/knowledge/entities` and `/knowledge/graph` API
  endpoints, the latter supporting a `?entity_name=&depth=` neighborhood
  query matching the spec's Demo 4 scenario exactly.

  Manual inspection of the extracted graph (not just "it ran without
  errors") caught four real bugs before they became silent data quality
  issues, all now covered by regression tests in
  `tests/test_knowledge_graph.py`:
  1. Plain `DiGraph` silently collapses two different relation types
     between the same (source, target) pair into a single edge (e.g. a
     department-owned SOP is both `owned_by` and `applies_to` the same
     department) -- fixed by switching to `MultiDiGraph`.
  2. Two document versions sharing an identical title (e.g. both called
     "Remote Work Policy") caused a document's own H1 heading to spuriously
     "match" its sibling version's title, producing a nonsensical
     backward-in-time `references` edge (older version referencing the
     newer one, despite predating it).
  3. A target title that is a substring of the source's own title (e.g.
     "Leave Policy" inside "Parental Leave Policy") caused the same class
     of spurious self-referential match.
  4. Hard line-wraps in the source markdown (e.g. "...and Device\nPolicy.")
     defeated naive substring matching until body text was whitespace-
     normalized before comparison -- this also caused a real *miss* (the
     Remote Work Policy v4 → Device Policy reference wasn't found until
     fixed).

  Final graph: 34 entities, 73 relationships, manually spot-checked
  against source text for every relation type. ✅ Complete, 79 tests
  passing (18 new knowledge-graph unit tests, 7 new knowledge API tests).
- **Phase 6 (Integrity engine)**: four detectors, each validated against
  ground truth and source text, not just "it ran":
  - `integrity/versions/` -- outdated detection, pure metadata (walks
    `supersedes_doc_key`), 2/2 ground-truth cases found by construction.
  - `integrity/duplicates/` -- TF-IDF cosine + union-find clustering,
    excluding same-document and supersedes-linked pairs. **Investigated
    and validated a real limitation**: the two labeled ground-truth
    duplicate pairs (paraphrases) score 0.14-0.18 cosine similarity --
    LOWER than several unrelated same-topic pairs in the corpus
    (0.27-0.31) -- so no threshold separates true duplicates from noise
    with a lexical method here. Result: 0/2 found, documented honestly
    rather than tuned to pass. See `integrity/FINDINGS.md`.
  - `integrity/contradictions/` -- numeric-fact extraction
    (`numeric_fact_extractor.py`: regex for value+unit+local-context-key)
    grouped by concept across non-superseding document pairs; a group
    with 2+ distinct values is a contradiction, resolved via authority
    level. Catches the password-expiration case (90 vs 180 days) cleanly
    with zero false positives across the corpus. Misses the qualitative
    production-access-rules contradiction by design (no number to key
    off) -- documented as needing LLM-based semantic reasoning per the
    original architecture plan. 1/2 found.
  - `integrity/definitions/` -- regex extraction of "X is defined as Y" /
    "X means Y", grouped by term, flagged when defined differently
    (Jaccard word-overlap below threshold) by documents in different
    departments. 1/1 found (the Customer/Finance-vs-Marketing case), zero
    false positives.
  - `/integrity/conflicts`, `/integrity/duplicates`, `/integrity/outdated`,
    `/integrity/definitions` API endpoints, each returning full chunk
    evidence (not just IDs) so findings are independently checkable.
  - Dashboard metrics (`/dashboard/metrics`) now reflect real conflict/
    duplicate/outdated counts; the `knowledge_integrity_score` field only
    computes once the engine has actually found something (conflict or
    duplicate cluster), rather than showing a misleading "100%" before any
    check has run.
  - `integrity/FINDINGS.md` documents every result honestly, including two
    genuine, validated negative findings (0/2 duplicates, 1/2
    contradictions) with the investigation behind each, not just the
    passing cases. ✅ Complete, 110 tests passing (24 new integrity
    detector unit tests, 7 new integrity API tests).
- **Phase 7 (Frontend)**: React + Vite + Tailwind v4. Design brief executed
  before any code (per the frontend-design skill's required brainstorm
  pass): IBM Plex type family across three disciplined roles (Serif for
  titles, Sans for UI, Mono for data/status), ink-navy ground with warm
  paper surfaces, three *semantic* accent colors (verified-green,
  conflict-red, outdated-amber) rather than decorative ones. Six pages
  (Dashboard, Search, Knowledge Graph, Integrity Center, Documents,
  Document Detail), all wired to the live backend via a Vite dev proxy --
  no mock data anywhere. Signature element: the "Conflict Card"
  (`frontend/src/components/ConflictCard.jsx`), a redline-style two-source
  diff with an authority-based verdict line, directly visualizing the
  product's core thesis.

  Verified with real Playwright screenshots against the running app, not
  just "it compiles" -- this caught two real issues before they shipped:
  1. Definition-conflict text was rendering inside the large monospace
     "value" callout designed for short numeric facts (e.g. "90 days"),
     producing an oversized, redundant block for full sentences. Fixed by
     only showing that callout for `conflict_type === 'contradiction'`.
  2. The initial layout had no responsive behavior -- at a 390px mobile
     viewport, the fixed-width sidebar consumed most of the screen and
     stat-block labels visibly overlapped. Fixed with a `hidden md:flex`
     desktop rail plus a hamburger-triggered drawer below the `md`
     breakpoint, confirmed working via Playwright (drawer opens, nav
     links are clickable and route correctly, page content re-flows
     cleanly) rather than assumed to work from the CSS alone.

  Knowledge Graph page uses `d3-force` for a real force-directed layout
  (simulated synchronously to convergence, rendered as static SVG --
  intentionally skipping live drag-interactivity per the architecture's
  own risk/fallback plan, "ship a working ugly graph over a broken pretty
  one"), with click-to-inspect node detail confirmed working via
  Playwright locator clicks. Search page exposes all four IR systems
  (BM25/Dense/Hybrid/Hybrid+Rerank) via a live method selector, confirmed
  the password-expiration query surfaces both conflicting sources at the
  top regardless of method -- the exact Demo 2 behavior from the project
  spec. ✅ Complete. No automated frontend test suite (manual +
  Playwright-screenshot verification only); see `frontend/README.md` for
  the full list of what was and wasn't covered.
- **Phase 8 (Integration)**: deliberately hunted for integration gaps rather
  than assuming Phase 1-7's individual test suites meant the whole system
  was robust together. Found and fixed real issues:
  1. **Fresh-install / zero-setup scenario** (nobody has run any
     `scripts/build_*.py` yet): tested by wiping `data/processed/` entirely
     and starting a real `uvicorn` process (not just `TestClient`, since an
     early ad-hoc check using `TestClient(app)` without the context-manager
     form skipped the lifespan `init_db()` call and produced a misleading
     "no such table" crash that turned out to be a test-harness artifact,
     not a real bug -- confirmed by re-running with `with TestClient(app)
     as client:` and with an actual `uvicorn` subprocess). Real-world
     result: every endpoint degrades gracefully -- empty lists, honest
     "not yet computed" messaging, and a clear 503 with exact remediation
     instructions from `/search`. No crashes anywhere.
  2. **Frontend against that same fresh backend**: verified via Playwright
     screenshots that every page shows a legible empty/error state instead
     of a blank screen or unhandled exception -- including the dashboard's
     integrity score correctly showing "—" instead of a misleading "100%".
  3. **Frontend with the backend completely down**: confirmed the API
     client's error handling surfaces a clear "Request failed: 502"
     message rather than an infinite spinner or crash.
  4. **Missing catch-all route**: `/some-nonexistent-path` rendered nothing
     inside the layout (React Router had no `path="*"` route). Added
     `pages/NotFound.jsx` with a link back to the dashboard.
  5. **Document-detail error state had no way back**: hitting an invalid
     document ID showed the error but not the "← Documents" back-link that
     the success path has. Fixed for consistency.
  6. **Definition-conflict outdated-card redundancy** (carried over from
     Phase 7 polish): outdated-document stamps were repeating the same
     title text in both the "superseded" and "current" badges since both
     versions share a title. Simplified to plain status stamps.

  Full clean-slate pipeline re-verified after every fix (ingest → resolve
  → build BM25/dense/graph/integrity → evaluate all 4 IR systems → test)
  and a final full-stack Playwright pass across every route, both frontend
  and backend rebuilt from nothing. ✅ Complete, 110 backend tests still
  passing (no regressions from integration fixes).
- **Phase 9 (Submission)**: architecture diagram (Graphviz), two results
  charts (matplotlib, generated directly from `evaluation/comparison_table.json`
  and `data/processed/integrity_results.json` -- not hand-drawn illustrative
  figures); an 8-page written report (`docs/submission/EKOS_Report.docx`)
  covering problem statement, architecture, dataset, full IR evaluation
  methodology and honest findings, knowledge graph (including the four bugs
  caught during development), integrity engine (including both honest
  negative findings), frontend, integration testing, and limitations; a
  16-slide presentation deck (`docs/submission/EKOS_Presentation.pptx`);
  a demo script (`docs/submission/DEMO_SCRIPT.md`) walking through the 5
  demo scenarios from the original spec with exact steps and expected
  results, each fact-checked against a live run of the system rather than
  written from memory (this caught and corrected one inaccuracy -- the
  contradiction's displayed concept text -- before it shipped); a LICENSE
  file; final cache/artifact cleanup.

  Both the report and deck went through the mandatory visual QA process
  (convert to PDF, render every page/slide to an image, inspect each one)
  rather than being trusted from the generation script alone. This caught
  two real layout bugs in the deck before delivery: a title wrapping to a
  second line and overlapping the chart image below it, and a screenshot
  overflowing past the slide boundary into the footer. Both fixed and
  re-verified with the same process. ✅ Complete.
