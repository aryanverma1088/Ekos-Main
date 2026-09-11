"""
Phase 1 tests: document parsing, chunking, and ground-truth integrity.

Run with:  cd ekos && pytest tests/ -v
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from document_parser import parse_markdown          # noqa: E402
from chunking import chunk_document, split_into_sentences  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
GT_DIR = ROOT / "data" / "ground_truth"


def all_source_files():
    return sorted(RAW_DIR.rglob("*.md"))


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------

class TestDocumentParser:

    def test_all_source_files_parse_without_error(self):
        files = all_source_files()
        assert len(files) >= 15, "Expected at least 15 seed documents"
        for path in files:
            meta, body = parse_markdown(path)
            assert meta["doc_key"], f"{path} missing doc_key"
            assert body.strip(), f"{path} has empty body"

    def test_doc_keys_are_unique(self):
        keys = [parse_markdown(p)[0]["doc_key"] for p in all_source_files()]
        assert len(keys) == len(set(keys)), "Duplicate doc_key found across dataset"

    def test_required_metadata_fields_present(self):
        required = ["doc_key", "title", "department", "doc_type", "authority_level", "status"]
        for path in all_source_files():
            meta, _ = parse_markdown(path)
            for field in required:
                assert meta.get(field) not in (None, ""), f"{path} missing '{field}'"

    def test_authority_level_in_valid_range(self):
        for path in all_source_files():
            meta, _ = parse_markdown(path)
            assert 1 <= meta["authority_level"] <= 6, f"{path} has out-of-range authority_level"

    def test_supersedes_references_resolve(self):
        """If a doc declares supersedes_doc_key, that doc_key must exist in the dataset."""
        all_keys = {parse_markdown(p)[0]["doc_key"] for p in all_source_files()}
        for path in all_source_files():
            meta, _ = parse_markdown(path)
            supersedes = meta.get("supersedes_doc_key")
            if supersedes:
                assert supersedes in all_keys, f"{path} supersedes unknown doc_key '{supersedes}'"

    def test_superseded_status_consistency(self):
        """Every doc that is the target of a 'supersedes' link should itself be status=superseded."""
        metas = {parse_markdown(p)[0]["doc_key"]: parse_markdown(p)[0] for p in all_source_files()}
        for meta in metas.values():
            supersedes = meta.get("supersedes_doc_key")
            if supersedes:
                assert metas[supersedes]["status"] == "superseded", (
                    f"{supersedes} is superseded by {meta['doc_key']} but not marked status=superseded"
                )


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

class TestChunking:

    def test_chunking_produces_at_least_one_chunk(self):
        for path in all_source_files():
            _, body = parse_markdown(path)
            chunks = chunk_document(body)
            assert len(chunks) >= 1, f"{path} produced zero chunks"

    def test_chunks_never_exceed_target_by_more_than_one_sentence(self):
        """Soft check: chunking packs greedily, so a single long sentence can push
        a chunk over target, but it should never be wildly oversized."""
        for path in all_source_files():
            _, body = parse_markdown(path)
            for c in chunk_document(body):
                assert len(c.split()) < 400, f"{path} produced an oversized chunk"

    def test_no_empty_chunks(self):
        for path in all_source_files():
            _, body = parse_markdown(path)
            for c in chunk_document(body):
                assert c.strip(), f"{path} produced an empty chunk"

    def test_sentence_split_is_non_trivial(self):
        _, body = parse_markdown(RAW_DIR / "it-security" / "it-security-policy-v2.md")
        sentences = split_into_sentences(body)
        assert len(sentences) > 5


# ---------------------------------------------------------------------------
# Ground truth integrity (references real doc_keys, valid JSON structure)
# ---------------------------------------------------------------------------

class TestGroundTruth:

    @pytest.fixture(scope="class")
    @classmethod
    def all_doc_keys(cls):
        return {parse_markdown(p)[0]["doc_key"] for p in all_source_files()}

    def test_ground_truth_files_exist(self):
        for name in ["duplicates.json", "contradictions.json", "outdated.json", "definitions.json", "queries.json"]:
            assert (GT_DIR / name).exists(), f"Missing ground truth file: {name}"

    def test_duplicates_reference_real_docs(self, all_doc_keys):
        data = json.loads((GT_DIR / "duplicates.json").read_text())
        assert len(data["cases"]) >= 2
        for case in data["cases"]:
            assert case["doc_a"] in all_doc_keys
            assert case["doc_b"] in all_doc_keys

    def test_contradictions_reference_real_docs(self, all_doc_keys):
        data = json.loads((GT_DIR / "contradictions.json").read_text())
        assert len(data["cases"]) >= 2
        for case in data["cases"]:
            assert case["doc_a"] in all_doc_keys
            assert case["doc_b"] in all_doc_keys
            assert case["resolved_doc_key"] in all_doc_keys

    def test_outdated_reference_real_docs(self, all_doc_keys):
        data = json.loads((GT_DIR / "outdated.json").read_text())
        assert len(data["cases"]) >= 2
        for case in data["cases"]:
            assert case["outdated_doc"] in all_doc_keys
            assert case["current_doc"] in all_doc_keys

    def test_definitions_reference_real_docs(self, all_doc_keys):
        data = json.loads((GT_DIR / "definitions.json").read_text())
        assert len(data["cases"]) >= 1
        for case in data["cases"]:
            assert case["doc_a"] in all_doc_keys
            assert case["doc_b"] in all_doc_keys

    def test_queries_reference_real_docs(self, all_doc_keys):
        data = json.loads((GT_DIR / "queries.json").read_text())
        assert len(data["queries"]) >= 10
        for q in data["queries"]:
            assert len(q["relevant_docs"]) >= 1
            for doc_key in q["relevant_docs"]:
                assert doc_key in all_doc_keys, f"{q['query_id']} references unknown doc_key '{doc_key}'"

    def test_snippets_are_verbatim_substrings_of_chunks(self, all_doc_keys):
        """Every hand-labeled snippet must actually occur (after chunking) in the
        document it claims to come from -- catches drift between the source
        markdown and the ground truth files."""
        chunk_cache = {}

        def chunks_for(doc_key):
            if doc_key not in chunk_cache:
                path = next(p for p in all_source_files() if parse_markdown(p)[0]["doc_key"] == doc_key)
                _, body = parse_markdown(path)
                chunk_cache[doc_key] = [" ".join(c.split()) for c in chunk_document(body)]
            return chunk_cache[doc_key]

        def assert_found(doc_key, snippet, case_id):
            normalized = " ".join(snippet.split())
            found = any(normalized in c for c in chunks_for(doc_key))
            assert found, f"{case_id}: snippet not found in {doc_key}: {snippet[:60]}..."

        dup = json.loads((GT_DIR / "duplicates.json").read_text())
        for case in dup["cases"]:
            assert_found(case["doc_a"], case["snippet_a"], case["case_id"])
            assert_found(case["doc_b"], case["snippet_b"], case["case_id"])

        conf = json.loads((GT_DIR / "contradictions.json").read_text())
        for case in conf["cases"]:
            assert_found(case["doc_a"], case["snippet_a"], case["case_id"])
            assert_found(case["doc_b"], case["snippet_b"], case["case_id"])

        defs = json.loads((GT_DIR / "definitions.json").read_text())
        for case in defs["cases"]:
            assert_found(case["doc_a"], case["definition_a"], case["case_id"])
            assert_found(case["doc_b"], case["definition_b"], case["case_id"])
