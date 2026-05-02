"""Tests for the IBAC Cedar policy engine.

Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
"""

from pathlib import Path

import pytest

from src.ibac import AuthzRequest, Decision, PolicyEngine

PROD_POLICY = str(Path(__file__).parent.parent.parent / "policies" / "prod.cedar")


@pytest.fixture
def engine() -> PolicyEngine:
    e = PolicyEngine()
    count = e.load_file(PROD_POLICY)
    assert count > 0, f"No rules loaded from {PROD_POLICY}"
    return e


# ── Tier 1: Read-only recon ────────────────────────────────────────


class TestTier1:
    def test_any_agent_can_read_file(self, engine: PolicyEngine) -> None:
        for agent in ["Kimmy", "Alpha", "Charlie"]:
            r = engine.evaluate(
                AuthzRequest(principal=agent, action="read_file", resource="/workspace/src/main.py")
            )
            assert r.decision == Decision.ALLOW, f"{agent} should be able to read files"

    def test_any_agent_can_git_log(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(principal="Charlie", action="git_log", resource="/workspace")
        )
        assert r.decision == Decision.ALLOW

    def test_any_agent_can_grep(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(principal="Alpha", action="grep_search", resource="/workspace")
        )
        assert r.decision == Decision.ALLOW

    def test_any_agent_can_view_metrics(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(principal="Kimmy", action="view_metrics", resource="/metrics")
        )
        assert r.decision == Decision.ALLOW


# ── Tier 2: Active probing ─────────────────────────────────────────


class TestTier2:
    def test_charlie_write_with_approval(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Charlie",
                action="write_file",
                resource="/workspace/worktrees/fix-123/main.py",
                context={"approved_by_analyst": True},
            )
        )
        assert r.decision == Decision.ALLOW

    def test_charlie_write_without_approval(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Charlie",
                action="write_file",
                resource="/workspace/worktrees/fix-123/main.py",
                context={"approved_by_analyst": False},
            )
        )
        assert r.decision == Decision.DENY

    def test_charlie_write_outside_worktrees(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Charlie",
                action="write_file",
                resource="/workspace/src/main.py",
                context={"approved_by_analyst": True},
            )
        )
        assert r.decision == Decision.DENY


# ── Tier 3: Destructive operations ─────────────────────────────────


class TestTier3:
    def test_kimmy_merge_with_full_approval(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Kimmy",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            )
        )
        assert r.decision == Decision.ALLOW

    def test_kimmy_merge_without_arbiter(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Kimmy",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": False, "intent_token_valid": True},
            )
        )
        assert r.decision == Decision.DENY

    def test_kimmy_merge_without_intent_token(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Kimmy",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": False},
            )
        )
        assert r.decision == Decision.DENY

    def test_alpha_deploy_with_full_approval(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Alpha",
                action="deploy_production",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            )
        )
        assert r.decision == Decision.ALLOW

    def test_charlie_cannot_merge(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Charlie",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            )
        )
        assert r.decision == Decision.DENY

    def test_charlie_cannot_deploy(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Charlie",
                action="deploy_production",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            )
        )
        assert r.decision == Decision.DENY

    def test_charlie_cannot_shell(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Charlie",
                action="execute_shell",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            )
        )
        assert r.decision == Decision.DENY


# ── Absolute deny ──────────────────────────────────────────────────


class TestAbsoluteDeny:
    def test_no_agent_reads_policy_file(self, engine: PolicyEngine) -> None:
        for agent in ["Kimmy", "Alpha", "Charlie"]:
            r = engine.evaluate(
                AuthzRequest(
                    principal=agent,
                    action="read_file",
                    resource="/etc/openclaw/policies/prod.cedar",
                )
            )
            assert r.decision == Decision.DENY, f"{agent} should not read policy file"

    def test_no_agent_reads_env_file(self, engine: PolicyEngine) -> None:
        for agent in ["Kimmy", "Alpha", "Charlie"]:
            r = engine.evaluate(
                AuthzRequest(
                    principal=agent,
                    action="read_file",
                    resource="/workspace/.env",
                )
            )
            assert r.decision == Decision.DENY, f"{agent} should not read .env"


# ── Default deny ───────────────────────────────────────────────────


class TestDefaultDeny:
    def test_unknown_action_denied(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Kimmy",
                action="delete_database",
                resource="/workspace",
            )
        )
        assert r.decision == Decision.DENY

    def test_unknown_agent_denied(self, engine: PolicyEngine) -> None:
        r = engine.evaluate(
            AuthzRequest(
                principal="Rogue",
                action="write_file",
                resource="/workspace/worktrees/fix/main.py",
                context={"approved_by_analyst": True},
            )
        )
        assert r.decision == Decision.DENY
