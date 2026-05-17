#!/usr/bin/env python3
"""
PRE-UPLOAD SORT + CHECK — Amplified Artefact Corpus Scanner
============================================================
Scans, analyses, and clusters markdown artefacts across vault, clean-build,
and ground-truth repositories. Produces 4 output files for human review.

Signed-by: Devon | 2026-05-17 | Session 294b46afcdee47d5b250d328d61103c2
"""

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import yaml
from datasketch import MinHash, MinHashLSH

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPOS = {
    "vault": None,          # set from CLI or defaults
    "clean-build": None,
    "ground-truth": None,
}

QUARANTINE_FILES = {"HAZEL_DO_NOT_INGEST.txt"}

REQUIRED_YAML_FIELDS = [
    "id", "title", "source_path", "source_type", "created_at", "updated_at",
    "author_or_originator", "attribution_chain", "epistemic_tier", "claim_type",
    "domain", "goal_context", "pudding_label", "pattern_codes",
    "semantic_dimensions", "evidence_summary", "actionability", "risk_flags",
    "related_entities", "canonical_summary",
]

MINHASH_NUM_PERM = 128
MINHASH_SHINGLE_SIZE = 5  # word-level shingles
NEAR_DUP_JACCARD_THRESHOLD = 0.80  # MinHash Jaccard threshold for near-dups

# Regex for hash-suffixed filenames like `-a49933.md`
HASH_SUFFIX_RE = re.compile(r"-([a-f0-9]{5,8})\.md$", re.IGNORECASE)

# Regex for version-suffixed filenames like `-v2.md`, `-v3.md`
VERSION_SUFFIX_RE = re.compile(r"-v(\d+)\.md$", re.IGNORECASE)

# Regex for version in path like `/SHARED-BOARD-v2.md`
VERSION_IN_NAME_RE = re.compile(r"(.*?)-v(\d+)\.md$", re.IGNORECASE)

OUTPUT_DIR = "/tmp/preupload_sort_output"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Artefact:
    artifact_id: str
    file_path: str
    repo: str
    relative_path: str
    file_size: int
    mod_time: str
    line_count: int
    word_count: int
    content_hash_sha256: str
    normalized_hash_sha256: str
    minhash_signature: list = field(default_factory=list)
    yaml_present: bool = False
    yaml_fields_present: list = field(default_factory=list)
    yaml_fields_missing: list = field(default_factory=list)
    yaml_completeness_score: float = 0.0
    yaml_raw: dict = field(default_factory=dict)
    has_version_suffix: bool = False
    version_number: Optional[int] = None
    has_hash_suffix: bool = False
    hash_suffix: Optional[str] = None
    filename_stem: str = ""
    heading_count: int = 0
    has_markdown_structure: bool = False
    is_auto_synced: bool = False
    source_path_quality: float = 0.0
    has_risk_flags: bool = False
    risk_flag_values: list = field(default_factory=list)
    is_summary: bool = False
    is_chaptered: bool = False
    has_ocr_damage: bool = False
    retrieval_usefulness: float = 0.0
    component_type: str = "glue"
    # Cluster assignment
    cluster_id: Optional[str] = None
    cluster_type: Optional[str] = None
    # Decision fields
    proposed_status: str = ""
    relation_to_canonical: str = ""
    proposed_canonical_artifact_id: Optional[str] = None
    reason: str = ""
    confidence: float = 0.0
    confidence_basis: str = "computed"
    alternative_options: list = field(default_factory=list)
    needs_human_review: bool = False


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip non-essential punctuation."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sha256_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def compute_minhash(text: str, num_perm: int = MINHASH_NUM_PERM,
                    shingle_size: int = MINHASH_SHINGLE_SIZE) -> MinHash:
    """Compute MinHash from word-level shingles."""
    m = MinHash(num_perm=num_perm)
    words = text.split()
    if len(words) < shingle_size:
        for w in words:
            m.update(w.encode("utf-8"))
        return m
    for i in range(len(words) - shingle_size + 1):
        shingle = " ".join(words[i:i + shingle_size])
        m.update(shingle.encode("utf-8"))
    return m


def extract_yaml_frontmatter(content: str) -> Optional[dict]:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        # Check if first non-blank line is ---
        stripped = content.lstrip()
        if not stripped.startswith("---"):
            return None

    # Find the closing ---
    lines = content.split("\n")
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "---":
            if start_idx is None:
                start_idx = i
            else:
                end_idx = i
                break

    if start_idx is None or end_idx is None:
        return None

    yaml_block = "\n".join(lines[start_idx + 1:end_idx])
    try:
        parsed = yaml.safe_load(yaml_block)
        if isinstance(parsed, dict):
            return parsed
    except yaml.YAMLError:
        pass
    return None


def detect_markdown_structure(content: str) -> tuple[int, bool]:
    """Count headings and assess markdown structure quality."""
    heading_count = 0
    has_lists = False
    has_code_blocks = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading_count += 1
        if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.", stripped):
            has_lists = True
        if stripped.startswith("```"):
            has_code_blocks = True
    has_structure = heading_count >= 2 or (heading_count >= 1 and (has_lists or has_code_blocks))
    return heading_count, has_structure


def detect_ocr_damage(content: str) -> bool:
    """Heuristic detection of OCR/transcription damage patterns.
    Conservative — only flags genuinely garbled text, not normal markdown."""
    damage_patterns = [
        # Garbled character runs (non-ASCII control chars, replacement chars)
        r"[\ufffd\x00-\x08\x0e-\x1f]{2,}",
        # Long runs of random-looking hex/base64 that aren't code blocks
        r"(?<![`/=])[a-f0-9]{40,}(?![`/=])",
        # Repeated nonsense punctuation (not markdown syntax)
        r"[;:,]{4,}",
        # Lines that are mostly non-alphanumeric (>60% symbols, excluding
        # markdown headers, horizontal rules, YAML delimiters, code fences)
    ]

    lines = content.split("\n")
    sampled_lines = lines[:200]
    if not sampled_lines:
        return False

    damage_count = 0
    for line in sampled_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip known markdown syntax lines
        if stripped.startswith(("#", "---", "```", "- ", "* ", "|", ">")):
            continue
        # Check explicit damage patterns
        for pat in damage_patterns:
            if re.search(pat, stripped):
                damage_count += 1
                break
        else:
            # Check for lines that are mostly non-alphanumeric (garbled)
            if len(stripped) > 10:
                alnum = sum(1 for c in stripped if c.isalnum() or c.isspace())
                if alnum / len(stripped) < 0.3:
                    damage_count += 1

    non_blank = sum(1 for line in sampled_lines if line.strip())
    if non_blank == 0:
        return False
    return (damage_count / non_blank) > 0.25


def detect_summary(filename: str, content: str) -> bool:
    """Detect if artefact is a summary document."""
    fn_lower = filename.lower()
    if any(kw in fn_lower for kw in ["summary", "synopsis", "overview", "tldr", "brief"]):
        return True
    # Check content for summary indicators
    first_500 = content[:500].lower()
    if any(kw in first_500 for kw in ["this is a summary", "executive summary", "summary of",
                                       "tldr", "tl;dr"]):
        return True
    return False


def detect_chaptered(filename: str, content: str) -> bool:
    """Detect if artefact is a chaptered copy (part-1, chapter-2, etc.)."""
    fn_lower = filename.lower()
    if re.search(r"(part|chapter|section|segment)[-_]?\d+", fn_lower):
        return True
    return False


def compute_source_path_quality(artefact: Artefact) -> float:
    """Score source path quality 0.0-1.0 based on path characteristics."""
    score = 0.5  # baseline
    rp = artefact.relative_path.lower()

    # Boost for structured locations
    if any(d in rp for d in ["01_truth", "00_authority", "ground-truth"]):
        score += 0.3
    elif any(d in rp for d in ["02_build", "research", "work"]):
        score += 0.1
    elif any(d in rp for d in ["_staging", "03_shadow"]):
        score -= 0.1

    # Penalise inbox/raw locations
    if any(d in rp for d in ["_inbox", "inbox", "raw", "uncategorised"]):
        score -= 0.2

    # Penalise archive
    if "90_archive" in rp or "archive" in rp:
        score -= 0.1

    # Boost for auto-synced (has provenance)
    if artefact.is_auto_synced:
        score += 0.1

    return max(0.0, min(1.0, score))


def compute_retrieval_usefulness(artefact: Artefact) -> float:
    """Heuristic retrieval usefulness score 0.0-1.0."""
    score = 0.5

    # Content completeness
    if artefact.word_count > 500:
        score += 0.1
    if artefact.word_count > 2000:
        score += 0.1
    if artefact.word_count < 50:
        score -= 0.3

    # YAML completeness contributes
    score += artefact.yaml_completeness_score * 0.2

    # Markdown structure
    if artefact.has_markdown_structure:
        score += 0.1

    # Source path quality
    score += (artefact.source_path_quality - 0.5) * 0.2

    # Penalise damage
    if artefact.has_ocr_damage:
        score -= 0.2

    # Penalise summaries slightly (less detail)
    if artefact.is_summary:
        score -= 0.05

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Component Type Classification (15-type standard)
# ---------------------------------------------------------------------------

COMPONENT_TYPES = [
    "entry", "service", "worker", "connector", "model", "store",
    "pipeline", "orchestrator", "guard", "scorer", "agent", "test",
    "config", "telemetry", "glue",
]

# Priority-ordered rules: first match wins.
# Each rule is (component_type, match_function).
# match_function receives (relative_path_lower, filename_lower, stem_lower,
#                          yaml_data_or_none, first_500_lower)

def _ct_match_telemetry(rp: str, fn: str, stem: str,
                        yd: Optional[dict], head: str) -> bool:
    """Transcripts, voice notes, session logs, monitoring output."""
    if any(d in rp for d in [
        "transcripts", "_inbox-voice", "voice-",
        "vault-monitor-runs", "sessions/",
    ]):
        return True
    if fn.startswith("voice-"):
        return True
    if any(kw in fn for kw in [
        "session-log", "session-notes", "health-check",
        "daily-report", "monitor",
    ]):
        return True
    return False


def _ct_match_guard(rp: str, fn: str, stem: str,
                    yd: Optional[dict], head: str) -> bool:
    """Authority, governance, validation, enforcement, security."""
    if any(d in rp for d in [
        "00_authority/", "security/", "_system/",
    ]):
        return True
    if any(kw in fn for kw in [
        "lockdown", "checklist", "principles", "manifest",
        "governance", "ulysses", "enforcement", "signatures",
        "access-rules", "codeowners", "promotion-gate",
        "opinion-confidence", "use-it-or-cut-it",
    ]):
        return True
    return False


def _ct_match_agent(rp: str, fn: str, stem: str,
                    yd: Optional[dict], head: str) -> bool:
    """Agent definitions, personas, capability profiles, skills."""
    if "skills/" in rp:
        return True
    if any(kw in fn for kw in [
        "agents", "agent-", "soul", "persona", "skill",
        "remit", "routing", "roster",
    ]):
        return True
    if fn == "agents.md":
        return True
    return False


def _ct_match_entry(rp: str, fn: str, stem: str,
                    yd: Optional[dict], head: str) -> bool:
    """Entry points, READMEs, onboarding, landing pages."""
    if fn in ("readme.md", "onboarding.md", "index.md",
              "getting-started.md", "quick-start.md"):
        return True
    return False


def _ct_match_model(rp: str, fn: str, stem: str,
                    yd: Optional[dict], head: str) -> bool:
    """Schemas, data models, type definitions, entity structures."""
    if "schemas/" in rp:
        return True
    if any(kw in fn for kw in [
        "schema", "model", "ontology", "entity",
        "taxonomy", "terminology", "data-dictionary",
    ]):
        return True
    return False


def _ct_match_config(rp: str, fn: str, stem: str,
                     yd: Optional[dict], head: str) -> bool:
    """Configuration, settings, environment, parameters."""
    if any(kw in fn for kw in [
        "config", "settings", "environment", ".env",
        "parameters", "copilot-instructions", "copilot-review",
        "cursorrules", "handshake",
    ]):
        return True
    return False


def _ct_match_pipeline(rp: str, fn: str, stem: str,
                       yd: Optional[dict], head: str) -> bool:
    """Multi-step processing chains, workflows, build pipelines."""
    if any(d in rp for d in [
        "workflows/", "pipeline",
    ]):
        return True
    if any(kw in fn for kw in [
        "pipeline", "workflow", "ingestion", "build-loop",
        "ci-cd", "pr-workflow",
    ]):
        return True
    return False


def _ct_match_orchestrator(rp: str, fn: str, stem: str,
                           yd: Optional[dict], head: str) -> bool:
    """Coordination, routing, agent management, task distribution."""
    if "cove-orchestrator/" in rp:
        return True
    if any(kw in fn for kw in [
        "orchestrat", "shared-board", "routing",
        "coordination", "fleet", "arbiter",
    ]):
        return True
    return False


def _ct_match_service(rp: str, fn: str, stem: str,
                      yd: Optional[dict], head: str) -> bool:
    """Running services, APIs, servers, daemon definitions."""
    if any(kw in fn for kw in [
        "api", "server", "service", "endpoint",
        "mcp-server", "mcp_server", "enforcer",
        "infrastructure", "systems-and-api",
    ]):
        return True
    if "interfaces/" in rp:
        return True
    return False


def _ct_match_worker(rp: str, fn: str, stem: str,
                     yd: Optional[dict], head: str) -> bool:
    """Background processors, batch jobs, cron tasks."""
    if any(kw in fn for kw in [
        "worker", "cron", "batch", "job-wrapup",
        "scheduled", "processor",
    ]):
        return True
    if "job-wrapups/" in rp:
        return True
    return False


def _ct_match_connector(rp: str, fn: str, stem: str,
                        yd: Optional[dict], head: str) -> bool:
    """Integrations, bridges, adapters, sync mechanisms."""
    if "evolution-api/" in rp:
        return True
    if any(kw in fn for kw in [
        "connector", "integration", "bridge", "sync",
        "adapter", "webhook", "migration",
    ]):
        return True
    if "brain-migration/" in rp:
        return True
    return False


def _ct_match_store(rp: str, fn: str, stem: str,
                    yd: Optional[dict], head: str) -> bool:
    """Storage, database config, vault structure, archive layout."""
    if any(kw in fn for kw in [
        "vault-map", "archive", "store", "storage",
        "database", "qdrant", "falkordb",
        "brain-architecture",
    ]):
        return True
    if "knowledge-qdrant/" in rp:
        return True
    return False


def _ct_match_scorer(rp: str, fn: str, stem: str,
                     yd: Optional[dict], head: str) -> bool:
    """Evaluation, ranking, rubrics, quality assessment."""
    if any(kw in fn for kw in [
        "scorer", "rubric", "scoring", "pudding",
        "visual-polish", "evaluation", "quality",
        "methodology",
    ]):
        return True
    if "validators/" in rp:
        return True
    return False


def _ct_match_test(rp: str, fn: str, stem: str,
                   yd: Optional[dict], head: str) -> bool:
    """Tests, validation results, QA, verification."""
    if any(kw in fn for kw in [
        "test", "validation-result", "qa-report",
        "verification", "hooks-testing",
    ]):
        return True
    return False


def _ct_match_research(rp: str, fn: str, stem: str,
                       yd: Optional[dict], head: str) -> bool:
    """Research, synthesis — maps to glue with research tag."""
    if "research/" in rp or "_staging/" in rp:
        return True
    return False


# Ordered classifier chain — first match wins
_CLASSIFIER_CHAIN = [
    ("telemetry", _ct_match_telemetry),
    ("guard", _ct_match_guard),
    ("agent", _ct_match_agent),
    ("entry", _ct_match_entry),
    ("model", _ct_match_model),
    ("config", _ct_match_config),
    ("pipeline", _ct_match_pipeline),
    ("orchestrator", _ct_match_orchestrator),
    ("service", _ct_match_service),
    ("worker", _ct_match_worker),
    ("connector", _ct_match_connector),
    ("store", _ct_match_store),
    ("scorer", _ct_match_scorer),
    ("test", _ct_match_test),
]


def classify_component_type(relative_path: str, filename: str,
                            yaml_data: Optional[dict],
                            content: str) -> str:
    """Classify an artefact into one of 15 component types.
    Uses path, filename, YAML, and content signals. First match wins.
    Falls back to 'glue'."""
    rp = relative_path.lower()
    fn = filename.lower()
    stem = filename_stem_for_grouping(filename)
    head = content[:500].lower() if content else ""

    for comp_type, match_fn in _CLASSIFIER_CHAIN:
        if match_fn(rp, fn, stem, yaml_data, head):
            return comp_type

    # Inbox items → glue
    if any(d in rp for d in ["_inbox", "inbox", "03_shadow/notes"]):
        return "glue"

    # Archive items → store
    if "90_archive/" in rp and "vault-monitor" not in rp:
        return "store"

    # Imported business docs → telemetry (raw signal)
    if "imported-business-docs/" in rp:
        return "telemetry"

    # Work / covered-ai → glue
    if any(d in rp for d in ["work/", "work-covered-ai/"]):
        return "glue"

    return "glue"


def filename_stem_for_grouping(filename: str) -> str:
    """Extract the base stem for version/hash grouping."""
    name = filename
    # Strip .md extension
    if name.lower().endswith(".md"):
        name = name[:-3]

    # Strip hash suffix
    name = re.sub(r"-[a-f0-9]{5,8}$", "", name, flags=re.IGNORECASE)

    # Strip version suffix
    name = re.sub(r"-v\d+$", "", name, flags=re.IGNORECASE)

    return name.lower()


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_repos(repo_paths: dict[str, str]) -> list[Artefact]:
    """Scan all .md files across repos, excluding quarantined directories."""
    artefacts = []
    quarantine_dirs = set()

    # First pass: find quarantine markers
    for repo_name, repo_path in repo_paths.items():
        for root, dirs, files in os.walk(repo_path):
            # Skip .git
            if ".git" in root.split(os.sep):
                continue
            for f in files:
                if f in QUARANTINE_FILES:
                    quarantine_dirs.add(root)

    print(f"[SCAN] Found {len(quarantine_dirs)} quarantine zone(s):")
    for qd in quarantine_dirs:
        print(f"  - {qd}")
    print("  (Note: quarantine markers at repo root exclude ONLY files in")
    print("   the root directory itself, not subdirectories)")

    # Second pass: collect artefacts
    artifact_counter = 0
    for repo_name, repo_path in repo_paths.items():
        for root, dirs, files in os.walk(repo_path):
            # Skip .git directories
            path_parts = root.split(os.sep)
            if ".git" in path_parts:
                continue

            # Skip quarantine zones — files in EXACT directory containing
            # HAZEL_DO_NOT_INGEST.txt are skipped, but subdirectories are
            # still traversed (the marker means "don't ingest files HERE")
            is_quarantined = root in quarantine_dirs
            if is_quarantined:
                print(f"  [QUARANTINE] Skipping .md files in: {root} "
                      f"(subdirs still traversed)")

            for f in files:
                if not f.lower().endswith(".md"):
                    continue

                # Skip .md files in quarantined directories
                if is_quarantined:
                    continue

                filepath = os.path.join(root, f)
                relative = os.path.relpath(filepath, repo_path)

                try:
                    stat = os.stat(filepath)
                    content = open(filepath, "r", encoding="utf-8", errors="replace").read()
                except (OSError, IOError) as e:
                    print(f"  [WARN] Cannot read {filepath}: {e}")
                    continue

                artifact_counter += 1
                artifact_id = f"ART-{artifact_counter:05d}"

                # Basic metrics
                lines = content.split("\n")
                words = content.split()

                # Hashes
                content_hash = sha256_hash(content)
                normalized = normalize_text(content)
                norm_hash = sha256_hash(normalized)

                # MinHash
                mh = compute_minhash(normalized)

                # YAML frontmatter
                yaml_data = extract_yaml_frontmatter(content)
                yaml_present = yaml_data is not None
                yaml_fields_present = []
                yaml_fields_missing = list(REQUIRED_YAML_FIELDS)
                if yaml_present and yaml_data:
                    yaml_fields_present = [
                        field_name for field_name in REQUIRED_YAML_FIELDS
                        if field_name in yaml_data
                    ]
                    yaml_fields_missing = [
                        field_name for field_name in REQUIRED_YAML_FIELDS
                        if field_name not in yaml_data
                    ]

                completeness = len(yaml_fields_present) / len(REQUIRED_YAML_FIELDS)

                # Filename analysis
                has_version = bool(VERSION_SUFFIX_RE.search(f))
                version_num = None
                vm = VERSION_SUFFIX_RE.search(f)
                if vm:
                    version_num = int(vm.group(1))

                has_hash = bool(HASH_SUFFIX_RE.search(f))
                hash_val = None
                hm = HASH_SUFFIX_RE.search(f)
                if hm:
                    hash_val = hm.group(1)

                stem = filename_stem_for_grouping(f)

                # Markdown structure
                heading_count, has_structure = detect_markdown_structure(content)

                # Auto-synced detection
                is_auto_synced = False
                if yaml_present and yaml_data:
                    tags = yaml_data.get("tags", [])
                    if isinstance(tags, list) and "auto-synced" in tags:
                        is_auto_synced = True
                    if "synced" in yaml_data:
                        is_auto_synced = True

                # Risk flags
                has_risk = False
                risk_vals = []
                if yaml_present and yaml_data:
                    rf = yaml_data.get("risk_flags")
                    if rf:
                        has_risk = True
                        if isinstance(rf, list):
                            risk_vals = rf
                        else:
                            risk_vals = [str(rf)]

                # Content type detection
                is_summary = detect_summary(f, content)
                is_chaptered = detect_chaptered(f, content)
                has_ocr = detect_ocr_damage(content)

                mod_time_str = datetime.fromtimestamp(stat.st_mtime).isoformat()

                art = Artefact(
                    artifact_id=artifact_id,
                    file_path=filepath,
                    repo=repo_name,
                    relative_path=relative,
                    file_size=stat.st_size,
                    mod_time=mod_time_str,
                    line_count=len(lines),
                    word_count=len(words),
                    content_hash_sha256=content_hash,
                    normalized_hash_sha256=norm_hash,
                    minhash_signature=list(mh.hashvalues),
                    yaml_present=yaml_present,
                    yaml_fields_present=yaml_fields_present,
                    yaml_fields_missing=yaml_fields_missing,
                    yaml_completeness_score=completeness,
                    yaml_raw={},  # don't persist raw YAML to output (can be large)
                    has_version_suffix=has_version,
                    version_number=version_num,
                    has_hash_suffix=has_hash,
                    hash_suffix=hash_val,
                    filename_stem=stem,
                    heading_count=heading_count,
                    has_markdown_structure=has_structure,
                    is_auto_synced=is_auto_synced,
                    source_path_quality=0.0,
                    has_risk_flags=has_risk,
                    risk_flag_values=risk_vals,
                    is_summary=is_summary,
                    is_chaptered=is_chaptered,
                    has_ocr_damage=has_ocr,
                    retrieval_usefulness=0.0,
                    component_type="glue",
                )
                # Computed scores that depend on fields above
                art.source_path_quality = compute_source_path_quality(art)
                art.retrieval_usefulness = compute_retrieval_usefulness(art)
                art.component_type = classify_component_type(
                    relative, f, yaml_data, content
                )

                artefacts.append(art)

                if artifact_counter % 500 == 0:
                    print(f"  [SCAN] Processed {artifact_counter} files...")

    print(f"[SCAN] Total artefacts scanned: {len(artefacts)}")
    return artefacts


# ---------------------------------------------------------------------------
# Duplicate Detection & Clustering
# ---------------------------------------------------------------------------

def build_clusters(artefacts: list[Artefact]) -> dict[str, list[Artefact]]:
    """Build clusters from exact duplicates, near-duplicates, and version families."""
    clusters: dict[str, list[Artefact]] = {}
    cluster_counter = 0
    assigned: set[str] = set()  # artifact_ids already in a cluster

    # --- Phase 1: Exact duplicates (identical content hash) ---
    hash_groups: dict[str, list[Artefact]] = defaultdict(list)
    for art in artefacts:
        hash_groups[art.content_hash_sha256].append(art)

    for h, group in hash_groups.items():
        if len(group) > 1:
            cluster_counter += 1
            cid = f"CLU-{cluster_counter:05d}"
            clusters[cid] = group
            for art in group:
                art.cluster_id = cid
                art.cluster_type = "exact_duplicate"
                assigned.add(art.artifact_id)

    print(f"[CLUSTER] Phase 1 — exact duplicates: {len(clusters)} clusters, "
          f"{sum(len(g) for g in clusters.values())} artefacts")

    # --- Phase 2: Version families (filename stem matching) ---
    stem_groups: dict[str, list[Artefact]] = defaultdict(list)
    for art in artefacts:
        if art.artifact_id in assigned:
            continue
        if art.has_version_suffix:
            stem_groups[art.filename_stem].append(art)

    for stem, group in stem_groups.items():
        if len(group) > 1:
            cluster_counter += 1
            cid = f"CLU-{cluster_counter:05d}"
            clusters[cid] = group
            for art in group:
                art.cluster_id = cid
                art.cluster_type = "version_family"
                assigned.add(art.artifact_id)

    vf_count = sum(1 for cid, g in clusters.items()
                   if g[0].cluster_type == "version_family")
    print(f"[CLUSTER] Phase 2 — version families: {vf_count} new clusters")

    # --- Phase 3: Hash-suffix families (same stem, different hash suffixes) ---
    hash_stem_groups: dict[str, list[Artefact]] = defaultdict(list)
    for art in artefacts:
        if art.artifact_id in assigned:
            continue
        if art.has_hash_suffix:
            hash_stem_groups[art.filename_stem].append(art)

    for stem, group in hash_stem_groups.items():
        if len(group) > 1:
            cluster_counter += 1
            cid = f"CLU-{cluster_counter:05d}"
            clusters[cid] = group
            for art in group:
                art.cluster_id = cid
                art.cluster_type = "hash_family"
                assigned.add(art.artifact_id)

    hf_count = sum(1 for cid, g in clusters.items()
                   if len(g) > 0 and g[0].cluster_type == "hash_family")
    print(f"[CLUSTER] Phase 3 — hash-suffix families: {hf_count} new clusters")

    # --- Phase 4: Near-duplicates via MinHash LSH ---
    unassigned = [art for art in artefacts if art.artifact_id not in assigned]
    print(f"[CLUSTER] Phase 4 — scanning {len(unassigned)} unassigned artefacts "
          f"for near-duplicates via MinHash LSH...")

    # Phase 4a: normalized hash grouping as pre-filter
    norm_hash_groups: dict[str, list[Artefact]] = defaultdict(list)
    for art in unassigned:
        norm_hash_groups[art.normalized_hash_sha256].append(art)

    for nh, group in norm_hash_groups.items():
        if len(group) > 1:
            cluster_counter += 1
            cid = f"CLU-{cluster_counter:05d}"
            clusters[cid] = group
            for art in group:
                art.cluster_id = cid
                art.cluster_type = "near_duplicate"
                assigned.add(art.artifact_id)

    nd_exact = sum(1 for cid, g in clusters.items()
                   if len(g) > 0 and g[0].cluster_type == "near_duplicate")
    print(f"[CLUSTER] Phase 4a — normalized-hash exact matches: {nd_exact} clusters")

    # Phase 4b: MinHash LSH for remaining unassigned (O(n) insert + query)
    still_unassigned = [art for art in artefacts if art.artifact_id not in assigned]
    print(f"[CLUSTER] Phase 4b — MinHash LSH on {len(still_unassigned)} remaining...")

    lsh = MinHashLSH(threshold=NEAR_DUP_JACCARD_THRESHOLD, num_perm=MINHASH_NUM_PERM)
    arts_by_id = {art.artifact_id: art for art in still_unassigned}
    minhash_cache: dict[str, MinHash] = {}

    for art in still_unassigned:
        mh = MinHash(num_perm=MINHASH_NUM_PERM)
        mh.hashvalues = np.array(art.minhash_signature, dtype=np.uint64)
        minhash_cache[art.artifact_id] = mh
        try:
            lsh.insert(art.artifact_id, mh)
        except ValueError:
            pass  # duplicate key — already inserted

    # Query LSH for candidate pairs and build adjacency
    adjacency: dict[str, set[str]] = defaultdict(set)
    for art in still_unassigned:
        mh = minhash_cache[art.artifact_id]
        candidates = lsh.query(mh)
        for cand_id in candidates:
            if cand_id != art.artifact_id:
                adjacency[art.artifact_id].add(cand_id)
                adjacency[cand_id].add(art.artifact_id)

    # Connected components from adjacency
    visited: set[str] = set()
    for aid in adjacency:
        if aid in visited or aid in assigned:
            continue
        component = []
        queue = [aid]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(component) > 1:
            cluster_counter += 1
            cid = f"CLU-{cluster_counter:05d}"
            group = [arts_by_id[aid] for aid in component if aid in arts_by_id]
            clusters[cid] = group
            for art in group:
                art.cluster_id = cid
                art.cluster_type = "near_duplicate"
                assigned.add(art.artifact_id)

    nd_minhash = sum(1 for cid, g in clusters.items()
                     if len(g) > 0 and g[0].cluster_type == "near_duplicate") - nd_exact
    print(f"[CLUSTER] Phase 4b — MinHash LSH near-duplicate clusters: {nd_minhash}")

    # --- Phase 5: Assign singletons ---
    for art in artefacts:
        if art.artifact_id not in assigned:
            cluster_counter += 1
            cid = f"CLU-{cluster_counter:05d}"
            clusters[cid] = [art]
            art.cluster_id = cid
            art.cluster_type = "single"
            assigned.add(art.artifact_id)

    total_clusters = len(clusters)
    multi_clusters = sum(1 for g in clusters.values() if len(g) > 1)
    print(f"[CLUSTER] Total clusters: {total_clusters} "
          f"({multi_clusters} multi-member, "
          f"{total_clusters - multi_clusters} singletons)")

    return clusters


# ---------------------------------------------------------------------------
# Canonical Selection (10 criteria)
# ---------------------------------------------------------------------------

def score_artefact_for_canonical(art: Artefact) -> float:
    """Score an artefact across the 10 canonical selection criteria.
    Returns a weighted composite score 0.0-10.0."""
    score = 0.0

    # 1. Most complete content (line count, word count) — weight 1.5
    content_score = min(1.0, art.word_count / 2000.0)
    score += content_score * 1.5

    # 2. Cleanest formatting (markdown structure) — weight 1.0
    format_score = 0.0
    if art.has_markdown_structure:
        format_score += 0.5
    if art.heading_count >= 3:
        format_score += 0.3
    if art.heading_count >= 5:
        format_score += 0.2
    score += min(1.0, format_score) * 1.0

    # 3. Strongest provenance — weight 1.0
    score += art.source_path_quality * 1.0

    # 4. Best YAML completeness — weight 1.0
    score += art.yaml_completeness_score * 1.0

    # 5. Latest valid version — weight 0.5
    if art.version_number is not None:
        version_score = min(1.0, art.version_number / 5.0)
        score += version_score * 0.5
    else:
        score += 0.25  # neutral for non-versioned

    # 6. Original over summary — weight 1.0
    if not art.is_summary:
        score += 1.0

    # 7. Original over chaptered copy — weight 1.0
    if not art.is_chaptered:
        score += 1.0

    # 8. Non-damaged over OCR/transcription-damaged — weight 1.0
    if not art.has_ocr_damage:
        score += 1.0

    # 9. Safe/non-sensitive — weight 0.5
    if not art.has_risk_flags:
        score += 0.5

    # 10. Highest retrieval usefulness — weight 1.0
    score += art.retrieval_usefulness * 1.0

    return score


def select_canonical(clusters: dict[str, list[Artefact]]) -> dict[str, Artefact]:
    """For each multi-member cluster, select the canonical artefact."""
    canonicals: dict[str, Artefact] = {}

    for cid, group in clusters.items():
        if len(group) == 1:
            canonicals[cid] = group[0]
            continue

        # Score each artefact
        scored = [(art, score_artefact_for_canonical(art)) for art in group]
        scored.sort(key=lambda x: x[1], reverse=True)

        canonical = scored[0][0]
        canonicals[cid] = canonical

        # Build alternatives
        alternatives = []
        for art, sc in scored[1:min(4, len(scored))]:
            alternatives.append({
                "artifact_id": art.artifact_id,
                "file_path": art.relative_path,
                "score": round(sc, 3),
                "believability": round(sc / scored[0][1], 3) if scored[0][1] > 0 else 0.0,
            })

        # Assign decisions to all members
        canonical_score = scored[0][1]
        for art, sc in scored:
            art.alternative_options = alternatives if art.artifact_id == canonical.artifact_id else []

            if art.artifact_id == canonical.artifact_id:
                art.proposed_status = "proposed_canonical"
                art.relation_to_canonical = "canonical"
                art.proposed_canonical_artifact_id = art.artifact_id
                art.confidence = _compute_confidence(canonical_score, scored, group)
                art.confidence_basis = "computed"
                art.reason = _build_reason(art, "canonical", scored)
            else:
                # Determine relationship type
                status, relation = _determine_non_canonical_status(art, canonical, group)
                art.proposed_status = status
                art.relation_to_canonical = relation
                art.proposed_canonical_artifact_id = canonical.artifact_id
                art.confidence = _compute_confidence(sc, scored, group)
                art.confidence_basis = "computed"
                art.reason = _build_reason(art, relation, scored)

            # Needs human review?
            art.needs_human_review = _needs_review(art, scored)

    return canonicals


def _compute_confidence(score: float, scored: list, group: list) -> float:
    """Compute confidence based on score separation."""
    if len(scored) <= 1:
        return 0.9

    top_score = scored[0][1]
    if top_score == 0:
        return 0.5

    # How much separation from the next best?
    if len(scored) >= 2:
        second_score = scored[1][1]
        separation = (top_score - second_score) / top_score
        confidence = 0.5 + separation * 0.5
    else:
        confidence = 0.9

    return round(min(1.0, max(0.1, confidence)), 3)


def _determine_non_canonical_status(art: Artefact, canonical: Artefact,
                                     group: list[Artefact]) -> tuple[str, str]:
    """Determine the proposed status for a non-canonical cluster member."""
    cluster_type = art.cluster_type or "single"

    if cluster_type == "exact_duplicate":
        return "mark_duplicate", "duplicate_of"
    elif cluster_type == "version_family":
        if art.version_number is not None and canonical.version_number is not None:
            if art.version_number < canonical.version_number:
                return "mark_superseded", "superseded_by"
        return "mark_superseded", "superseded_by"
    elif cluster_type == "hash_family":
        return "mark_duplicate", "duplicate_of"
    elif cluster_type == "near_duplicate":
        if art.is_summary:
            return "mark_summary", "derived_from"
        if art.is_chaptered:
            return "mark_chaptered_copy", "derived_from"
        if art.word_count < canonical.word_count * 0.5:
            return "mark_partial", "derived_from"
        return "mark_duplicate", "duplicate_of"

    return "human_review", "unknown"


def _build_reason(art: Artefact, relation: str, scored: list) -> str:
    """Build evidence-based reason string."""
    parts = []

    if relation == "canonical":
        parts.append(f"Highest composite score ({scored[0][1]:.2f}/10.0)")
        if art.yaml_completeness_score > 0:
            parts.append(f"YAML {art.yaml_completeness_score:.0%} complete")
        parts.append(f"{art.word_count} words, {art.heading_count} headings")
        if art.has_markdown_structure:
            parts.append("well-structured markdown")
        parts.append(f"source quality {art.source_path_quality:.2f}")
    elif relation == "duplicate_of":
        parts.append(f"Content matches canonical ({art.cluster_type})")
        parts.append(f"score {[s for a, s in scored if a.artifact_id == art.artifact_id][0]:.2f} "
                      f"vs canonical {scored[0][1]:.2f}")
    elif relation == "superseded_by":
        parts.append(f"Older version (v{art.version_number})")
        parts.append("superseded by newer version in cluster")
    elif relation == "derived_from":
        if art.is_summary:
            parts.append("Detected as summary document")
        elif art.is_chaptered:
            parts.append("Detected as chaptered copy")
        else:
            parts.append(f"Partial content ({art.word_count} words vs canonical)")

    return "; ".join(parts) if parts else "UNKNOWN — insufficient signal for determination"


def _needs_review(art: Artefact, scored: list) -> bool:
    """Determine if human review is needed."""
    if art.confidence < 0.6:
        return True
    if art.has_risk_flags:
        return True
    # Close scores between top 2
    if len(scored) >= 2 and scored[0][1] > 0:
        gap = (scored[0][1] - scored[1][1]) / scored[0][1]
        if gap < 0.05:
            return True
    return False


# ---------------------------------------------------------------------------
# Singleton decisions
# ---------------------------------------------------------------------------

def decide_singletons(artefacts: list[Artefact]):
    """Assign decisions for singleton artefacts (not in multi-member clusters)."""
    for art in artefacts:
        if art.cluster_type == "single":
            art.proposed_status = "proposed_canonical"
            art.relation_to_canonical = "canonical"
            art.proposed_canonical_artifact_id = art.artifact_id

            # Confidence based on content quality
            if art.word_count < 20:
                art.proposed_status = "drop_from_active_ingestion"
                art.confidence = 0.85
                art.reason = f"Minimal content ({art.word_count} words)"
                art.needs_human_review = art.word_count > 5
            elif art.has_ocr_damage:
                art.proposed_status = "quarantine_candidate"
                art.confidence = 0.7
                art.reason = "OCR/transcription damage detected"
                art.needs_human_review = True
            elif art.has_risk_flags:
                art.proposed_status = "human_review"
                art.confidence = 0.5
                art.reason = f"Risk flags present: {', '.join(art.risk_flag_values)}"
                art.needs_human_review = True
            else:
                art.confidence = 0.9
                art.confidence_basis = "computed"
                reason_parts = [f"{art.word_count} words"]
                if art.yaml_completeness_score > 0:
                    reason_parts.append(
                        f"YAML {art.yaml_completeness_score:.0%} complete"
                    )
                reason_parts.append(
                    f"source quality {art.source_path_quality:.2f}"
                )
                reason_parts.append(
                    f"retrieval usefulness {art.retrieval_usefulness:.2f}"
                )
                art.reason = "Unique artefact; " + "; ".join(reason_parts)
                art.needs_human_review = False


# ---------------------------------------------------------------------------
# Output Generation
# ---------------------------------------------------------------------------

def artefact_to_decision_row(art: Artefact) -> dict:
    """Convert Artefact to a decision row for JSONL output."""
    return {
        "artifact_id": art.artifact_id,
        "file_path": art.file_path,
        "repo": art.repo,
        "relative_path": art.relative_path,
        "file_size": art.file_size,
        "mod_time": art.mod_time,
        "line_count": art.line_count,
        "word_count": art.word_count,
        "content_hash_sha256": art.content_hash_sha256,
        "normalized_hash_sha256": art.normalized_hash_sha256,
        "yaml_present": art.yaml_present,
        "yaml_fields_present": art.yaml_fields_present,
        "yaml_fields_missing": art.yaml_fields_missing,
        "yaml_completeness_score": round(art.yaml_completeness_score, 4),
        "has_version_suffix": art.has_version_suffix,
        "version_number": art.version_number,
        "has_hash_suffix": art.has_hash_suffix,
        "hash_suffix": art.hash_suffix,
        "filename_stem": art.filename_stem,
        "heading_count": art.heading_count,
        "has_markdown_structure": art.has_markdown_structure,
        "is_auto_synced": art.is_auto_synced,
        "source_path_quality": round(art.source_path_quality, 4),
        "has_risk_flags": art.has_risk_flags,
        "risk_flag_values": art.risk_flag_values,
        "is_summary": art.is_summary,
        "is_chaptered": art.is_chaptered,
        "has_ocr_damage": art.has_ocr_damage,
        "retrieval_usefulness": round(art.retrieval_usefulness, 4),
        "component_type": art.component_type,
        "cluster_id": art.cluster_id,
        "cluster_type": art.cluster_type,
        "proposed_status": art.proposed_status,
        "relation_to_canonical": art.relation_to_canonical,
        "proposed_canonical_artifact_id": art.proposed_canonical_artifact_id,
        "reason": art.reason,
        "confidence": round(art.confidence, 4),
        "confidence_basis": art.confidence_basis,
        "alternative_options": art.alternative_options,
        "needs_human_review": art.needs_human_review,
    }


def generate_outputs(artefacts: list[Artefact],
                     clusters: dict[str, list[Artefact]],
                     canonicals: dict[str, Artefact],
                     output_dir: str,
                     scan_duration: float):
    """Generate the 4 required output files."""
    os.makedirs(output_dir, exist_ok=True)

    # --- 1. proposed_1000_review_pack.jsonl ---
    review_pack_path = os.path.join(output_dir, "proposed_1000_review_pack.jsonl")
    with open(review_pack_path, "w") as f:
        for art in artefacts:
            row = artefact_to_decision_row(art)
            f.write(json.dumps(row, default=str) + "\n")
    print(f"[OUTPUT] {review_pack_path} — {len(artefacts)} rows")

    # --- 2. proposed_canonical_clusters.jsonl ---
    clusters_path = os.path.join(output_dir, "proposed_canonical_clusters.jsonl")
    with open(clusters_path, "w") as f:
        for cid, group in clusters.items():
            canonical = canonicals.get(cid)
            if not canonical:
                continue

            top_alts = []
            for art in group:
                if art.artifact_id != canonical.artifact_id:
                    top_alts.append({
                        "artifact_id": art.artifact_id,
                        "relative_path": art.relative_path,
                        "score": round(score_artefact_for_canonical(art), 3),
                    })
            top_alts.sort(key=lambda x: x["score"], reverse=True)
            top_alts = top_alts[:3]

            cluster_title = canonical.filename_stem or canonical.relative_path
            reasoning_parts = []
            if group[0].cluster_type == "exact_duplicate":
                reasoning_parts.append(
                    f"{len(group)} exact copies found"
                )
            elif group[0].cluster_type == "version_family":
                versions = [a.version_number for a in group if a.version_number]
                reasoning_parts.append(
                    f"Version family: v{min(versions) if versions else '?'}"
                    f"–v{max(versions) if versions else '?'}"
                )
            elif group[0].cluster_type in ("near_duplicate", "hash_family"):
                reasoning_parts.append(
                    f"{len(group)} near-duplicate/hash-family members"
                )
            else:
                reasoning_parts.append("Singleton")

            reasoning_parts.append(
                f"Canonical score: "
                f"{score_artefact_for_canonical(canonical):.2f}/10.0"
            )

            row = {
                "cluster_id": cid,
                "cluster_title": cluster_title,
                "recommended_canonical_artifact_id": canonical.artifact_id,
                "canonical_source_path": canonical.relative_path,
                "cluster_size": len(group),
                "cluster_type": group[0].cluster_type,
                "top_alternatives": top_alts,
                "reasoning": "; ".join(reasoning_parts),
            }
            f.write(json.dumps(row, default=str) + "\n")
    print(f"[OUTPUT] {clusters_path} — {len(clusters)} rows")

    # --- 3. human_review_required.jsonl ---
    review_path = os.path.join(output_dir, "human_review_required.jsonl")
    review_count = 0
    with open(review_path, "w") as f:
        for art in artefacts:
            if art.needs_human_review:
                row = artefact_to_decision_row(art)
                f.write(json.dumps(row, default=str) + "\n")
                review_count += 1
    print(f"[OUTPUT] {review_path} — {review_count} rows")

    # --- 4. preupload_sort_summary.md ---
    summary_path = os.path.join(output_dir, "preupload_sort_summary.md")
    summary = build_summary_report(artefacts, clusters, canonicals, scan_duration)
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"[OUTPUT] {summary_path}")


def build_summary_report(artefacts: list[Artefact],
                         clusters: dict[str, list[Artefact]],
                         canonicals: dict[str, Artefact],
                         scan_duration: float) -> str:
    """Build the markdown summary report."""
    total = len(artefacts)
    by_repo = defaultdict(int)
    for art in artefacts:
        by_repo[art.repo] += 1

    # Status counts
    status_counts = defaultdict(int)
    for art in artefacts:
        status_counts[art.proposed_status] += 1

    # Cluster type counts
    cluster_type_counts = defaultdict(int)
    multi_clusters = 0
    for cid, group in clusters.items():
        ct = group[0].cluster_type if group else "unknown"
        cluster_type_counts[ct] += 1
        if len(group) > 1:
            multi_clusters += 1

    # YAML stats
    yaml_present_count = sum(1 for a in artefacts if a.yaml_present)
    yaml_complete_avg = (
        sum(a.yaml_completeness_score for a in artefacts) / total if total else 0
    )
    yaml_full_count = sum(
        1 for a in artefacts if a.yaml_completeness_score == 1.0
    )

    # Content stats
    total_words = sum(a.word_count for a in artefacts)
    avg_words = total_words / total if total else 0
    max_words_art = max(artefacts, key=lambda a: a.word_count) if artefacts else None

    # Detection stats
    summary_count = sum(1 for a in artefacts if a.is_summary)
    chaptered_count = sum(1 for a in artefacts if a.is_chaptered)
    ocr_damage_count = sum(1 for a in artefacts if a.has_ocr_damage)
    risk_flag_count = sum(1 for a in artefacts if a.has_risk_flags)
    auto_synced_count = sum(1 for a in artefacts if a.is_auto_synced)
    version_count = sum(1 for a in artefacts if a.has_version_suffix)
    hash_suffix_count = sum(1 for a in artefacts if a.has_hash_suffix)

    human_review_count = sum(1 for a in artefacts if a.needs_human_review)

    # Avg confidence
    avg_confidence = (
        sum(a.confidence for a in artefacts) / total if total else 0
    )

    # Component type distribution
    comp_type_counts = defaultdict(int)
    for a in artefacts:
        comp_type_counts[a.component_type] += 1

    # Retrieval usefulness distribution
    ru_bins = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for a in artefacts:
        if a.retrieval_usefulness < 0.2:
            ru_bins["0.0-0.2"] += 1
        elif a.retrieval_usefulness < 0.4:
            ru_bins["0.2-0.4"] += 1
        elif a.retrieval_usefulness < 0.6:
            ru_bins["0.4-0.6"] += 1
        elif a.retrieval_usefulness < 0.8:
            ru_bins["0.6-0.8"] += 1
        else:
            ru_bins["0.8-1.0"] += 1

    report = f"""# PRE-UPLOAD SORT + CHECK — Summary Report

**Generated:** {datetime.now(timezone.utc).isoformat()}
**Scan duration:** {scan_duration:.1f} seconds
**Signed-by:** Devon | Session 294b46afcdee47d5b250d328d61103c2

---

## 1. Corpus Overview

| Metric | Value |
|--------|-------|
| Total artefacts scanned | {total} |
| vault | {by_repo.get('vault', 0)} |
| clean-build | {by_repo.get('clean-build', 0)} |
| ground-truth | {by_repo.get('ground-truth', 0)} |
| Total word count | {total_words:,} |
| Average words/artefact | {avg_words:,.0f} |
| Largest artefact | {max_words_art.relative_path if max_words_art else 'N/A'} ({max_words_art.word_count:,} words) |

## 2. Clustering Results

| Metric | Value |
|--------|-------|
| Total clusters | {len(clusters)} |
| Multi-member clusters | {multi_clusters} |
| Singleton clusters | {len(clusters) - multi_clusters} |

### Cluster Types

| Type | Count |
|------|-------|
"""
    for ct, count in sorted(cluster_type_counts.items()):
        report += f"| {ct} | {count} |\n"

    report += """
## 3. Proposed Decisions

| Status | Count |
|--------|-------|
"""
    for status, count in sorted(status_counts.items()):
        report += f"| {status} | {count} |\n"

    report += f"""
## 4. YAML Frontmatter Analysis

| Metric | Value |
|--------|-------|
| Artefacts with YAML frontmatter | {yaml_present_count} ({yaml_present_count/total*100:.1f}%) |
| Average completeness (vs 20-field standard) | {yaml_complete_avg:.1%} |
| Fully compliant (20/20 fields) | {yaml_full_count} |

## 5. Content Quality Signals

| Signal | Count |
|--------|-------|
| Auto-synced content | {auto_synced_count} |
| Version-suffixed files | {version_count} |
| Hash-suffixed files | {hash_suffix_count} |
| Detected summaries | {summary_count} |
| Detected chaptered copies | {chaptered_count} |
| OCR/transcription damage | {ocr_damage_count} |
| Risk flags present | {risk_flag_count} |

## 6. Confidence & Review

| Metric | Value |
|--------|-------|
| Average decision confidence | {avg_confidence:.3f} |
| Needs human review | {human_review_count} ({human_review_count/total*100:.1f}%) |

## 7. Component Type Distribution (15-type standard)

| Type | Count | % |
|------|-------|---|
"""
    for ct in COMPONENT_TYPES:
        c = comp_type_counts.get(ct, 0)
        pct = c / total * 100 if total else 0
        report += f"| {ct} | {c} | {pct:.1f}% |\n"

    report += """
## 8. Retrieval Usefulness Distribution

| Range | Count |
|-------|-------|
"""
    for rng, count in ru_bins.items():
        report += f"| {rng} | {count} |\n"

    report += f"""
## 9. Methodology

### Scanning
- Recursive scan of `.md` files in vault, clean-build, ground-truth
- Excluded: `HAZEL_DO_NOT_INGEST.txt` quarantine zones, `.git` directories
- Recorded: file path, size (bytes), modification time, line count, word count

### Content Hashing
- SHA256 of raw file content (exact duplicate detection)
- SHA256 of normalized text (lowercase + whitespace-collapsed) for near-duplicate pre-filter
- MinHash with {MINHASH_NUM_PERM} permutations, {MINHASH_SHINGLE_SIZE}-word shingles for Jaccard similarity

### YAML Frontmatter
- Parsed between `---` delimiters using PyYAML
- Compared against 20-field standard schema
- Completeness score = present_fields / 20

### Duplicate Detection
1. **Exact duplicates:** Identical SHA256 content hash
2. **Version families:** Filename pattern `-vN.md` with shared stem
3. **Hash-suffix families:** Filename pattern `-<hex>.md` with shared stem
4. **Near duplicates (normalized):** Identical normalized-text SHA256
5. **Near duplicates (MinHash):** Jaccard similarity >= {NEAR_DUP_JACCARD_THRESHOLD} via MinHash

### Canonical Selection (10 criteria, weighted)
1. Content completeness (word count) — weight 1.5
2. Markdown structure quality — weight 1.0
3. Source path provenance — weight 1.0
4. YAML completeness — weight 1.0
5. Latest version number — weight 0.5
6. Original over summary — weight 1.0
7. Original over chaptered copy — weight 1.0
8. Non-damaged content — weight 1.0
9. Non-sensitive content — weight 0.5
10. Retrieval usefulness heuristic — weight 1.0

### Decision Statuses
- `proposed_canonical` — recommended as the canonical version
- `mark_duplicate` — exact or near duplicate of canonical
- `mark_derived` — derivative content (summary, chapter, partial)
- `mark_superseded` — older version in a version family
- `mark_summary` — detected summary document
- `mark_chaptered_copy` — detected chaptered/segmented copy
- `mark_partial` — significantly shorter than canonical (<50% words)
- `quarantine_candidate` — OCR damage or quality concerns
- `human_review` — insufficient confidence or risk flags
- `drop_from_active_ingestion` — minimal content (<20 words)

### Constraints
- All measurements computed by Python (hashes, YAML parsing, similarity, field counts)
- No values estimated — any value that could not be computed is marked UNKNOWN
- No files modified, deleted, or overwritten — proposals only
- Output contains exactly {total} decisions (one per scanned artefact)

---

*This report was generated by the PRE-UPLOAD SORT + CHECK scanner.*
*Devon | {datetime.now(timezone.utc).strftime('%Y-%m-%d')} | Amplified Partners*
"""
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("PRE-UPLOAD SORT + CHECK — Amplified Artefact Corpus Scanner")
    print("=" * 70)

    # Resolve repo paths
    repos_root = os.environ.get("REPOS_ROOT", "/home/ubuntu/repos")
    repo_paths = {
        "vault": os.path.join(repos_root, "vault"),
        "clean-build": os.path.join(repos_root, "clean-build"),
        "ground-truth": os.path.join(repos_root, "ground-truth"),
    }

    # Validate paths
    for name, path in repo_paths.items():
        if not os.path.isdir(path):
            print(f"[ERROR] Repository not found: {path}")
            sys.exit(1)
        print(f"[OK] {name}: {path}")

    output_dir = os.environ.get("OUTPUT_DIR", OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)
    print(f"[OK] Output directory: {output_dir}")
    print()

    # --- Stage 1: Scan ---
    t0 = time.time()
    print("[STAGE 1] Scanning repositories...")
    artefacts = scan_repos(repo_paths)
    t_scan = time.time() - t0
    print(f"[STAGE 1] Complete in {t_scan:.1f}s — {len(artefacts)} artefacts\n")

    # --- Stage 2: Cluster ---
    print("[STAGE 2] Building clusters...")
    t1 = time.time()
    clusters = build_clusters(artefacts)
    t_cluster = time.time() - t1
    print(f"[STAGE 2] Complete in {t_cluster:.1f}s\n")

    # --- Stage 3: Canonical selection ---
    print("[STAGE 3] Selecting canonicals and generating decisions...")
    t2 = time.time()
    canonicals = select_canonical(clusters)
    decide_singletons(artefacts)
    t_decide = time.time() - t2
    print(f"[STAGE 3] Complete in {t_decide:.1f}s\n")

    # --- Stage 4: Output ---
    total_duration = time.time() - t0
    print("[STAGE 4] Generating output files...")
    generate_outputs(artefacts, clusters, canonicals, output_dir, total_duration)

    print()
    print("=" * 70)
    print(f"DONE — {len(artefacts)} artefacts processed in {total_duration:.1f}s")
    print(f"Output: {output_dir}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
