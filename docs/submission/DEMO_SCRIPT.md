# EKOS Demo Script

Five scenarios, matching the project brief exactly. Each includes the exact
action to take, what should appear, and why it matters. Run through
`README.md` setup first (backend on :8000, frontend on :5173, all
`scripts/build_*.py` already run).

Total run time: ~8-10 minutes.

---

## Demo 1 — Enterprise Search

**Goal:** show grounded search with source, version, confidence, and related
knowledge — not just a ranked list of documents.

1. Open **Search** (`/search`).
2. Type: `What is the current remote work policy?`
3. Leave method on the default, **Hybrid + Rerank**. Press Enter.

**Expect:**
- Top result is `hr-remote-work-policy-v4`, marked **CURRENT**.
- Authority ladder shows L1 (highest — official approved policy).
- The superseded `v3` also appears in results, marked **SUPERSEDED**, lower
  in the ranking.
- Score shown per result (not a black box).

**Say:** "The system doesn't just find documents that match — it tells you
which version is current, how authoritative the source is, and shows you
the superseded version too, rather than hiding it."

---

## Demo 2 — Contradiction

**Goal:** show EKOS surfacing a real conflict instead of silently picking
one source.

1. Still on Search, type: `What is the password expiration policy?`
2. Note: **both** `it-security-policy-v2` (90 days) and `it-handbook`
   (180 days) appear near the top of results, regardless of method.
3. Switch to **Integrity Center** → **Contradictions** tab.

**Expect:**
- One contradiction card: concept "must be changed every" (the extracted
  context key, shown verbatim as the system's real output rather than
  cleaned up for the demo).
- Two source columns: IT Handbook (180 days) vs. IT Security Policy
  (90 days).
- IT Security Policy is marked **AUTHORITATIVE** (green highlight),
  resolved via authority level (L1 vs L3).
- Verdict line: "→ it-security-policy-v2 is authoritative (higher
  authority level)".

**Say:** "This is the core differentiator. A normal search engine returns
both documents and lets you figure out which is right. EKOS tells you
there's a conflict, shows you the evidence side by side, and resolves it
by document authority — while still showing you both sources so you can
disagree with the resolution if you have context the system doesn't."

---

## Demo 3 — Duplicate Knowledge

**Goal:** show the duplicate-detection UI, **and** be upfront about its
honest limitation — this is a deliberate part of the demo, not something to
skip past.

1. Integrity Center → **Duplicates** tab.

**Expect:**
- Empty state: "No near-duplicates found by the current method" with an
  explanation that this is a validated, honest finding, not a bug — see
  `integrity/FINDINGS.md`.

**Say:** "We could have hidden this or quietly lowered the threshold until
it found something. Instead: we checked the two labeled duplicate pairs in
our ground truth against every other pair in the corpus. The true
duplicates score 0.14–0.18 cosine similarity — *lower* than several
unrelated pairs, which score 0.27–0.31. No threshold separates them. That's
because these are genuine paraphrases sharing a fact but very little
vocabulary — exactly what bag-of-words methods (our no-network fallback)
miss, and exactly what a real sentence-embedding model is built to catch.
This is the single clearest argument in the whole project for why the
encoder swap matters."

*(Optional, if you want to show duplicate detection succeeding on
easier cases: point out in `integrity/FINDINGS.md` that the two document
version pairs — Remote Work Policy v3/v4, Expense Policy v1/v2 — score
0.80–0.98 similarity, correctly identified as near-identical text, but are
deliberately excluded from "duplicates" and handled instead by outdated
detection, since supersession is a better explanation than coincidence.)*

---

## Demo 4 — Knowledge Graph

**Goal:** show the interactive graph and a meaningful neighborhood query.

1. Open **Knowledge Graph** (`/graph`).
2. In the search box, type `hr-remote-work-policy-v4` and click **Explore**.

**Expect:**
- Neighborhood graph centered on the policy, showing:
  - `HR` (Department, green) — via `owned_by`
  - `Employees` (Group, amber) — via `applies_to`
  - `hr-remote-work-policy-v3` (Document, white square) — via `supersedes`
  - `it-security-policy-v2` and `it-device-policy` (Documents) — via
    `references` (detected from the policy's own text: "Employees must
    comply with the current IT Security Policy and Device Policy...")
3. Click the `HR` node to show its own neighborhood — all documents owned
   by HR.

**Say:** "This is built entirely from document metadata and a rule-based
scan of the text for cross-references — no LLM. It took catching four real
bugs during development to get here: two document versions sharing a title
caused false self-references, a target title being a substring of the
source's own title caused the same issue, and a hard line-wrap in the
source markdown defeated naive text matching until we normalized
whitespace. All four are now regression-tested."

---

## Demo 5 — Retrieval Evaluation

**Goal:** show the real IR comparison — the core of the IR course
contribution.

1. In a terminal, from the repo root:
   ```bash
   python evaluation/compare_systems.py
   ```
2. Walk through the printed table: BM25 / Dense / Hybrid / Hybrid+Rerank
   across Precision@5/10, Recall@5/10, MRR, nDCG@5/10.
3. Open `evaluation/FINDINGS.md` and read the "Honest caveats" section
   aloud or paraphrase it.

**Expect / say:**
- Recall@5/10 = 1.000 across all four systems — flag immediately that this
  reflects the small, paraphrase-style 18-query eval set, not unusually
  strong retrieval. State this before anyone else can raise it as a
  concern.
- System D scores at or below System C. Walk through the traced cause:
  query q04 ("reimbursement limit"), where Hybrid RRF ranks the current
  Expense Policy v2 fractionally above superseded v1 (near-tied since the
  text is nearly identical), and the TF-IDF reranker — which has no
  authority/recency signal — flips that order. Point out this motivates
  the metadata-authority boost described in `docs/architecture.md`.

**Say:** "Every number here is from a real, reproducible run — not
illustrative. And when a result looked slightly off (System D scoring
below System C), we didn't just report it, we traced it to a specific
query and explained the mechanism, because that's more useful for an IR
course than a clean-looking table that hides why."

---

## If asked "why not just use real embeddings?"

Be direct: this sandboxed development environment cannot reach
huggingface.co, so `sentence-transformers` model downloads fail. Every
affected component (dense encoder, reranker, and the duplicate/
contradiction detectors that depend on similarity) is built behind a
swappable interface with a one-line config change
(`ir/embeddings/config.py`, `ir/reranking/config.py`) to switch to the real
models once running with internet access. This isn't a workaround hiding a
gap — it's why several of the "honest findings" above exist and are
worth discussing on their own merits.

## Closing line

"The clearest evidence for EKOS's own thesis is its most honest finding:
the 0/2 result on paraphrased duplicate detection isn't a failure of the
system — it's a precise, validated demonstration of exactly where lexical
methods stop being sufficient and semantic understanding becomes
necessary. That's the same problem EKOS exists to solve for an
organization's documentation in the first place."
