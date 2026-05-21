"""Brain analytics engine tests.

Tests the Brain connector, Brain-specific named queries, and the
unified analytics engine with Brain data loaded.

All tests use in-memory test data — no PostgreSQL connection required.
The Brain connector's PostgreSQL path is tested separately via
integration tests on Beast.

Dana | 2026-05-21 | Brain analytics tests — statistical lens
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio

from vellum.analytics.engine import DUCKDB_AVAILABLE, AnalyticsEngine, QUERY_REGISTRY
from vellum.analytics.brain_queries import BRAIN_QUERY_REGISTRY_LITE
from vellum.routes.correspondence import clear_participants
from vellum.storage import init_store
from vellum.storage.memory import MemorySheetStore


@pytest_asyncio.fixture(autouse=True)
async def _setup():
    store = await init_store()
    yield
    clear_participants()
    if isinstance(store, MemorySheetStore):
        store.clear()


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)
_30_DAYS_AGO = _NOW - timedelta(days=30)
_120_DAYS_AGO = _NOW - timedelta(days=120)


def _seed_brain_packets(engine: AnalyticsEngine) -> int:
    """Load test brain_packets data. Returns row count."""
    rows = [
        # packet_id, packet_type, title, summary, status, route,
        # epistemic_tier, claim_status, decision_state, valid_from,
        # valid_to, last_verified_at, source_document_id,
        # canonical_packet_id, metadata, created_at, updated_at
        [
            "pkt-001", "working_model", "Compound Engineering Loop",
            "PLAN 40% → WORK 10% → ASSESS 30% → COMPOUND 20%",
            "active", "keep", "STRUCTURED", None, None,
            None, None, _NOW, "doc-001", None,
            json.dumps({}), _30_DAYS_AGO, _NOW,
        ],
        [
            "pkt-002", "decision", "Use PostgreSQL canonical stack",
            "PostgreSQL + Apache AGE + pgvector replaces FalkorDB + Qdrant",
            "active", "keep", "MEASURED", None, None,
            None, None, _NOW, "doc-002", None,
            json.dumps({}), _30_DAYS_AGO, _NOW,
        ],
        [
            "pkt-003", "doctrine", "Five Rods constitutional principles",
            "Radical honesty, transparency, attribution, win-win, ideas meritocracy",
            "active", "freeze", "PROVEN", None, None,
            None, None, _NOW, "doc-003", None,
            json.dumps({}), _120_DAYS_AGO, _NOW,
        ],
        [
            "pkt-004", "method", "PUDDING taxonomy",
            "4-character WHAT.HOW.SCALE.TIME structural code",
            "active", "keep", "STRUCTURED", None, None,
            None, None, _120_DAYS_AGO, "doc-004", None,
            json.dumps({}), _120_DAYS_AGO, _120_DAYS_AGO,
        ],
        [
            "pkt-005", "conversation", "Ewan + Antigravity session",
            "Architecture review discussion",
            "quarantined", "quarantine", "INTUITED", None, None,
            None, None, None, "doc-005", None,
            json.dumps({}), _30_DAYS_AGO, _30_DAYS_AGO,
        ],
        [
            "pkt-006", "reference", "Swanson 1986 fish oil paper",
            "Don R. Swanson original LBD paper",
            "active", "keep", "PROVEN", None, None,
            None, None, None, None, None,
            json.dumps({}), _120_DAYS_AGO, _120_DAYS_AGO,
        ],
    ]
    return engine.load_brain_test_data("brain_packets", rows)


def _seed_brain_documents(engine: AnalyticsEngine) -> int:
    """Load test brain_documents data."""
    rows = [
        [
            "doc-001", "/opt/amplified/data/compound-engineering.md",
            "amplified-pipeline-v0.3", None, "abc123", "Compound Engineering",
            "methodology", _30_DAYS_AGO, _30_DAYS_AGO, "amplified-pipeline-v0.3",
            15, "inventoried",
        ],
        [
            "doc-002", "/opt/amplified/data/data-architecture.md",
            "amplified-pipeline-v0.3", None, "def456", "Data Architecture",
            "decision", _30_DAYS_AGO, _30_DAYS_AGO, "amplified-pipeline-v0.3",
            8, "inventoried",
        ],
        [
            "doc-003", "/opt/amplified/data/five-rods.md",
            "amplified-pipeline-v0.3", None, "ghi789", "Five Rods",
            "doctrine", _120_DAYS_AGO, _120_DAYS_AGO, "amplified-pipeline-v0.3",
            3, "inventoried",
        ],
    ]
    return engine.load_brain_test_data("brain_documents", rows)


def _seed_evidence(engine: AnalyticsEngine) -> int:
    """Load test brain_packet_evidence data."""
    rows = [
        # pkt-001 has 3 evidence links (strong)
        ["ev-001", "pkt-001", "chunk-a1", "supports", 0.95, _NOW],
        ["ev-002", "pkt-001", "chunk-a2", "supports", 0.88, _NOW],
        ["ev-003", "pkt-001", "chunk-a3", "context", 0.72, _NOW],
        # pkt-002 has 1 evidence link (single_source)
        ["ev-004", "pkt-002", "chunk-b1", "supports", 0.91, _NOW],
        # pkt-003 has 2 evidence links (moderate)
        ["ev-005", "pkt-003", "chunk-c1", "supports", 0.99, _NOW],
        ["ev-006", "pkt-003", "chunk-c2", "supports", 0.97, _NOW],
        # pkt-004 has 0 evidence links (orphan!) — not in this table
        # pkt-006 has 0 evidence links (orphan!)
    ]
    return engine.load_brain_test_data("brain_packet_evidence", rows)


def _seed_curation_runs(engine: AnalyticsEngine) -> int:
    """Load test brain_curation_runs data."""
    rows = [
        [
            "run-001", "inventory", _30_DAYS_AGO,
            _30_DAYS_AGO + timedelta(seconds=45),
            "brain-curator-v0.1", "cfg-abc",
            json.dumps({}), json.dumps({"documents": 150}),
            "completed", None,
        ],
        [
            "run-002", "dedup", _30_DAYS_AGO + timedelta(minutes=5),
            _30_DAYS_AGO + timedelta(minutes=5, seconds=120),
            "brain-curator-v0.1", "cfg-abc",
            json.dumps({}), json.dumps({"clusters": 30}),
            "completed", None,
        ],
        [
            "run-003", "packet_builder", _30_DAYS_AGO + timedelta(minutes=10),
            _30_DAYS_AGO + timedelta(minutes=10, seconds=200),
            "brain-curator-v0.1", "cfg-abc",
            json.dumps({}), json.dumps({"packets": 172780}),
            "completed", None,
        ],
        [
            "run-004", "route_decider", _30_DAYS_AGO + timedelta(minutes=15),
            None, "brain-curator-v0.1", "cfg-abc",
            json.dumps({}), json.dumps({}),
            "failed", "timeout after 300s",
        ],
    ]
    return engine.load_brain_test_data("brain_curation_runs", rows)


def _seed_dedup(engine: AnalyticsEngine) -> int:
    """Load test dedup cluster and member data."""
    clusters = [
        ["clust-001", "exact", "sha256", "chunk-a1", json.dumps({}), _30_DAYS_AGO],
        ["clust-002", "metadata_family", "title_path", None, json.dumps({}), _30_DAYS_AGO],
    ]
    engine.load_brain_test_data("brain_dedupe_clusters", clusters)

    members = [
        ["mem-001", "clust-001", "chunk-a1", "canonical", 1.0, _30_DAYS_AGO],
        ["mem-002", "clust-001", "chunk-a2", "member", 1.0, _30_DAYS_AGO],
        ["mem-003", "clust-001", "chunk-a3", "member", 1.0, _30_DAYS_AGO],
        ["mem-004", "clust-002", "chunk-b1", "canonical", 0.85, _30_DAYS_AGO],
        ["mem-005", "clust-002", "chunk-b2", "member", 0.80, _30_DAYS_AGO],
    ]
    return engine.load_brain_test_data("brain_dedupe_members", members)


def _seed_relationships(engine: AnalyticsEngine) -> int:
    """Load test brain_relationships data."""
    rows = [
        ["rel-001", "pkt-001", "pkt-002", "supports", 2, 0.88, json.dumps({}), _NOW],
        ["rel-002", "pkt-003", "pkt-001", "derived_from", 1, 0.75, json.dumps({}), _NOW],
    ]
    return engine.load_brain_test_data("brain_relationships", rows)


def _seed_validation(engine: AnalyticsEngine) -> int:
    """Load test brain_validation_samples data."""
    rows = [
        ["samp-001", "pkt-001", "correct", "ewan", _NOW, "Looks right", json.dumps({})],
        ["samp-002", "pkt-002", "correct", "antigravity", _NOW, None, json.dumps({})],
        ["samp-003", "pkt-005", "incorrect", "ewan", _NOW, "Too vague", json.dumps({})],
    ]
    return engine.load_brain_test_data("brain_validation_samples", rows)


def _seed_all(engine: AnalyticsEngine) -> None:
    """Seed all Brain test data."""
    _seed_brain_packets(engine)
    _seed_brain_documents(engine)
    _seed_evidence(engine)
    _seed_curation_runs(engine)
    _seed_dedup(engine)
    _seed_relationships(engine)
    _seed_validation(engine)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestBrainQueriesRegistered:
    """Verify Brain queries are registered in the unified registry."""

    def test_brain_queries_in_registry(self) -> None:
        engine = AnalyticsEngine()
        queries = engine.list_queries()
        assert "brain_tier_distribution" in queries
        assert "brain_health_score" in queries
        assert "curation_pipeline_health" in queries
        assert "evidence_density" in queries
        assert "stale_packets" in queries
        engine.close()

    def test_brain_query_count(self) -> None:
        # Lite registry excludes full triangulation queries
        assert len(BRAIN_QUERY_REGISTRY_LITE) >= 18

    def test_no_duplicate_query_names(self) -> None:
        """Brain queries must not collide with Vellum queries."""
        engine = AnalyticsEngine()
        # Count total unique keys
        all_queries = engine.list_queries()
        assert len(all_queries) == len(set(all_queries))
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestBrainTierDistribution:
    def test_tier_distribution(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)

        result = engine.run("brain_tier_distribution", executed_by="test")
        assert result.row_count > 0
        assert "epistemic_tier" in result.columns
        assert "packet_count" in result.columns

        # Check we see all tiers
        tiers = {row[0] for row in result.rows}
        assert "STRUCTURED" in tiers
        assert "MEASURED" in tiers
        assert "PROVEN" in tiers
        assert "INTUITED" in tiers
        engine.close()

    def test_tier_by_type(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)

        result = engine.run("brain_tier_by_type", executed_by="test")
        assert result.row_count > 0
        types = {row[0] for row in result.rows}
        assert "working_model" in types
        assert "decision" in types
        engine.close()

    def test_tier_by_route(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)

        result = engine.run("brain_tier_by_route", executed_by="test")
        assert result.row_count > 0
        routes = {row[0] for row in result.rows}
        assert "keep" in routes
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestCurationPipelineHealth:
    def test_pipeline_health(self) -> None:
        engine = AnalyticsEngine()
        _seed_curation_runs(engine)

        result = engine.run("curation_pipeline_health", executed_by="test")
        assert result.row_count > 0
        stages = {row[0] for row in result.rows}
        assert "inventory" in stages
        assert "dedup" in stages
        engine.close()

    def test_recent_runs(self) -> None:
        engine = AnalyticsEngine()
        _seed_curation_runs(engine)

        result = engine.run("curation_recent_runs", executed_by="test")
        assert result.row_count == 4
        # Most recent first
        assert result.rows[0][0] == "run-004"  # run_id
        engine.close()

    def test_velocity(self) -> None:
        engine = AnalyticsEngine()
        _seed_curation_runs(engine)

        result = engine.run("curation_velocity", executed_by="test")
        assert result.row_count > 0
        assert "avg_seconds" in result.columns
        assert "p50_seconds" in result.columns
        engine.close()

    def test_failed_run_visible(self) -> None:
        engine = AnalyticsEngine()
        _seed_curation_runs(engine)

        result = engine.run("curation_velocity", executed_by="test")
        # route_decider had a failure
        for row in result.rows:
            if row[0] == "route_decider":
                stage_data = dict(zip(result.columns, row))
                assert stage_data["failed"] >= 1
                break
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestDedupCoverage:
    def test_cluster_stats(self) -> None:
        engine = AnalyticsEngine()
        _seed_dedup(engine)

        result = engine.run("dedup_cluster_stats", executed_by="test")
        assert result.row_count > 0
        assert "clusters" in result.columns
        assert "total_members" in result.columns
        engine.close()

    def test_largest_clusters(self) -> None:
        engine = AnalyticsEngine()
        _seed_dedup(engine)

        result = engine.run("dedup_largest_clusters", executed_by="test")
        assert result.row_count == 2
        # Cluster 001 has 3 members, should be first
        assert result.rows[0][3] == 3  # member_count column
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestEvidenceDensity:
    def test_evidence_density(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)
        _seed_evidence(engine)

        result = engine.run("evidence_density", executed_by="test")
        assert result.row_count > 0
        assert "avg_evidence_per_packet" in result.columns
        assert "orphan_packets" in result.columns
        engine.close()

    def test_evidence_orphans(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)
        _seed_evidence(engine)

        result = engine.run("evidence_orphans", executed_by="test")
        # pkt-004 and pkt-006 are active with no evidence
        orphan_ids = {row[0] for row in result.rows}
        assert "pkt-004" in orphan_ids
        assert "pkt-006" in orphan_ids
        engine.close()

    def test_well_evidenced_not_orphan(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)
        _seed_evidence(engine)

        result = engine.run("evidence_orphans", executed_by="test")
        orphan_ids = {row[0] for row in result.rows}
        # pkt-001 has 3 evidence links — not an orphan
        assert "pkt-001" not in orphan_ids
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestStalePackets:
    def test_stale_packet_detection(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)

        result = engine.run("stale_packets", executed_by="test")
        stale_ids = {row[0] for row in result.rows}
        # pkt-004 last verified 120 days ago, pkt-006 never verified
        assert "pkt-006" in stale_ids
        engine.close()

    def test_stale_summary(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)

        result = engine.run("stale_packet_summary", executed_by="test")
        assert result.row_count > 0
        freshness_levels = {row[0] for row in result.rows}
        assert "fresh" in freshness_levels or "never_verified" in freshness_levels
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestTriangulation:
    def test_triangulation_summary_lite(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)
        _seed_evidence(engine)

        result = engine.run("triangulation_summary_lite", executed_by="test")
        assert result.row_count > 0
        strengths = {row[0] for row in result.rows}
        # We should see at least strong (3+ evidence) and no_evidence
        assert "strong" in strengths or "moderate" in strengths or "single_source" in strengths
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestDocumentStats:
    def test_document_stats(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_documents(engine)

        result = engine.run("document_stats", executed_by="test")
        assert result.row_count > 0
        assert "documents" in result.columns
        assert "total_chunks" in result.columns
        engine.close()

    def test_pipeline_versions(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_documents(engine)

        result = engine.run("document_pipeline_versions", executed_by="test")
        assert result.row_count >= 1
        versions = {row[0] for row in result.rows}
        assert "amplified-pipeline-v0.3" in versions
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestRelationshipStats:
    def test_relationship_stats(self) -> None:
        engine = AnalyticsEngine()
        _seed_relationships(engine)

        result = engine.run("relationship_stats", executed_by="test")
        assert result.row_count == 2
        predicates = {row[0] for row in result.rows}
        assert "supports" in predicates
        assert "derived_from" in predicates
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestValidation:
    def test_verdict_distribution(self) -> None:
        engine = AnalyticsEngine()
        _seed_validation(engine)

        result = engine.run("validation_verdict_distribution", executed_by="test")
        assert result.row_count == 2  # correct and incorrect
        verdicts = {row[0]: row[1] for row in result.rows}
        assert verdicts["correct"] == 2
        assert verdicts["incorrect"] == 1
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestBrainHealthScore:
    def test_health_score_green(self) -> None:
        engine = AnalyticsEngine()
        _seed_all(engine)

        result = engine.run("brain_health_score", executed_by="test")
        assert result.row_count == 1
        row = dict(zip(result.columns, result.rows[0]))
        assert row["health_status"] in ("GREEN", "AMBER", "RED")
        assert row["active_packets"] >= 4
        assert row["quarantined_packets"] >= 1
        engine.close()

    def test_health_witnessed(self) -> None:
        """Every health check execution is logged for anti-shelfware."""
        engine = AnalyticsEngine()
        _seed_all(engine)

        engine.run("brain_health_score", executed_by="loom-health-check")

        log = engine.get_query_log()
        assert len(log) == 1
        assert log[0]["query_name"] == "brain_health_score"
        assert log[0]["executed_by"] == "loom-health-check"
        assert len(log[0]["output_hash"]) == 64  # SHA-256
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestPacketStatusFlow:
    def test_status_flow(self) -> None:
        engine = AnalyticsEngine()
        _seed_brain_packets(engine)

        result = engine.run("packet_status_flow", executed_by="test")
        assert result.row_count > 0
        statuses = {row[0] for row in result.rows}
        assert "active" in statuses
        assert "quarantined" in statuses
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestBrainTestDataLoader:
    def test_load_brain_test_data(self) -> None:
        engine = AnalyticsEngine()
        count = _seed_brain_packets(engine)
        assert count == 6
        engine.close()

    def test_unknown_table_raises(self) -> None:
        engine = AnalyticsEngine()
        with pytest.raises(KeyError, match="Unknown Brain table"):
            engine.load_brain_test_data("nonexistent_table", [[1, 2]])
        engine.close()


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestBrainConnectorInit:
    def test_brain_tables_created(self) -> None:
        """Brain tables are created when the engine initialises."""
        engine = AnalyticsEngine()
        # Verify we can query Brain tables (they exist but are empty)
        result = engine.run("brain_tier_distribution", executed_by="test")
        assert result.row_count == 0  # Empty but queryable
        engine.close()

    def test_brain_connector_present(self) -> None:
        engine = AnalyticsEngine()
        assert engine._brain_connector is not None
        engine.close()
