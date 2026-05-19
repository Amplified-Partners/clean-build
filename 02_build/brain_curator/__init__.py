"""brain_curator — post-write curation layer for the Amplified Brain.

Chunks are evidence; packets are meaning.

This module reads existing knowledge_vectors and produces governed
knowledge packets without mutating raw source content. It implements
stages 3.5-9 as a post-write layer on top of the canonical ingestion
pipeline (AMP-302).

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""
