"""
Tests for integrity/duplicates, integrity/contradictions, integrity/versions,
integrity/definitions. Use small controlled fixtures rather than the real
corpus, so these tests are fast, deterministic, and test the detection
LOGIC in isolation from the real dataset's specific (and, per
integrity/FINDINGS.md, sometimes disappointing) similarity scores.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from integrity.contradictions.numeric_fact_extractor import extract_numeric_facts  # noqa: E402
from integrity.contradictions.contradiction_detector import detect_contradictions   # noqa: E402
from integrity.duplicates.duplicate_detector import detect_duplicates, UnionFind     # noqa: E402
from integrity.versions.outdated_detector import detect_outdated, find_supersedes_document_id_pairs  # noqa: E402
from integrity.definitions.definition_conflict_detector import extract_definitions, detect_definition_conflicts  # noqa: E402


class TestNumericFactExtractor:

    def test_extracts_days(self):
        facts = extract_numeric_facts("Passwords must be changed every 90 days.")
        assert len(facts) == 1
        assert facts[0]["value"] == 90
        assert facts[0]["unit"] == "days"

    def test_extracts_dollars_with_commas(self):
        facts = extract_numeric_facts("Purchases above $10,000 require sign-off.")
        assert facts[0]["value"] == 10000
        assert facts[0]["unit"] == "dollars"

    def test_same_context_produces_matching_keys(self):
        a = extract_numeric_facts("Passwords must be changed every 90 days.")
        b = extract_numeric_facts("Passwords must be changed every 180 days under standard settings.")
        assert a[0]["context_key"] == b[0]["context_key"]

    def test_different_context_produces_different_keys(self):
        a = extract_numeric_facts("Employees accrue 22 days of annual leave.")
        b = extract_numeric_facts("Passwords must be changed every 90 days.")
        assert a[0]["context_key"] != b[0]["context_key"]

    def test_no_facts_in_plain_text(self):
        assert extract_numeric_facts("This policy has no numbers in it at all.") == []


class TestContradictionDetector:

    def _chunk(self, chunk_id, document_id, doc_key, department, authority_level, text):
        return {"chunk_id": chunk_id, "document_id": document_id, "doc_key": doc_key,
                "department": department, "authority_level": authority_level, "text": text}

    def test_detects_differing_value_same_concept(self):
        chunks = [
            self._chunk(1, 1, "policy-a", "IT-Security", 1, "Passwords must be changed every 90 days."),
            self._chunk(2, 2, "policy-b", "IT-Security", 3, "Passwords must be changed every 180 days."),
        ]
        results = detect_contradictions(chunks, supersedes_doc_pairs=set())
        assert len(results) == 1
        assert results[0]["value_a"] == "90 days" or results[0]["value_b"] == "90 days"
        assert results[0]["resolved_doc_key"] == "policy-a"  # lower authority_level number wins
        assert results[0]["severity"] == "high"  # "password"/"security" keyword

    def test_same_value_is_not_a_contradiction(self):
        chunks = [
            self._chunk(1, 1, "policy-a", "HR", 1, "Employees accrue 22 days of leave."),
            self._chunk(2, 2, "policy-b", "HR", 1, "Employees accrue 22 days of leave, per policy."),
        ]
        results = detect_contradictions(chunks, supersedes_doc_pairs=set())
        assert results == []

    def test_supersedes_pair_excluded(self):
        chunks = [
            self._chunk(1, 1, "policy-v1", "Finance", 1, "Reimbursement limit is $150 per month."),
            self._chunk(2, 2, "policy-v2", "Finance", 1, "Reimbursement limit is $250 per month."),
        ]
        results = detect_contradictions(chunks, supersedes_doc_pairs={(1, 2)})
        assert results == []

    def test_same_document_not_flagged(self):
        chunks = [
            self._chunk(1, 1, "policy-a", "Finance", 1, "Purchases under $1,000 need no approval, and purchases under $1,000 are common."),
        ]
        results = detect_contradictions(chunks, supersedes_doc_pairs=set())
        assert results == []

    def test_qualitative_contradiction_not_caught_by_design(self):
        """Documented limitation (integrity/FINDINGS.md): non-numeric
        contradictions aren't detected by this rule-based fallback."""
        chunks = [
            self._chunk(1, 1, "policy-a", "IT-Security", 1, "Access requires manager approval for all engineers."),
            self._chunk(2, 2, "policy-b", "Engineering", 2, "Senior engineers get standing access without approval."),
        ]
        results = detect_contradictions(chunks, supersedes_doc_pairs=set())
        assert results == []  # documented miss, not a bug


class TestDuplicateDetector:

    def test_near_identical_text_detected(self):
        chunks = [
            (1, 1, "All company laptops must have full-disk encryption enabled before deployment to staff."),
            (2, 2, "All company laptops must have full disk encryption enabled before being deployed to staff."),
        ]
        results = detect_duplicates(chunks, supersedes_doc_pairs=set(), threshold=0.5)
        assert len(results) == 1
        assert results[0]["chunk_a_id"] == 1
        assert results[0]["chunk_b_id"] == 2

    def test_unrelated_text_not_flagged(self):
        chunks = [
            (1, 1, "Employees may take parental leave for eighteen weeks."),
            (2, 2, "Production database access requires manager approval and an access ticket."),
        ]
        results = detect_duplicates(chunks, supersedes_doc_pairs=set(), threshold=0.5)
        assert results == []

    def test_same_document_pairs_excluded(self):
        chunks = [
            (1, 1, "This is the policy text repeated for testing purposes here."),
            (2, 1, "This is the policy text repeated for testing purposes here."),  # same document_id
        ]
        results = detect_duplicates(chunks, supersedes_doc_pairs=set(), threshold=0.5)
        assert results == []

    def test_supersedes_pair_excluded_even_if_near_identical(self):
        chunks = [
            (1, 1, "Employees may work remotely up to two days per week with approval."),
            (2, 2, "Employees may work remotely up to three days per week with approval."),
        ]
        results = detect_duplicates(chunks, supersedes_doc_pairs={(1, 2)}, threshold=0.3)
        assert results == []

    def test_union_find_clusters_transitively(self):
        uf = UnionFind([1, 2, 3, 4])
        uf.union(1, 2)
        uf.union(2, 3)
        assert uf.find(1) == uf.find(3)
        assert uf.find(1) != uf.find(4)


class TestOutdatedDetector:

    def test_detects_supersession_chain(self):
        docs = [
            {"doc_key": "policy-v3", "status": "superseded", "supersedes_doc_key": None, "title": "Remote Work Policy"},
            {"doc_key": "policy-v4", "status": "current", "supersedes_doc_key": "policy-v3", "title": "Remote Work Policy"},
        ]
        results = detect_outdated(docs)
        assert len(results) == 1
        assert results[0]["outdated_doc_key"] == "policy-v3"
        assert results[0]["current_doc_key"] == "policy-v4"

    def test_no_supersedes_no_findings(self):
        docs = [{"doc_key": "policy-a", "status": "current", "supersedes_doc_key": None, "title": "A"}]
        assert detect_outdated(docs) == []

    def test_find_supersedes_document_id_pairs(self):
        docs = [
            {"id": 10, "doc_key": "policy-v3", "supersedes_doc_key": None},
            {"id": 11, "doc_key": "policy-v4", "supersedes_doc_key": "policy-v3"},
        ]
        pairs = find_supersedes_document_id_pairs(docs)
        assert pairs == {(11, 10)}


class TestDefinitionExtraction:

    def test_extracts_is_defined_as(self):
        text = "For reporting purposes, a Customer is defined as a paying account with an active contract."
        defs = extract_definitions(text)
        assert len(defs) == 1
        assert defs[0]["term"] == "Customer"
        assert "paying account" in defs[0]["definition_text"]

    def test_extracts_means(self):
        text = "Churn means the cancellation of an active subscription before renewal."
        defs = extract_definitions(text)
        assert defs[0]["term"] == "Churn"

    def test_no_definitions_in_plain_text(self):
        assert extract_definitions("This policy has no formal definitions.") == []


class TestDefinitionConflictDetector:

    def _chunk(self, chunk_id, document_id, department, text):
        return {"chunk_id": chunk_id, "document_id": document_id, "department": department, "text": text}

    def test_detects_cross_department_conflict(self):
        chunks = [
            self._chunk(1, 1, "Finance", "A Customer is defined as a paying account with an active billed contract."),
            self._chunk(2, 2, "Marketing", "A Customer is defined as any qualified lead in the sales funnel."),
        ]
        results = detect_definition_conflicts(chunks)
        assert len(results) == 1
        assert results[0]["term"] == "Customer"

    def test_same_department_not_flagged(self):
        chunks = [
            self._chunk(1, 1, "Finance", "A Customer is defined as a paying account with a contract."),
            self._chunk(2, 2, "Finance", "A Customer is defined as an account holder with an active contract."),
        ]
        results = detect_definition_conflicts(chunks)
        assert results == []

    def test_similar_definitions_not_flagged_as_conflict(self):
        chunks = [
            self._chunk(1, 1, "Finance", "A Customer is defined as a paying account with an active billed contract with the company."),
            self._chunk(2, 2, "Sales", "A Customer is defined as a paying account with an active billed contract for services."),
        ]
        results = detect_definition_conflicts(chunks)
        assert results == []  # high word overlap -> not a meaningful conflict


class TestBuildIntegrityEngineIdempotency:
    """Regression test for a real bug: running scripts/build_integrity_engine.py
    without --reset used to insert a new Conflict/Duplicate row for every
    detected case on EVERY run, with no check for an existing row -- so two
    runs in a row silently doubled every case shown in the API and the
    Integrity Center UI. Caught by visually inspecting the rendered page
    (duplicate case cards appeared), not by any test that existed at the
    time. Runs the actual script's run() function against the real project
    DB (same DB the rest of this test file already depends on being
    pre-built) and confirms a second run without --reset doesn't change
    the row counts."""

    def test_running_twice_does_not_duplicate_conflicts_or_duplicates(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_integrity_engine", ROOT / "scripts" / "build_integrity_engine.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        session = mod.get_session()
        from models import Conflict, Duplicate
        before_conflicts = session.query(Conflict).count()
        before_duplicates = session.query(Duplicate).count()
        session.close()

        assert before_conflicts > 0, "expected the real project DB to already have detected conflicts"

        mod.run(reset=False)

        session = mod.get_session()
        after_conflicts = session.query(Conflict).count()
        after_duplicates = session.query(Duplicate).count()
        session.close()

        assert after_conflicts == before_conflicts, "Conflicts were duplicated by a second run without --reset"
        assert after_duplicates == before_duplicates, "Duplicates were duplicated by a second run without --reset"
