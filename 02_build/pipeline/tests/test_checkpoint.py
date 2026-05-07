"""
Tests for the checkpoint store.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

import pytest

from ..checkpoint import CheckpointStore
from ..models import Classification, ItemStatus, PuddingTaxonomy


@pytest.fixture
def store(tmp_path):
    return CheckpointStore(tmp_path / "test.db")


def test_register_and_count(store):
    files = ["/tmp/a.md", "/tmp/b.md", "/tmp/c.md"]
    store.register_items(files)
    assert store.total_count() == 3
    counts = store.count_by_stage()
    assert counts.get("pending", 0) == 3


def test_register_idempotent(store):
    files = ["/tmp/a.md", "/tmp/b.md"]
    store.register_items(files)
    store.register_items(files)  # duplicate
    assert store.total_count() == 2


def test_update_item(store):
    store.register_items(["/tmp/a.md"])
    taxonomy = PuddingTaxonomy(
        type="framework",
        dimensions=["pricing", "sales"],
        expert="PORTER",
        actionable="ready_to_use",
        status="proven",
        confidence=0.92,
    )
    classification = Classification(include=True, value="high", reason="Ready to use + proven")

    store.update_item(
        "/tmp/a.md",
        ItemStatus.CLASSIFIED,
        file_hash="abc123",
        taxonomy=taxonomy,
        classification=classification,
    )

    item = store.get_item("/tmp/a.md")
    assert item is not None
    assert item.stage == ItemStatus.CLASSIFIED
    assert item.file_hash == "abc123"
    assert item.taxonomy.type == "framework"
    assert item.taxonomy.confidence == 0.92
    assert item.classification.value == "high"


def test_get_items_by_stage(store):
    store.register_items(["/tmp/a.md", "/tmp/b.md", "/tmp/c.md"])
    store.update_item("/tmp/a.md", ItemStatus.CLASSIFIED)
    store.update_item("/tmp/b.md", ItemStatus.FAILED, error="timeout")

    pending = store.get_items_by_stage(ItemStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].file_path == "/tmp/c.md"

    classified = store.get_items_by_stage(ItemStatus.CLASSIFIED)
    assert len(classified) == 1

    failed = store.get_items_by_stage(ItemStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].error == "timeout"


def test_run_meta(store):
    store.record_run_start("run_001", {"workers": 12})
    store.record_run_end("run_001")
