#!/usr/bin/env python3
"""
Validate Cedar policy files — checks syntax and reports rules found.

Usage: python scripts/validate-policies.py policies/

Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
"""

import sys
from pathlib import Path

# Add agent src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from src.ibac import PolicyEngine


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: validate-policies.py <policy_dir>")
        sys.exit(1)

    policy_dir = sys.argv[1]
    # Validate prod.cedar specifically (dev.cedar has relaxed rules by design)
    prod_path = Path(policy_dir) / "prod.cedar"
    engine = PolicyEngine()
    if prod_path.exists():
        count = engine.load_file(str(prod_path))
    else:
        count = engine.load_directory(policy_dir)

    if count == 0:
        print(f"WARNING: No rules found in {policy_dir}")
        sys.exit(1)

    print(f"Loaded {count} rules from {policy_dir}")

    # Validate by running test evaluations
    from src.ibac import AuthzRequest

    tests = [
        # Tier 1: should allow any agent to read
        (
            AuthzRequest(principal="Charlie", action="read_file", resource="/workspace/README.md"),
            "ALLOW",
            "Tier 1: Charlie reads a file",
        ),
        # Tier 2: Charlie write without approval = deny
        (
            AuthzRequest(
                principal="Charlie",
                action="write_file",
                resource="/workspace/worktrees/fix/main.py",
                context={"approved_by_analyst": False},
            ),
            "DENY",
            "Tier 2: Charlie writes without approval",
        ),
        # Tier 2: Charlie write with approval = allow
        (
            AuthzRequest(
                principal="Charlie",
                action="write_file",
                resource="/workspace/worktrees/fix/main.py",
                context={"approved_by_analyst": True},
            ),
            "ALLOW",
            "Tier 2: Charlie writes with approval",
        ),
        # Tier 3: Kimmy merge without approval = deny
        (
            AuthzRequest(
                principal="Kimmy",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": False, "intent_token_valid": True},
            ),
            "DENY",
            "Tier 3: Kimmy merges without arbiter approval",
        ),
        # Tier 3: Kimmy merge with full approval = allow
        (
            AuthzRequest(
                principal="Kimmy",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            ),
            "ALLOW",
            "Tier 3: Kimmy merges with full approval",
        ),
        # Absolute deny: read policy file
        (
            AuthzRequest(
                principal="Kimmy",
                action="read_file",
                resource="/etc/openclaw/policies/prod.cedar",
            ),
            "DENY",
            "Absolute deny: read policy file",
        ),
        # Absolute deny: read .env
        (
            AuthzRequest(
                principal="Alpha",
                action="read_file",
                resource="/workspace/.env",
            ),
            "DENY",
            "Absolute deny: read .env",
        ),
        # Charlie cannot merge (not in Tier 3 principals)
        (
            AuthzRequest(
                principal="Charlie",
                action="merge_pr",
                resource="/workspace",
                context={"approved_by_arbiter": True, "intent_token_valid": True},
            ),
            "DENY",
            "Charlie cannot merge PRs",
        ),
    ]

    passed = 0
    failed = 0
    for req, expected, desc in tests:
        result = engine.evaluate(req)
        actual = result.decision.value
        ok = actual == expected
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {desc}: expected={expected} got={actual}")
        if not ok:
            print(f"         reason: {result.reason}")

    print(f"\nResults: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
