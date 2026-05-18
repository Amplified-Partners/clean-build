"""Vellum Interceptor — agent action middleware.

Every agent action auto-POSTs to the Ledger before execution.
The agent cannot sneeze without the Ledger recording it.

Usage:
    from vellum.interceptor import LedgerInterceptor

    ledger = LedgerInterceptor(
        agent_name="Devon",
        model="claude-sonnet-4-20250514",
        knowledge_cutoff="2025-04-01",
        ledger_url="http://135.181.161.131:8410",
    )

    # Decorator pattern
    @ledger.action("deploying vellum-v6 to Beast")
    def deploy():
        ...

    # Context manager pattern
    with ledger.action_context("running tests"):
        subprocess.run(["pytest", "tests/"])

    # Direct fire (fire-and-forget)
    ledger.record("completed PR review", epistemic_tier="STRUCTURED")

Devon-b5dc | 2026-05-18
"""

from vellum.interceptor._middleware import LedgerInterceptor

__all__ = ["LedgerInterceptor"]
