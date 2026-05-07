"""
Tests for the dead letter queue.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

import pytest

from ..dlq import DeadLetterQueue


@pytest.fixture
def dlq(tmp_path):
    return DeadLetterQueue(tmp_path / "test.db")


def test_add_and_count(dlq):
    dlq.add("/tmp/a.md", "classify", "timeout")
    dlq.add("/tmp/b.md", "classify", "parse error")
    assert dlq.count() == 2


def test_add_increments_attempts(dlq):
    dlq.add("/tmp/a.md", "classify", "timeout")
    dlq.add("/tmp/a.md", "classify", "timeout again")
    entries = dlq.get_all()
    assert len(entries) == 1
    assert entries[0].attempts == 2


def test_get_retryable(dlq):
    dlq.add("/tmp/a.md", "classify", "err")
    dlq.add("/tmp/a.md", "classify", "err")
    dlq.add("/tmp/a.md", "classify", "err")
    dlq.add("/tmp/a.md", "classify", "err")  # 4th attempt

    retryable = dlq.get_retryable(max_retries=3)
    assert len(retryable) == 0  # exceeded limit


def test_remove(dlq):
    dlq.add("/tmp/a.md", "classify", "err")
    dlq.remove("/tmp/a.md")
    assert dlq.count() == 0


def test_clear(dlq):
    dlq.add("/tmp/a.md", "classify", "err")
    dlq.add("/tmp/b.md", "write", "err")
    removed = dlq.clear()
    assert removed == 2
    assert dlq.count() == 0
