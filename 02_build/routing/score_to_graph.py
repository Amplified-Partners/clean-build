#!/usr/bin/env python3
"""
Score-to-Graph adapter — writes labeled/scored APDS items into FalkorDB.

Pipeline position:  Score --> [this adapter] --> FalkorDB (kg_pudding_discovery)

Takes ``LabeledRecord`` objects (from harvest_to_label or sidecar_to_label)
and writes them as Concept nodes in the FalkorDB knowledge graph. Also handles
Recipe creation when the Match stage produces A-B-C chains, and Signal
recording when the Body Language detector flags anomalies/drift/convergence.

FalkorDB graph schema follows the APDS spec (Part 2.4):
    - (:Concept) — extracted entities with PUDDING labels and scores
    - (:Source)  — harvest origins
    - (:Content) — raw harvested content
    - (:Recipe)  — A-B-C pudding discoveries
    - (:Signal)  — body language detections

Usage:
    from score_to_graph import GraphWriter

    writer = GraphWriter()                     # uses env defaults
    writer.upsert_concept(labeled_record)      # single concept
    writer.upsert_recipe(recipe_dict)          # A-B-C chain
    writer.record_signal(signal_dict)          # body language signal
    writer.close()

Signed-by: Devon (Devin session f32d587cc3e54f959c5309d93f72bc97) - 2026-05-01
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("apds.score_to_graph")

# FalkorDB uses a Redis-compatible protocol.
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "falkordb")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "kg_pudding_discovery")


# ---------------------------------------------------------------------------
# Cypher template library (APDS spec Part 2.4)
# ---------------------------------------------------------------------------

_UPSERT_CONCEPT = """
MERGE (c:Concept {id: $id})
SET c.mechanism_label   = $mechanism_label,
    c.pudding_label     = $pudding_label,
    c.dimensions         = $dimensions,
    c.relevance_score    = $relevance_score,
    c.actionability_score = $actionability_score,
    c.evidence_score     = $evidence_score,
    c.impact_score       = $impact_score,
    c.total_pudding_score = $total_pudding_score,
    c.source_domain      = $source_domain,
    c.extracted_at       = $extracted_at,
    c.validated_at       = $validated_at
RETURN c.id
"""

_UPSERT_SOURCE = """
MERGE (s:Source {id: $id})
SET s.url            = $url,
    s.name           = $name,
    s.tier           = $tier,
    s.domain         = $domain,
    s.last_scanned   = $last_scanned,
    s.status         = $status
RETURN s.id
"""

_UPSERT_CONTENT = """
MERGE (ct:Content {id: $id})
SET ct.source_id    = $source_id,
    ct.url          = $url,
    ct.title        = $title,
    ct.text_hash    = $text_hash,
    ct.harvested_at = $harvested_at,
    ct.change_type  = $change_type
RETURN ct.id
"""

_LINK_CONTENT_CONCEPT = """
MATCH (ct:Content {id: $content_id})
MATCH (c:Concept {id: $concept_id})
MERGE (ct)-[:CONTAINS]->(c)
"""

_LINK_SOURCE_CONTENT = """
MATCH (s:Source {id: $source_id})
MATCH (ct:Content {id: $content_id})
MERGE (s)-[:PROVIDES]->(ct)
"""

_UPSERT_RECIPE = """
MERGE (r:Recipe {id: $id})
SET r.concept_a_id              = $concept_a_id,
    r.bridge_b_id               = $concept_b_id,
    r.concept_c_id              = $concept_c_id,
    r.hypothesis                = $hypothesis,
    r.one_plus_one_equals_three = $insight,
    r.simple_score              = $simple_score,
    r.advanced_score            = $advanced_score,
    r.jaccard_slot              = $jaccard_slot,
    r.domain_distance           = $domain_distance,
    r.status                    = $status,
    r.testable_prediction       = $testable_prediction,
    r.discovered_at             = $discovered_at,
    r.discovered_by             = $discovered_by,
    r.reviewed_by               = $reviewed_by,
    r.reviewed_at               = $reviewed_at
RETURN r.id
"""

_LINK_RECIPE_CONCEPTS = """
MATCH (a:Concept {id: $concept_a_id})
MATCH (b:Concept {id: $concept_b_id})
MATCH (c:Concept {id: $concept_c_id})
MERGE (a)-[:BRIDGES {jaccard: $jaccard, recipe_id: $recipe_id}]->(b)
MERGE (b)-[:BRIDGES {jaccard: $jaccard, recipe_id: $recipe_id}]->(c)
"""

_UPSERT_SIGNAL = """
MERGE (sig:Signal {id: $id})
SET sig.type        = $type,
    sig.source_ids  = $source_ids,
    sig.description = $description,
    sig.severity    = $severity,
    sig.detected_at = $detected_at,
    sig.resolved_at = $resolved_at
RETURN sig.id
"""

_LINK_SIGNAL_RECIPE = """
MATCH (sig:Signal {id: $signal_id})
MATCH (r:Recipe {id: $recipe_id})
MERGE (sig)-[:INDICATES]->(r)
"""


# ---------------------------------------------------------------------------
# Graph writer
# ---------------------------------------------------------------------------

class GraphWriter:
    """Manages FalkorDB graph writes for the APDS pipeline.

    Wraps the ``falkordb`` Python client. Falls back to a dry-run logger
    if the client is unavailable or the server is unreachable.
    """

    def __init__(
        self,
        host: str = FALKORDB_HOST,
        port: int = FALKORDB_PORT,
        graph_name: str = FALKORDB_GRAPH,
    ):
        self._host = host
        self._port = port
        self._graph_name = graph_name
        self._graph = None
        self._dry_run = False
        self._connect()

    def _connect(self) -> None:
        try:
            from falkordb import FalkorDB
            db = FalkorDB(host=self._host, port=self._port)
            self._graph = db.select_graph(self._graph_name)
            logger.info("Connected to FalkorDB %s:%d graph=%s", self._host, self._port, self._graph_name)
        except ImportError:
            logger.warning("falkordb package not installed — running in dry-run mode")
            self._dry_run = True
        except Exception as exc:
            logger.warning("FalkorDB connection failed (%s) — running in dry-run mode", exc)
            self._dry_run = True

    def _query(self, cypher: str, params: dict[str, Any]) -> Any:
        if self._dry_run:
            logger.info("[DRY RUN] %s | %s", cypher.split("\n")[0].strip(), list(params.keys()))
            return None
        return self._graph.query(cypher, params)

    # -- Concept nodes --

    def upsert_concept(self, labeled_record: Any) -> str:
        """Write a labeled item as a Concept node.

        Accepts a ``LabeledRecord`` (from harvest_to_label / sidecar_to_label)
        or a dict with equivalent keys.
        """
        if hasattr(labeled_record, "harvest"):
            lr = labeled_record
            harvest = lr.harvest
            concept_id = _make_concept_id(harvest.source_name, harvest.external_id)
            params = {
                "id": concept_id,
                "mechanism_label": harvest.title,
                "pudding_label": lr.pudding_label,
                "dimensions": [lr.what, lr.how, lr.scale, lr.time],
                "relevance_score": 0,
                "actionability_score": 0,
                "evidence_score": 0,
                "impact_score": 0,
                "total_pudding_score": 0,
                "source_domain": harvest.source_name,
                "extracted_at": lr.labeled_at,
                "validated_at": "",
            }
        elif isinstance(labeled_record, dict):
            concept_id = labeled_record.get("id", _make_concept_id(
                labeled_record.get("source_domain", "unknown"),
                labeled_record.get("mechanism_label", ""),
            ))
            params = {
                "id": concept_id,
                "mechanism_label": labeled_record.get("mechanism_label", ""),
                "pudding_label": labeled_record.get("pudding_label", ""),
                "dimensions": labeled_record.get("dimensions", []),
                "relevance_score": labeled_record.get("relevance_score", 0),
                "actionability_score": labeled_record.get("actionability_score", 0),
                "evidence_score": labeled_record.get("evidence_score", 0),
                "impact_score": labeled_record.get("impact_score", 0),
                "total_pudding_score": labeled_record.get("total_pudding_score", 0),
                "source_domain": labeled_record.get("source_domain", ""),
                "extracted_at": labeled_record.get("extracted_at", datetime.now(timezone.utc).isoformat()),
                "validated_at": labeled_record.get("validated_at", ""),
            }
        else:
            raise TypeError(f"Expected LabeledRecord or dict, got {type(labeled_record)}")

        self._query(_UPSERT_CONCEPT, params)
        logger.debug("Upserted concept %s [%s]", concept_id, params["pudding_label"])
        return concept_id

    def upsert_source(self, source: dict[str, Any]) -> str:
        """Write a Source node."""
        source_id = source.get("id", _make_id(source.get("url", source.get("name", ""))))
        params = {
            "id": source_id,
            "url": source.get("url", ""),
            "name": source.get("name", ""),
            "tier": source.get("tier", "T1"),
            "domain": source.get("domain", ""),
            "last_scanned": source.get("last_scanned", datetime.now(timezone.utc).isoformat()),
            "status": source.get("status", "active"),
        }
        self._query(_UPSERT_SOURCE, params)
        return source_id

    def upsert_content(self, content: dict[str, Any]) -> str:
        """Write a Content node and link to its Source."""
        content_id = content.get("id", _make_id(content.get("url", content.get("title", ""))))
        params = {
            "id": content_id,
            "source_id": content.get("source_id", ""),
            "url": content.get("url", ""),
            "title": content.get("title", ""),
            "text_hash": content.get("text_hash", ""),
            "harvested_at": content.get("harvested_at", datetime.now(timezone.utc).isoformat()),
            "change_type": content.get("change_type", "new"),
        }
        self._query(_UPSERT_CONTENT, params)

        if params["source_id"]:
            self._query(_LINK_SOURCE_CONTENT, {
                "source_id": params["source_id"],
                "content_id": content_id,
            })

        return content_id

    def link_content_to_concept(self, content_id: str, concept_id: str) -> None:
        """Create a CONTAINS edge from Content to Concept."""
        self._query(_LINK_CONTENT_CONCEPT, {
            "content_id": content_id,
            "concept_id": concept_id,
        })

    # -- Recipe nodes (A-B-C chains) --

    def upsert_recipe(self, recipe: dict[str, Any]) -> str:
        """Write a Recipe node representing a discovered A-B-C chain."""
        recipe_id = recipe.get("id", _make_id(
            f"{recipe.get('concept_a_id', '')}-{recipe.get('concept_b_id', '')}-{recipe.get('concept_c_id', '')}"
        ))
        params = {
            "id": recipe_id,
            "concept_a_id": recipe.get("concept_a_id", ""),
            "concept_b_id": recipe.get("concept_b_id", ""),
            "concept_c_id": recipe.get("concept_c_id", ""),
            "hypothesis": recipe.get("hypothesis", ""),
            "insight": recipe.get("one_plus_one_equals_three", ""),
            "simple_score": recipe.get("simple_score", 0),
            "advanced_score": recipe.get("advanced_score", 0),
            "jaccard_slot": recipe.get("jaccard_slot", 0.0),
            "domain_distance": recipe.get("domain_distance", 0),
            "status": recipe.get("status", "hypothesis"),
            "testable_prediction": recipe.get("testable_prediction", ""),
            "discovered_at": recipe.get("discovered_at", datetime.now(timezone.utc).isoformat()),
            "discovered_by": recipe.get("discovered_by", "deterministic"),
            "reviewed_by": recipe.get("reviewed_by", ""),
            "reviewed_at": recipe.get("reviewed_at", ""),
        }
        self._query(_UPSERT_RECIPE, params)

        if params["concept_a_id"] and params["concept_b_id"] and params["concept_c_id"]:
            result = self._query(_LINK_RECIPE_CONCEPTS, {
                "concept_a_id": params["concept_a_id"],
                "concept_b_id": params["concept_b_id"],
                "concept_c_id": params["concept_c_id"],
                "jaccard": params["jaccard_slot"],
                "recipe_id": recipe_id,
            })
            if not self._dry_run and result is not None and result.result_set == []:
                logger.warning(
                    "Recipe %s: one or more concepts not found in graph "
                    "(A=%s, B=%s, C=%s) — BRIDGES edges not created",
                    recipe_id, params["concept_a_id"],
                    params["concept_b_id"], params["concept_c_id"],
                )

        logger.debug("Upserted recipe %s (score=%s)", recipe_id, params["advanced_score"])
        return recipe_id

    # -- Signal nodes (body language) --

    def record_signal(self, signal: dict[str, Any]) -> str:
        """Write a Signal node (anomaly, drift, spike, weak_signal, convergence, structural_echo)."""
        signal_id = signal.get("id", _make_id(
            f"{signal.get('type', 'unknown')}-{signal.get('description', '')[:50]}"
        ))
        params = {
            "id": signal_id,
            "type": signal.get("type", "unknown"),
            "source_ids": signal.get("source_ids", []),
            "description": signal.get("description", ""),
            "severity": signal.get("severity", 0),
            "detected_at": signal.get("detected_at", datetime.now(timezone.utc).isoformat()),
            "resolved_at": signal.get("resolved_at", ""),
        }
        self._query(_UPSERT_SIGNAL, params)

        recipe_id = signal.get("recipe_id")
        if recipe_id:
            self._query(_LINK_SIGNAL_RECIPE, {
                "signal_id": signal_id,
                "recipe_id": recipe_id,
            })

        logger.debug("Recorded signal %s [%s] severity=%s", signal_id, params["type"], params["severity"])
        return signal_id

    # -- Batch convenience --

    def ingest_labeled_batch(self, records: list) -> list[str]:
        """Write a batch of LabeledRecords as Concept nodes.

        Returns list of concept IDs created/updated.
        """
        ids = []
        for record in records:
            try:
                cid = self.upsert_concept(record)
                ids.append(cid)
            except Exception as exc:
                logger.warning("Failed to ingest record: %s", exc)
        logger.info("Ingested %d/%d concepts into %s", len(ids), len(records), self._graph_name)
        return ids

    def close(self) -> None:
        """Clean up connection resources."""
        self._graph = None
        logger.debug("GraphWriter closed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(seed: str) -> str:
    return f"AMP-{hashlib.sha256(seed.encode()).hexdigest()[:12]}"


def _make_concept_id(source: str, external_id: str) -> str:
    return f"AMP-{hashlib.sha256(f'{source}:{external_id}'.encode()).hexdigest()[:12]}"


# ---------------------------------------------------------------------------
# CLI — quick smoke test / manual ingest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="APDS Score-to-Graph adapter")
    parser.add_argument("--test", action="store_true", help="Run a dry-run test with sample data")
    args = parser.parse_args()

    if args.test:
        writer = GraphWriter()
        sample_concept = {
            "mechanism_label": "Test Concept",
            "pudding_label": "M.+.5.l",
            "dimensions": ["M", "+", "5", "l"],
            "source_domain": "test",
            "total_pudding_score": 15,
        }
        cid = writer.upsert_concept(sample_concept)
        print(f"Concept ID: {cid}")

        sample_recipe = {
            "concept_a_id": cid,
            "concept_b_id": "AMP-bridge-test",
            "concept_c_id": "AMP-target-test",
            "hypothesis": "Test hypothesis",
            "one_plus_one_equals_three": "Test insight",
            "simple_score": 8,
            "advanced_score": 15,
            "jaccard_slot": 0.85,
            "domain_distance": 4,
            "discovered_by": "test",
        }
        rid = writer.upsert_recipe(sample_recipe)
        print(f"Recipe ID: {rid}")

        sample_signal = {
            "type": "convergence",
            "description": "Test convergence signal",
            "severity": 7,
            "recipe_id": rid,
        }
        sid = writer.record_signal(sample_signal)
        print(f"Signal ID: {sid}")

        writer.close()
        print("Smoke test complete.")
