"""
Action definitions for the Sovereign Fleet.

Each action maps to a Cedar Action:: identifier and defines
what the agent can do. The IBAC engine authorizes each action
before execution.

Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
"""

from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    # Tier 1: Read-only recon
    READ_FILE = "read_file"
    GIT_LOG = "git_log"
    GREP_SEARCH = "grep_search"
    VIEW_METRICS = "view_metrics"

    # Tier 2: Active probing
    WRITE_FILE = "write_file"

    # Tier 3: Destructive operations
    MERGE_PR = "merge_pr"
    DEPLOY_PRODUCTION = "deploy_production"
    EXECUTE_SHELL = "execute_shell"


# Tier classification for logging and UI display.
ACTION_TIERS: dict[Action, int] = {
    Action.READ_FILE: 1,
    Action.GIT_LOG: 1,
    Action.GREP_SEARCH: 1,
    Action.VIEW_METRICS: 1,
    Action.WRITE_FILE: 2,
    Action.MERGE_PR: 3,
    Action.DEPLOY_PRODUCTION: 3,
    Action.EXECUTE_SHELL: 3,
}
