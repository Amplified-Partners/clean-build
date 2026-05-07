"""
Tests for the classification stage.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from pathlib import Path

from ..models import PuddingTaxonomy
from ..stages.classify import classify_value, is_already_classified, is_boilerplate


def test_is_boilerplate():
    assert is_boilerplate(Path("/tmp/LICENSE.md"))
    assert is_boilerplate(Path("/tmp/README.md"))
    assert is_boilerplate(Path("/tmp/changelog.md"))
    assert not is_boilerplate(Path("/tmp/strategy-notes.md"))
    assert not is_boilerplate(Path("/tmp/2026-04-01_pricing_analysis.md"))


def test_is_already_classified(tmp_path):
    # File with dimensions in frontmatter
    classified = tmp_path / "classified.md"
    classified.write_text("---\ntitle: Test\ndimensions:\n  - pricing\n---\nContent here")
    assert is_already_classified(classified)

    # File without dimensions
    unclassified = tmp_path / "unclassified.md"
    unclassified.write_text("---\ntitle: Test\n---\nContent here")
    assert not is_already_classified(unclassified)

    # File without frontmatter
    no_fm = tmp_path / "nofm.md"
    no_fm.write_text("Just some content without frontmatter")
    assert not is_already_classified(no_fm)


def test_classify_value_high():
    tax = PuddingTaxonomy(
        type="framework",
        dimensions=["pricing", "sales", "customer_retention"],
        actionable="ready_to_use",
        status="proven",
        confidence=0.95,
    )
    c = classify_value(tax)
    assert c.include is True
    assert c.value == "high"


def test_classify_value_medium():
    tax = PuddingTaxonomy(
        type="technique",
        dimensions=["pricing", "sales"],
        actionable="needs_adaptation",
        status="tested_internal",
        confidence=0.7,
    )
    c = classify_value(tax)
    assert c.include is True
    assert c.value == "medium"


def test_classify_value_low_hypothesis():
    tax = PuddingTaxonomy(
        type="hypothesis",
        dimensions=["pricing"],
        status="hypothesis",
    )
    c = classify_value(tax)
    assert c.include is False
    assert c.value == "low"


def test_classify_value_low_few_dimensions():
    tax = PuddingTaxonomy(
        type="principle",
        dimensions=["pricing"],
        actionable="ready_to_use",
        status="proven",
    )
    c = classify_value(tax)
    assert c.include is False
    assert c.value == "low"
