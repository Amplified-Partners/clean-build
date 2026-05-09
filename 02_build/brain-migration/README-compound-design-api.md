# Compound Design API — Brain MCP Server

REST endpoints for the Compound Design memory-write / memory-recall system.
These endpoints coexist with the existing MCP protocol on the same FastAPI app.

## Endpoints

### Writer (`:8091` — ALLOW_WRITES=true)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/design/artifacts` | Create a design artifact |
| POST | `/design/patterns` | Create a design pattern |
| POST | `/design/research` | Create a research finding |
| POST | `/design/pudding` | Create a pudding concept |
| POST | `/design/graph/edge` | Create a graph edge between nodes |

### Reader (`:8090` — read-only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/design/recall` | Semantic recall via pgvector cosine distance |
| GET | `/design/patterns` | List/filter design patterns |
| GET | `/design/research` | List/filter research findings |
| GET | `/design/graph/traverse` | Traverse the AGE knowledge graph |

---

## Write Endpoints

### POST /design/artifacts

Create a design artifact (component, layout, pattern, token, composition).

```bash
curl -X POST http://localhost:8091/design/artifacts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sidebar-collapse-animation",
    "artifact_type": "component",
    "phase": "develop",
    "description": "Sidebar collapse/expand animation using CSS transitions",
    "content": {"duration_ms": 200, "easing": "ease-in-out", "property": "width"},
    "tags": ["animation", "sidebar", "transition"],
    "source": "plugin:compound-design"
  }'
```

**Response:**
```json
{"id": "a1b2c3d4-...", "created_at": "2026-05-09T12:00:00+00:00"}
```

### POST /design/patterns

Create a design pattern (spacing, typography, color, motion, layout, interaction).

```bash
curl -X POST http://localhost:8091/design/patterns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "spatial-breathing",
    "category": "spacing",
    "description": "Minimum 16px breathing room between interactive elements",
    "rationale": "Touch targets need isolation; cognitive load reduces with whitespace",
    "constraints": {"min_gap_px": 16, "applies_to": ["buttons", "links", "inputs"]},
    "examples": [{"component": "toolbar", "gap": "20px"}]
  }'
```

### POST /design/research

Create a research finding.

```bash
curl -X POST http://localhost:8091/design/research \
  -H "Content-Type: application/json" \
  -d '{
    "title": "WCAG 2.2 touch target minimum",
    "domain": "accessibility",
    "summary": "Interactive elements must be at least 24x24 CSS pixels",
    "evidence": {"source": "WCAG 2.2 Success Criterion 2.5.8", "url": "https://www.w3.org/TR/WCAG22/#target-size-minimum"},
    "confidence": 0.99
  }'
```

### POST /design/pudding

Create a pudding concept (cross-domain bridge discovery).

```bash
curl -X POST http://localhost:8091/design/pudding \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gestalt-proximity-to-css-gap",
    "bridge_a": "Gestalt proximity principle (psychology)",
    "bridge_b": "CSS gap property (implementation)",
    "mechanism": "Perceptual grouping maps directly to flex/grid gap values",
    "pudding_score": 0.85,
    "domain_distance": 0.7,
    "confidence_band": "VALID"
  }'
```

### POST /design/graph/edge

Create a relationship edge in the compound_design AGE graph.

```bash
curl -X POST http://localhost:8091/design/graph/edge \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "a1b2c3d4-...",
    "source_label": "Pattern",
    "target_id": "e5f6g7h8-...",
    "target_label": "Research",
    "edge_type": "VALIDATED_BY",
    "properties": {"confidence": 0.95, "validated_at": "2026-05-09"}
  }'
```

**Valid labels:** `Artifact`, `Pattern`, `Research`, `Pudding`, `Concept`
**Valid edge types:** `INFORMS`, `DERIVES_FROM`, `CONTRADICTS`, `BRIDGES_TO`, `VALIDATED_BY`

---

## Read Endpoints

### GET /design/recall

Semantic recall using pgvector cosine distance. Returns design artifacts sorted by similarity.

```bash
curl "http://localhost:8090/design/recall?query_embedding=[0.1,0.2,...384 floats]&limit=5&phase=develop"
```

**Parameters:**
- `query_embedding` (required) — JSON array of 384 floats
- `phase` (optional) — Filter by phase: discover, define, develop, deliver
- `artifact_type` (optional) — Filter by type: component, layout, pattern, token, composition
- `limit` (optional, default 10, max 100)

**Response:**
```json
{
  "results": [
    {
      "id": "...",
      "name": "sidebar-collapse-animation",
      "artifact_type": "component",
      "phase": "develop",
      "description": "...",
      "content": {...},
      "tags": ["animation"],
      "distance": 0.123,
      "created_at": "2026-05-09T12:00:00+00:00"
    }
  ],
  "count": 1
}
```

### GET /design/patterns

List design patterns, optionally filtered by category.

```bash
curl "http://localhost:8090/design/patterns?category=spacing&limit=10"
```

**Parameters:**
- `category` (optional) — spacing, typography, color, motion, layout, interaction
- `limit` (optional, default 25, max 200)

### GET /design/research

List research findings, optionally filtered by domain.

```bash
curl "http://localhost:8090/design/research?domain=accessibility&limit=10"
```

**Parameters:**
- `domain` (optional) — accessibility, performance, aesthetics, usability, brand
- `limit` (optional, default 25, max 200)

### GET /design/graph/traverse

Traverse the compound_design AGE graph from a starting node.

```bash
curl "http://localhost:8090/design/graph/traverse?start_id=a1b2c3d4-...&start_label=Pattern&edge_type=INFORMS&depth=2"
```

**Parameters:**
- `start_id` (required) — Starting node UUID
- `start_label` (required) — Node label: Artifact, Pattern, Research, Pudding, Concept
- `edge_type` (optional) — Filter edges: INFORMS, DERIVES_FROM, CONTRADICTS, BRIDGES_TO, VALIDATED_BY
- `depth` (optional, default 2, max 5) — Traversal depth

**Response:**
```json
{
  "results": [
    {"node": "{...agtype...}", "edges": "[{...agtype...}]"}
  ],
  "count": 1,
  "start": "a1b2c3d4-...",
  "depth": 2
}
```

---

## Embeddings

All tables support optional `embedding` fields (384-dimensional vectors).
Embeddings are pre-computed by the calling plugin/agent and passed in the POST body.
The server does NOT generate embeddings — it stores and searches them.

Dimension: **384** (matches existing `knowledge_vectors` table).

---

## Database Tables

Created by migration `006_compound_design_schema.sql`:

| Table | Purpose |
|-------|---------|
| `design_artifacts` | Design components, layouts, tokens, compositions |
| `design_patterns` | Reusable design rules and constraints |
| `research_findings` | Evidence-backed design research |
| `pudding_concepts` | Cross-domain bridge discoveries (Pudding Technique) |

Graph (Apache AGE):
- Graph name: `compound_design`
- Vertex labels: Artifact, Pattern, Research, Pudding, Concept
- Edge labels: INFORMS, DERIVES_FROM, CONTRADICTS, BRIDGES_TO, VALIDATED_BY

---

## Access Control

- **brain_writer** (`:8091`): INSERT, UPDATE on all compound design tables + ag_catalog usage
- **brain_reader** (`:8090`): SELECT on all compound design tables + ag_catalog usage
- No DELETE for either role (append-only by design)

---

*Devon-a81b | 2026-05-09 | AMP-280 Compound Design API documentation*
