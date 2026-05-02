"""Health check module for the Sovereign Fleet agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HealthStatus:
    status: str  # "healthy", "degraded", "unhealthy"
    agent_name: str
    role: str
    model: str
    ibac_rules_loaded: int
    ibac_enabled: bool
    litellm_reachable: bool = False
    workspace_writable: bool = False

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"
