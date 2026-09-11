# Integrity Engine Findings (Phase 6)

Validation run: `python scripts/build_integrity_engine.py --reset`, results
in `data/processed/integrity_results.json`.

## Summary

| Detector | Ground truth cases found | Total detected | Method |
|---|---|---|---|
| Outdated | 2/2 | 2 | Metadata (supersedes chain) |
| Contradictions | 1/2 | 1 | Rule-based (numeric fact grouping) |
| Duplicates | 0/2 | 0 | Rule-based (TF-IDF cosine + clustering) |
| Definitions | 1/1 | 1 | Rule-based (regex extraction + diff) |

Every finding was manually inspected against source text before being
trusted (see below) — none of these numbers are asserted on faith that the
detector "ran correctly."

## Outdated detection: 2/2, as expected

This is pure metadata (the `supersedes_doc_key` chain from document
frontmatter), so 100% precision/recall here isn't an achievement — it's
the expected result of a detector with no inference step. Included in the
table for completeness, not because it demonstrates anything about the
detection *technique*.

## Contradictions: 1/2 — a validated, honest partial result

**Found:** password expiration (90 days vs 180 days,
`it-security-policy-v2` vs `it-handbook`), correctly resolved in favor of
`it-security-policy-v2` via authority level (1 vs 3), correctly flagged
`severity: high` via keyword match on "security"/"password".

**Missed:** production database access rules (`it-access-control-policy`
vs `eng-production-access-policy`) — one requires manager approval "for
all, regardless of seniority," the other grants senior engineers standing
access without a per-instance request. This is a genuine factual
contradiction, but it doesn't hinge on a **number** — it's a qualitative
disagreement about a policy rule. The detector implemented here (extract
numeric facts, group by concept, flag differing values) has no mechanism
to catch this by design, not by bug. Catching it would require semantic /
NLI-style reasoning over the two passages — exactly what the original
architecture plan (`docs/architecture.md`) assigns to an LLM step, and
exactly what this sandboxed environment's lack of network access to
huggingface.co (or any other model host) rules out for now (see
`evaluation/FINDINGS.md` for the parallel constraint on the dense encoder
and reranker).

**Candidate-generation investigation that informed this design:** before
settling on numeric-fact grouping as the core signal, I tested whether
whole-chunk similarity (both LSA and plain TF-IDF cosine) could serve as a
*candidate pair generator* for contradiction detection. It doesn't work
well here: the true password-contradiction pair scores only **0.106**
cosine similarity — lower than numerous unrelated pairs in the corpus —
because `it-security-policy-v2` is a multi-topic document (passwords, MFA,
encryption, incident reporting) and the shared "password" topic gets
diluted across the whole-chunk vector. Numeric-fact grouping sidesteps
this entirely by extracting concept keys directly from local context
around each number, rather than relying on whole-document similarity.

## Duplicates: 0/2 — a real, validated limitation, not a bug

This is the most important honest finding in this phase. I did not simply
accept "0 detected" — I validated *why*, using the same investigative
process as the reranker finding in `evaluation/FINDINGS.md`.

Both labeled duplicate ground-truth pairs were checked against every
cross-document chunk pair in the corpus, using both LSA and plain TF-IDF
cosine similarity:

| Pair | Cosine similarity |
|---|---|
| `hr-leave-policy` / `hr-employee-handbook` (labeled duplicate) | 0.143 |
| `it-security-policy-v2` / `it-device-policy` (labeled duplicate) | 0.181 |
| `eng-production-access-policy` / `it-access-control-policy` (unrelated, per duplicate ground truth — this is a *contradiction* case) | 0.314 |
| `eng-incident-response-sop` / `it-incident-response-policy` (unrelated) | 0.271 |
| `hr-leave-policy` / `hr-parental-leave-policy` (unrelated) | 0.270 |

**No threshold value separates the true duplicates (0.14–0.18) from the
unrelated pairs (0.27–0.31) here.** The two document version pairs
(`finance-expense-policy` v1/v2 at 0.85–0.98, `hr-remote-work-policy` v3/v4
at 0.80–0.81) score far higher than either — as expected, since they share
nearly identical boilerplate text — and are correctly excluded from
duplicate detection entirely (handled instead by outdated detection, since
they're connected by a `supersedes` relationship).

**Why this happens:** the two labeled duplicate cases are *paraphrases*
("submit leave requests at least 48 hours before" vs "should be submitted
two days before"; "full-disk encryption enabled before...used" vs "Full
disk encryption must be enabled...before the device is handed over") —
they share the underlying fact but not much surface vocabulary. Both
lexical methods available in this sandboxed environment (TF-IDF, and LSA
built on top of TF-IDF) fundamentally represent text via shared *words*
(or word co-occurrence patterns derived from shared words). Catching
genuine paraphrase-level duplication requires representations trained to
place paraphrases near each other in vector space regardless of surface
wording — i.e., a real sentence-embedding model (`sentence-transformers`),
not a bag-of-words method. This is the single clearest piece of evidence
in this project for why the encoder swap documented in
`ir/embeddings/config.py` matters, not just as an incremental quality
improvement.

**Threshold choice:** rather than lower the threshold until it happens to
catch these two labeled cases (which would just overfit to n=2 examples
and flood the corpus with false positives at that threshold — recall the
0.27–0.31 unrelated pairs sit *above* the true duplicates), the threshold
(0.60) was set to catch only near-verbatim duplication with high
precision, and this limitation is documented instead of hidden.

## Definitions: 1/1

Found the "Customer" conflict between `finance-glossary` (paying account)
and `project-atlas-charter` (qualified lead), correctly restricted to
cross-department pairs and correctly passing the difference threshold
(the two definitions share almost no vocabulary). This detector's regex
pattern (`"X is defined as Y."` / `"X means Y."`) is narrow by design — it
will miss definitions phrased other ways — but had zero false positives
against this corpus.

## What would close the gaps

Both remaining gaps (qualitative contradictions, paraphrase-level
duplicates) point to the same root cause and the same fix: semantic
understanding beyond bag-of-words. Per the architecture plan, this is
exactly what an LLM-assisted step and a real sentence-embedding model are
for. Recommended before final submission: re-run
`scripts/build_integrity_engine.py` after switching
`ir/embeddings/config.py` to `sentence_transformer` (duplicate detection
could be extended to reuse the dense index instead of a dedicated TF-IDF
pass) and adding an LLM-based contradiction classifier for the
non-numeric case, once running with internet access.
