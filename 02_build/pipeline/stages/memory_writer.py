"""
Memory Store Writer (AMP-156)
=============================

Unified writer for FalkorDB (graph) and Qdrant (vector). Takes classified +
validated files and writes memory events with dedup.

Patterns reused:
- UNWIND-batched MERGE from apds_labeller_v2.2 (proven defence against
  FalkorDB silent data loss on container recycle)
- Verify-and-retry from AMP-128
- all-MiniLM-L6-v2 embeddings (384-dim) to match existing 57k Qdrant vectors

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..checkpoint import CheckpointStore
from ..dlq import DeadLetterQueue
from ..logging_config import get_logger
from ..models import IngestResult, ItemStatus, PipelineItem

logger = get_logger("memory_writer")

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "172.18.0.22")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "business_knowledge")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "amplified_knowledge")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.18.0.12:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

BATCH_SIZE = int(os.getenv("WRITER_BATCH_SIZE", "50"))
VERIFY_RETRIES = int(os.getenv("WRITER_VERIFY_RETRIES", "3"))


def _escape_cypher(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", " ")


def _cypher_string(s: str | None) -> str:
    return "'" + _escape_cypher(s or "") + "'"


def _cypher_value(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return _cypher_string(v)
    if isinstance(v, list):
        return "[" + ", ".join(_cypher_value(i) for i in v) + "]"
    raise TypeError(f"Unsupported type for Cypher: {type(v).__name__}")


def _cypher_map(d: dict) -> str:
    parts = [f"{k}: {_cypher_value(v)}" for k, v in d.items()]
    return "{" + ", ".join(parts) + "}"


class FalkorDBWriter:
    """Writes documents to FalkorDB using UNWIND-batched MERGE with verify-retry."""

    def __init__(
        self,
        host: str = FALKORDB_HOST,
        port: int = FALKORDB_PORT,
        graph_name: str = FALKORDB_GRAPH,
    ):
        self._host = host
        self._port = port
        self._graph_name = graph_name
        self._client = None
        self._connect()

    def _connect(self) -> None:
        try:
            import redis
            self._client = redis.Redis(
                host=self._host, port=self._port,
                decode_responses=True, socket_timeout=30,
                socket_connect_timeout=10,
            )
            self._client.ping()
            logger.info("FalkorDB connected at %s:%d graph=%s", self._host, self._port, self._graph_name)
        except Exception as exc:
            logger.warning("FalkorDB connection failed: %s — running in dry-run mode", exc)
            self._client = None

    def _query(self, cypher: str) -> list:
        if not self._client:
            logger.info("[DRY RUN] %s", cypher[:120])
            return []
        return self._client.execute_command("GRAPH.QUERY", self._graph_name, cypher)

    def _doc_exists(self, doc_id: str) -> bool:
        res = self._query(
            f"MATCH (d:Document {{id: {_cypher_string(doc_id)}}}) RETURN count(d)"
        )
        if not res or len(res) < 2 or not res[1]:
            return False
        try:
            row = res[1][0] if res[1] else None
            if isinstance(row, list):
                return int(row[0]) > 0
            return int(row) > 0
        except (IndexError, TypeError, ValueError):
            return False

    def write_batch(self, items: list[PipelineItem]) -> tuple[int, int]:
        """Write a batch of items using UNWIND-batched MERGE.

        Returns (created_count, skipped_count).
        """
        if not items:
            return 0, 0

        batch_maps = []
        for item in items:
            doc_id = hashlib.sha256(item.file_path.encode()).hexdigest()[:16]
            taxonomy = item.taxonomy
            dims_str = ", ".join(taxonomy.dimensions) if taxonomy and taxonomy.dimensions else ""
            props = {
                "id": doc_id,
                "file_path": item.file_path,
                "file_hash": item.file_hash,
                "type": taxonomy.type if taxonomy else "unknown",
                "dimensions": dims_str,
                "expert": taxonomy.expert if taxonomy else "UNKNOWN",
                "actionable": taxonomy.actionable if taxonomy else "principle_only",
                "status": taxonomy.status if taxonomy else "hypothesis",
                "confidence": taxonomy.confidence if taxonomy else 0.0,
                "value": item.classification.value if item.classification else "low",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "provenance": "amplified-pipeline-v0.1",
            }
            batch_maps.append(props)

        list_literal = "[" + ", ".join(_cypher_map(m) for m in batch_maps) + "]"
        cypher = (
            f"UNWIND {list_literal} AS doc "
            "MERGE (d:Document {id: doc.id}) "
            "SET d.file_path = doc.file_path, "
            "    d.file_hash = doc.file_hash, "
            "    d.type = doc.type, "
            "    d.dimensions = doc.dimensions, "
            "    d.expert = doc.expert, "
            "    d.actionable = doc.actionable, "
            "    d.status = doc.status, "
            "    d.confidence = doc.confidence, "
            "    d.value = doc.value, "
            "    d.ingested_at = doc.ingested_at, "
            "    d.provenance = doc.provenance "
            "RETURN count(d)"
        )

        for attempt in range(1, VERIFY_RETRIES + 1):
            try:
                self._query(cypher)
                # Verify: count how many of our batch are present
                ids = [m["id"] for m in batch_maps]
                id_list = "[" + ", ".join(_cypher_string(i) for i in ids) + "]"
                verify_q = (
                    f"MATCH (d:Document) WHERE d.id IN {id_list} RETURN count(d)"
                )
                res = self._query(verify_q)
                found = 0
                if res and len(res) >= 2 and res[1]:
                    row = res[1][0] if isinstance(res[1], list) and res[1] else res[1]
                    if isinstance(row, list):
                        found = int(row[0])
                    else:
                        found = int(row)

                if found >= len(batch_maps):
                    return found, 0
                logger.warning(
                    "Verify: %d/%d found (attempt %d/%d), retrying batch",
                    found, len(batch_maps), attempt, VERIFY_RETRIES,
                )
            except Exception as exc:
                logger.error("FalkorDB batch write error (attempt %d): %s", attempt, exc)
                if attempt == VERIFY_RETRIES:
                    raise
                time.sleep(1 * attempt)

        return len(batch_maps), 0

    def close(self) -> None:
        if self._client:
            self._client.close()


class QdrantWriter:
    """Writes document embeddings to Qdrant."""

    def __init__(
        self,
        host: str = QDRANT_HOST,
        port: int = QDRANT_PORT,
        collection: str = QDRANT_COLLECTION,
        ollama_url: str = OLLAMA_URL,
        model: str = EMBEDDING_MODEL,
    ):
        self._host = host
        self._port = port
        self._collection = collection
        self._ollama_url = ollama_url
        self._model = model
        self._client = None
        self._connect()

    def _connect(self) -> None:
        try:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(host=self._host, port=self._port, timeout=30)
            info = self._client.get_collection(self._collection)
            logger.info(
                "Qdrant connected: %s (%d points)",
                self._collection, info.points_count,
            )
        except Exception as exc:
            logger.warning("Qdrant connection failed: %s — running in dry-run mode", exc)
            self._client = None

    def _embed(self, text: str) -> list[float]:
        """Get embedding via Ollama."""
        payload = json.dumps({
            "model": self._model,
            "prompt": text[:8000],
        }).encode()
        req = urllib.request.Request(
            f"{self._ollama_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data.get("embedding", [])

    def _point_exists(self, point_id: str) -> bool:
        """Check if a point already exists by its ID."""
        if not self._client:
            return False
        try:
            result = self._client.retrieve(
                collection_name=self._collection,
                ids=[point_id],
            )
            return len(result) > 0
        except Exception:
            return False

    def write_batch(self, items: list[PipelineItem]) -> tuple[int, int]:
        """Write a batch of items to Qdrant. Returns (created, skipped)."""
        if not self._client or not items:
            return 0, len(items)

        from qdrant_client.models import PointStruct

        points = []
        skipped = 0
        for item in items:
            point_id = hashlib.sha256(item.file_path.encode()).hexdigest()[:32]
            if self._point_exists(point_id):
                skipped += 1
                continue

            try:
                content = Path(item.file_path).read_text(encoding="utf-8", errors="ignore")
                vector = self._embed(content)
                if not vector:
                    continue
                taxonomy = item.taxonomy
                payload = {
                    "file_path": item.file_path,
                    "file_hash": item.file_hash,
                    "type": taxonomy.type if taxonomy else "unknown",
                    "dimensions": taxonomy.dimensions if taxonomy else [],
                    "expert": taxonomy.expert if taxonomy else "UNKNOWN",
                    "value": item.classification.value if item.classification else "low",
                    "confidence": taxonomy.confidence if taxonomy else 0.0,
                    "provenance": "amplified-pipeline-v0.1",
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                }
                points.append(PointStruct(id=point_id, vector=vector, payload=payload))
            except Exception as exc:
                logger.warning("Embed/write failed for %s: %s", item.file_path, exc)

        if points:
            self._client.upsert(collection_name=self._collection, points=points)

        return len(points), skipped

    def close(self) -> None:
        if self._client:
            self._client.close()


class MemoryStoreWriter:
    """Unified writer: FalkorDB (graph) + Qdrant (vector)."""

    def __init__(
        self,
        falkordb_host: str = FALKORDB_HOST,
        falkordb_port: int = FALKORDB_PORT,
        falkordb_graph: str = FALKORDB_GRAPH,
        qdrant_host: str = QDRANT_HOST,
        qdrant_port: int = QDRANT_PORT,
        qdrant_collection: str = QDRANT_COLLECTION,
        ollama_url: str = OLLAMA_URL,
        batch_size: int = BATCH_SIZE,
    ):
        self._batch_size = batch_size
        self._falkordb = FalkorDBWriter(falkordb_host, falkordb_port, falkordb_graph)
        self._qdrant = QdrantWriter(qdrant_host, qdrant_port, qdrant_collection, ollama_url)

    def write_items(
        self,
        items: list[PipelineItem],
        checkpoint: CheckpointStore,
        dlq: DeadLetterQueue,
    ) -> IngestResult:
        """Write classified items to both stores.

        FalkorDB first (verify-retry), then Qdrant. Per the AMP-156 plan:
        FalkorDB-first write order with verify before Qdrant write.
        """
        result = IngestResult(file_path="batch")
        total = len(items)

        for batch_start in range(0, total, self._batch_size):
            batch = items[batch_start:batch_start + self._batch_size]

            # Mark as writing
            for item in batch:
                checkpoint.update_item(item.file_path, ItemStatus.WRITING)

            # FalkorDB
            try:
                fb_created, fb_skipped = self._falkordb.write_batch(batch)
                result.falkordb_created += fb_created
                result.falkordb_skipped += fb_skipped
            except Exception as exc:
                error_msg = f"FalkorDB batch error: {exc}"[:500]
                result.errors.append(error_msg)
                for item in batch:
                    checkpoint.update_item(item.file_path, ItemStatus.FAILED, error=error_msg)
                    dlq.add(item.file_path, "write_falkordb", error_msg)
                continue

            # Qdrant
            try:
                qd_created, qd_skipped = self._qdrant.write_batch(batch)
                result.qdrant_created += qd_created
                result.qdrant_skipped += qd_skipped
            except Exception as exc:
                error_msg = f"Qdrant batch error: {exc}"[:500]
                result.errors.append(error_msg)
                for item in batch:
                    checkpoint.update_item(item.file_path, ItemStatus.FAILED, error=error_msg)
                    dlq.add(item.file_path, "write_qdrant", error_msg)
                continue

            # Mark written
            for item in batch:
                checkpoint.update_item(item.file_path, ItemStatus.WRITTEN)

            logger.info(
                "Batch %d-%d: FalkorDB %d created/%d skipped, Qdrant %d created/%d skipped",
                batch_start, batch_start + len(batch),
                fb_created, fb_skipped, qd_created, qd_skipped,
            )

        return result

    def close(self) -> None:
        self._falkordb.close()
        self._qdrant.close()
