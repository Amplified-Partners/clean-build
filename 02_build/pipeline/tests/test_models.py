"""
Tests for pipeline data models.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from ..models import (
    Classification,
    IngestResult,
    PipelineItem,
    PipelineStats,
    PuddingTaxonomy,
)


def test_pudding_taxonomy_defaults():
    t = PuddingTaxonomy()
    assert t.type == "principle"
    assert t.dimensions == []
    assert t.confidence == 0.0


def test_classification_value():
    c = Classification(include=True, value="high", reason="test")
    assert c.include is True
    assert c.value == "high"


def test_pipeline_item_compute_hash(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("Hello world")
    item = PipelineItem(file_path=str(f))
    h = item.compute_hash()
    assert len(h) == 64  # SHA-256 hex
    assert item.file_hash == h


def test_ingest_result_success():
    r = IngestResult(file_path="batch", falkordb_created=10, qdrant_created=10)
    assert r.success is True

    r2 = IngestResult(file_path="batch", errors=["fail"])
    assert r2.success is False


def test_pipeline_stats_fps():
    s = PipelineStats(classified=100, elapsed_seconds=10.0)
    assert s.files_per_second == 10.0

    s2 = PipelineStats(classified=100, elapsed_seconds=0.0)
    assert s2.files_per_second == 0.0
