"""Brain-specific named queries for DuckDB analytics.

Statistical lens queries over the Brain's PostgreSQL tables.
Every query is named, registered, and witnessed. No ad-hoc SQL.

Covers:
  - Tier distribution and drift (the epistemic health of the Brain)
  - Curation pipeline health (stage-by-stage throughput)
  - Dedup coverage (cluster stats, canonical ratios)
  - Evidence density (claims vs supporting chunks)
  - Stale packet detection (unverified active knowledge)
  - Cross-source triangulation (independent corroboration)
  - Curation velocity (bottleneck detection via TOC)
  - Brain health traffic light (single-glance score)

Dana | 2026-05-21 | Brain analytics queries — statistical lens
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Brain query registry — named, no ad-hoc accumulation
# ---------------------------------------------------------------------------

BRAIN_QUERY_REGISTRY: dict[str, str] = {
    # -----------------------------------------------------------------------
    # 1. Epistemic tier distribution — the heartbeat of the Brain
    # -----------------------------------------------------------------------
    "brain_tier_distribution": """
        SELECT
            epistemic_tier,
            status,
            COUNT(*) as packet_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
        FROM brain_packets
        GROUP BY epistemic_tier, status
        ORDER BY epistemic_tier, packet_count DESC
    """,

    "brain_tier_by_type": """
        SELECT
            packet_type,
            epistemic_tier,
            COUNT(*) as count
        FROM brain_packets
        GROUP BY packet_type, epistemic_tier
        ORDER BY packet_type, count DESC
    """,

    "brain_tier_by_route": """
        SELECT
            route,
            epistemic_tier,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY route), 2) as pct_within_route
        FROM brain_packets
        WHERE route IS NOT NULL
        GROUP BY route, epistemic_tier
        ORDER BY route, count DESC
    """,

    # -----------------------------------------------------------------------
    # 2. Curation pipeline health — stage-by-stage throughput
    # -----------------------------------------------------------------------
    "curation_pipeline_health": """
        SELECT
            stage,
            status,
            COUNT(*) as runs,
            MIN(started_at) as first_run,
            MAX(started_at) as last_run,
            AVG(
                EPOCH(completed_at - started_at)
            ) as avg_duration_seconds,
            MAX(
                EPOCH(completed_at - started_at)
            ) as max_duration_seconds
        FROM brain_curation_runs
        WHERE completed_at IS NOT NULL
        GROUP BY stage, status
        ORDER BY stage, runs DESC
    """,

    "curation_recent_runs": """
        SELECT
            run_id,
            stage,
            started_at,
            completed_at,
            ROUND(EPOCH(completed_at - started_at), 1) as duration_seconds,
            status,
            code_version,
            error
        FROM brain_curation_runs
        ORDER BY started_at DESC
        LIMIT 50
    """,

    "curation_velocity": """
        SELECT
            stage,
            COUNT(*) as total_runs,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'failed' OR status = 'error') as failed,
            ROUND(
                AVG(EPOCH(completed_at - started_at)) FILTER (WHERE status = 'completed'),
                1
            ) as avg_seconds,
            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EPOCH(completed_at - started_at)
                ) FILTER (WHERE status = 'completed'),
                1
            ) as p50_seconds,
            ROUND(
                PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY EPOCH(completed_at - started_at)
                ) FILTER (WHERE status = 'completed'),
                1
            ) as p95_seconds
        FROM brain_curation_runs
        GROUP BY stage
        ORDER BY stage
    """,

    # -----------------------------------------------------------------------
    # 3. Dedup coverage — cluster stats
    # -----------------------------------------------------------------------
    "dedup_cluster_stats": """
        SELECT
            dc.cluster_type,
            dc.method,
            COUNT(DISTINCT dc.cluster_id) as clusters,
            COUNT(dm.member_id) as total_members,
            ROUND(AVG(member_counts.member_count), 1) as avg_cluster_size,
            MAX(member_counts.member_count) as max_cluster_size,
            COUNT(dm.member_id) FILTER (WHERE dm.member_role = 'canonical') as canonical_count
        FROM brain_dedupe_clusters dc
        LEFT JOIN brain_dedupe_members dm ON dc.cluster_id = dm.cluster_id
        LEFT JOIN (
            SELECT cluster_id, COUNT(*) as member_count
            FROM brain_dedupe_members
            GROUP BY cluster_id
        ) member_counts ON dc.cluster_id = member_counts.cluster_id
        GROUP BY dc.cluster_type, dc.method
        ORDER BY clusters DESC
    """,

    "dedup_largest_clusters": """
        SELECT
            dc.cluster_id,
            dc.cluster_type,
            dc.method,
            COUNT(dm.member_id) as member_count,
            MIN(dm.confidence) as min_confidence,
            AVG(dm.confidence) as avg_confidence
        FROM brain_dedupe_clusters dc
        JOIN brain_dedupe_members dm ON dc.cluster_id = dm.cluster_id
        GROUP BY dc.cluster_id, dc.cluster_type, dc.method
        ORDER BY member_count DESC
        LIMIT 25
    """,

    # -----------------------------------------------------------------------
    # 4. Evidence density — claims vs supporting chunks
    # -----------------------------------------------------------------------
    "evidence_density": """
        SELECT
            bp.packet_type,
            bp.epistemic_tier,
            COUNT(DISTINCT bp.packet_id) as packets,
            COUNT(bpe.evidence_id) as total_evidence_links,
            ROUND(
                COUNT(bpe.evidence_id) * 1.0 / NULLIF(COUNT(DISTINCT bp.packet_id), 0),
                2
            ) as avg_evidence_per_packet,
            COUNT(DISTINCT bp.packet_id) FILTER (
                WHERE bp.packet_id NOT IN (SELECT DISTINCT packet_id FROM brain_packet_evidence)
            ) as orphan_packets
        FROM brain_packets bp
        LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
        WHERE bp.status = 'active'
        GROUP BY bp.packet_type, bp.epistemic_tier
        ORDER BY orphan_packets DESC, packets DESC
    """,

    "evidence_orphans": """
        SELECT
            bp.packet_id,
            bp.packet_type,
            bp.title,
            bp.epistemic_tier,
            bp.status,
            bp.route,
            bp.created_at
        FROM brain_packets bp
        LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
        WHERE bpe.evidence_id IS NULL
          AND bp.status = 'active'
        ORDER BY bp.created_at DESC
        LIMIT 50
    """,

    # -----------------------------------------------------------------------
    # 5. Stale packet detection — unverified active knowledge
    # -----------------------------------------------------------------------
    "stale_packets": """
        SELECT
            packet_id,
            packet_type,
            title,
            epistemic_tier,
            status,
            route,
            last_verified_at,
            created_at,
            ROUND(
                EPOCH(now() - COALESCE(last_verified_at, created_at)) / 86400,
                0
            ) as days_since_verification
        FROM brain_packets
        WHERE status = 'active'
          AND (
              last_verified_at IS NULL
              OR last_verified_at < now() - INTERVAL '90 days'
          )
        ORDER BY days_since_verification DESC
        LIMIT 50
    """,

    "stale_packet_summary": """
        SELECT
            CASE
                WHEN last_verified_at IS NULL THEN 'never_verified'
                WHEN last_verified_at < now() - INTERVAL '180 days' THEN 'stale_180d'
                WHEN last_verified_at < now() - INTERVAL '90 days' THEN 'stale_90d'
                WHEN last_verified_at < now() - INTERVAL '30 days' THEN 'stale_30d'
                ELSE 'fresh'
            END as freshness,
            COUNT(*) as packet_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
        FROM brain_packets
        WHERE status = 'active'
        GROUP BY freshness
        ORDER BY packet_count DESC
    """,

    # -----------------------------------------------------------------------
    # 6. Cross-source triangulation — independent corroboration
    # -----------------------------------------------------------------------
    "triangulation_by_packet": """
        SELECT
            bp.packet_id,
            bp.packet_type,
            bp.title,
            bp.epistemic_tier,
            COUNT(DISTINCT bpe.chunk_id) as evidence_chunks,
            COUNT(DISTINCT kv.file_path) as distinct_source_files,
            CASE
                WHEN COUNT(DISTINCT kv.file_path) >= 3 THEN 'strong'
                WHEN COUNT(DISTINCT kv.file_path) = 2 THEN 'moderate'
                WHEN COUNT(DISTINCT kv.file_path) = 1 THEN 'single_source'
                ELSE 'no_evidence'
            END as corroboration_strength
        FROM brain_packets bp
        LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
        LEFT JOIN (
            SELECT id, file_path FROM knowledge_vectors
            UNION ALL
            SELECT id, file_path FROM knowledge_vectors_legacy
        ) kv ON bpe.chunk_id = kv.id
        WHERE bp.status = 'active'
        GROUP BY bp.packet_id, bp.packet_type, bp.title, bp.epistemic_tier
        ORDER BY distinct_source_files DESC
        LIMIT 50
    """,

    "triangulation_summary": """
        SELECT
            corroboration_strength,
            COUNT(*) as packet_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
        FROM (
            SELECT
                bp.packet_id,
                CASE
                    WHEN COUNT(DISTINCT kv.file_path) >= 3 THEN 'strong'
                    WHEN COUNT(DISTINCT kv.file_path) = 2 THEN 'moderate'
                    WHEN COUNT(DISTINCT kv.file_path) = 1 THEN 'single_source'
                    ELSE 'no_evidence'
                END as corroboration_strength
            FROM brain_packets bp
            LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
            LEFT JOIN (
                SELECT id, file_path FROM knowledge_vectors
                UNION ALL
                SELECT id, file_path FROM knowledge_vectors_legacy
            ) kv ON bpe.chunk_id = kv.id
            WHERE bp.status = 'active'
            GROUP BY bp.packet_id
        ) sub
        GROUP BY corroboration_strength
        ORDER BY packet_count DESC
    """,

    # -----------------------------------------------------------------------
    # 7. Document inventory stats
    # -----------------------------------------------------------------------
    "document_stats": """
        SELECT
            document_type,
            status,
            COUNT(*) as documents,
            SUM(chunk_count) as total_chunks,
            ROUND(AVG(chunk_count), 1) as avg_chunks_per_doc,
            MIN(ingested_at) as first_ingested,
            MAX(ingested_at) as last_ingested
        FROM brain_documents
        GROUP BY document_type, status
        ORDER BY documents DESC
    """,

    "document_pipeline_versions": """
        SELECT
            pipeline_version,
            COUNT(*) as documents,
            SUM(chunk_count) as chunks,
            MIN(ingested_at) as first_seen,
            MAX(ingested_at) as last_seen
        FROM brain_documents
        GROUP BY pipeline_version
        ORDER BY documents DESC
    """,

    # -----------------------------------------------------------------------
    # 8. Relationship graph stats
    # -----------------------------------------------------------------------
    "relationship_stats": """
        SELECT
            predicate,
            COUNT(*) as count,
            ROUND(AVG(confidence), 3) as avg_confidence,
            ROUND(AVG(evidence_count), 1) as avg_evidence_count
        FROM brain_relationships
        GROUP BY predicate
        ORDER BY count DESC
    """,

    # -----------------------------------------------------------------------
    # 9. Validation sample stats
    # -----------------------------------------------------------------------
    "validation_verdict_distribution": """
        SELECT
            verdict,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
        FROM brain_validation_samples
        WHERE verdict IS NOT NULL
        GROUP BY verdict
        ORDER BY count DESC
    """,

    # -----------------------------------------------------------------------
    # 10. Brain health traffic light — single-glance score
    # -----------------------------------------------------------------------
    "brain_health_score": """
        SELECT
            (SELECT COUNT(*) FROM brain_packets WHERE status = 'active') as active_packets,
            (SELECT COUNT(*) FROM brain_packets WHERE status = 'quarantined') as quarantined_packets,
            (SELECT COUNT(*) FROM brain_packets
             WHERE status = 'active'
               AND (last_verified_at IS NULL OR last_verified_at < now() - INTERVAL '90 days')
            ) as stale_active_packets,
            (SELECT COUNT(*) FROM brain_packet_evidence) as total_evidence_links,
            (SELECT COUNT(DISTINCT bp.packet_id)
             FROM brain_packets bp
             LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
             WHERE bp.status = 'active' AND bpe.evidence_id IS NULL
            ) as orphan_active_packets,
            (SELECT COUNT(*) FROM brain_documents) as total_documents,
            (SELECT COUNT(*) FROM brain_dedupe_clusters) as dedup_clusters,
            (SELECT COUNT(*) FROM brain_curation_runs WHERE status = 'completed') as completed_runs,
            (SELECT COUNT(*) FROM brain_curation_runs WHERE status IN ('failed', 'error')) as failed_runs,
            CASE
                WHEN (SELECT COUNT(*) FROM brain_packets WHERE status = 'quarantined') >
                     (SELECT COUNT(*) FROM brain_packets WHERE status = 'active') * 0.1
                THEN 'RED'
                WHEN (SELECT COUNT(DISTINCT bp.packet_id)
                      FROM brain_packets bp
                      LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
                      WHERE bp.status = 'active' AND bpe.evidence_id IS NULL
                ) > (SELECT COUNT(*) FROM brain_packets WHERE status = 'active') * 0.3
                THEN 'AMBER'
                WHEN (SELECT COUNT(*) FROM brain_curation_runs WHERE status IN ('failed', 'error')) >
                     (SELECT COUNT(*) FROM brain_curation_runs WHERE status = 'completed') * 0.2
                THEN 'AMBER'
                ELSE 'GREEN'
            END as health_status
    """,

    # -----------------------------------------------------------------------
    # 11. Packet status flow — governance overview
    # -----------------------------------------------------------------------
    "packet_status_flow": """
        SELECT
            status,
            route,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
        FROM brain_packets
        GROUP BY status, route
        ORDER BY count DESC
    """,

    # -----------------------------------------------------------------------
    # 12. Anti-shelfware: query freshness for Brain queries
    # -----------------------------------------------------------------------
    "brain_query_freshness": """
        SELECT
            query_name,
            MAX(executed_at) as last_run,
            COUNT(*) as total_runs,
            ROUND(
                EPOCH(now() - MAX(executed_at)) / 86400,
                1
            ) as days_since_last_run
        FROM query_log
        WHERE query_name LIKE 'brain_%'
           OR query_name IN (
               'curation_pipeline_health', 'curation_recent_runs',
               'curation_velocity', 'dedup_cluster_stats',
               'evidence_density', 'evidence_orphans',
               'stale_packets', 'stale_packet_summary',
               'triangulation_summary', 'document_stats',
               'relationship_stats', 'validation_verdict_distribution',
               'brain_health_score', 'packet_status_flow'
           )
        GROUP BY query_name
        ORDER BY days_since_last_run DESC
    """,
}

# ---------------------------------------------------------------------------
# Simplified triangulation queries (when knowledge_vectors not loaded)
# These work without the vectors table for basic Brain analytics
# ---------------------------------------------------------------------------

BRAIN_QUERY_REGISTRY_LITE: dict[str, str] = {
    k: v for k, v in BRAIN_QUERY_REGISTRY.items()
    if k not in ("triangulation_by_packet", "triangulation_summary")
}

# Lite triangulation (evidence link count only, no file_path join)
BRAIN_QUERY_REGISTRY_LITE["triangulation_summary_lite"] = """
    SELECT
        CASE
            WHEN evidence_count >= 3 THEN 'strong'
            WHEN evidence_count = 2 THEN 'moderate'
            WHEN evidence_count = 1 THEN 'single_source'
            ELSE 'no_evidence'
        END as corroboration_strength,
        COUNT(*) as packet_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct
    FROM (
        SELECT
            bp.packet_id,
            COUNT(DISTINCT bpe.chunk_id) as evidence_count
        FROM brain_packets bp
        LEFT JOIN brain_packet_evidence bpe ON bp.packet_id = bpe.packet_id
        WHERE bp.status = 'active'
        GROUP BY bp.packet_id
    ) sub
    GROUP BY corroboration_strength
    ORDER BY packet_count DESC
"""
