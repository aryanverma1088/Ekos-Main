"""
API tests for the Phase 1-2 endpoints (documents, dashboard).

These run against the same SQLite DB used by scripts/ingest.py. Run
`python scripts/ingest.py --reset` before this suite if you want a known-
clean 18-document baseline; test_upload_and_dedupe cleans up after itself
either way.

Run with:  cd ekos/backend && pytest ../tests/test_api.py -v
(or from repo root: pytest tests/test_api.py -v)
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app                        # noqa: E402
from db import get_session                  # noqa: E402
from models import Document                 # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_documents_returns_seed_dataset():
    r = client.get("/documents")
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) >= 18
    # spot check required fields are present on every item
    for d in docs:
        assert d["doc_key"]
        assert d["department"]
        assert 1 <= d["authority_level"] <= 6


def test_filter_by_department():
    r = client.get("/documents", params={"department": "HR"})
    docs = r.json()
    assert len(docs) >= 5
    assert all(d["department"] == "HR" for d in docs)


def test_filter_by_status_superseded():
    r = client.get("/documents", params={"status": "superseded"})
    docs = r.json()
    assert len(docs) >= 2
    keys = {d["doc_key"] for d in docs}
    assert "hr-remote-work-policy-v3" in keys
    assert "finance-expense-policy-v1" in keys


def test_document_detail_includes_chunks():
    r = client.get("/documents")
    first_id = r.json()[0]["id"]
    detail = client.get(f"/documents/{first_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert "raw_text" in body
    assert len(body["chunks"]) >= 1


def test_document_not_found():
    r = client.get("/documents/999999")
    assert r.status_code == 404


def test_upload_and_dedupe_then_cleanup():
    new_doc = """---
doc_key: test-temp-doc
title: Temporary Test Document
department: HR
doc_type: Policy
version: "1.0"
created_date: 2024-01-01
effective_date: 2024-01-01
updated_date: 2024-01-01
author: Test Author
owner: HR
authority_level: 3
status: current
supersedes: null
tags: test
---

# Temporary Test Document

This document exists only to exercise the upload endpoint in tests and is
removed at the end of the test.
"""
    files = {"file": ("test-temp-doc.md", new_doc, "text/markdown")}

    try:
        r1 = client.post("/documents/upload", files=files)
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["status"] == "ingested"
        assert body1["chunks_created"] >= 1

        # re-uploading the same doc_key should be detected as a duplicate, not double-inserted
        r2 = client.post("/documents/upload", files=files)
        body2 = r2.json()
        assert body2["status"] == "skipped_duplicate"
        assert body2["chunks_created"] == 0
        assert body2["id"] == body1["id"]
    finally:
        # clean up so this test doesn't permanently pollute the dev database
        session = get_session()
        doc = session.query(Document).filter_by(doc_key="test-temp-doc").first()
        if doc:
            session.delete(doc)
            session.commit()
        session.close()


def test_upload_rejects_non_markdown():
    files = {"file": ("not-a-doc.txt", "hello", "text/plain")}
    r = client.post("/documents/upload", files=files)
    assert r.status_code == 400


def test_dashboard_metrics_are_live_not_hardcoded():
    r = client.get("/dashboard/metrics")
    assert r.status_code == 200
    metrics = r.json()
    assert metrics["documents"] >= 18
    assert sum(metrics["documents_by_department"].values()) == metrics["documents"]
    # Phase 5 (knowledge graph) and Phase 6 (integrity engine) are both implemented.
    # These must reflect REAL detector output, not fabricated numbers (project spec Rule 4) --
    # exact values are asserted in tests/test_integrity_api.py against the known corpus;
    # here we just check the field exists and is non-negative.
    assert metrics["conflicts"] >= 0
    assert "note" in metrics and len(metrics["note"]) > 0
