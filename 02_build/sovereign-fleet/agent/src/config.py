"""
Configuration models for the OpenClaw Sovereign Fleet agent.

Each entity container loads its own config from:
  1. Environment variables (AGENT_ROLE, MODEL_OVERRIDE, etc.)
  2. Entity YAML config mounted at /etc/openclaw/entity.yaml
  3. Defaults baked into this module
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AgentRole(str, Enum):
    ORCHESTRATOR = "ORCHESTRATOR"
    ARBITER = "ARBITER"
    PLUMBER = "PLUMBER"


class ModelOverride(str, Enum):
    KIMI_K2 = "kimi_k2"
    CLAUDE_OPUS = "claude_opus"
    DEEPSEEK_V4 = "deepseek_v4"


# Maps MODEL_OVERRIDE env values to LiteLLM model identifiers.
MODEL_ROUTING: dict[str, str] = {
    "kimi_k2": os.environ.get("LITELLM_MODEL_KIMI", "openai/moonshot-v1-auto"),
    "claude_opus": os.environ.get("LITELLM_MODEL_OPUS", "anthropic/claude-sonnet-4-20250514"),
    "deepseek_v4": os.environ.get("LITELLM_MODEL_DEEPSEEK", "deepseek/deepseek-chat"),
}


class EntityConfig(BaseModel):
    """Per-entity configuration loaded from YAML."""

    name: str = "unnamed"
    display_name: str = "Agent"
    role: AgentRole = AgentRole.PLUMBER
    model: str = "deepseek/deepseek-chat"
    temperature: float = 0.0
    max_tokens: int = 8192
    workspace: str = "/workspace"
    description: str = ""


class Settings(BaseSettings):
    """Root settings — sourced from environment variables."""

    agent_role: AgentRole = AgentRole.PLUMBER
    model_override: str = "deepseek_v4"
    ibac_enabled: bool = True
    policy_dir: str = "/etc/openclaw/policies"
    entity_config_path: str = "/etc/openclaw/entity.yaml"

    litellm_base_url: str = Field(default="http://litellm:4000", alias="LITELLM_BASE_URL")
    litellm_api_key: str = Field(default="", alias="LITELLM_API_KEY")

    workspace_dir: str = "/workspace"
    log_level: str = "INFO"
    port: int = 8000

    class Config:
        env_prefix = ""
        case_sensitive = False


def load_entity_config(path: str | None = None) -> EntityConfig:
    """Load entity config from YAML, falling back to env-derived defaults."""
    config_path = Path(path) if path else Path("/etc/openclaw/entity.yaml")
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return EntityConfig(**data)

    # Derive from environment
    settings = Settings()
    model_id = MODEL_ROUTING.get(settings.model_override, settings.model_override)
    return EntityConfig(
        name=os.environ.get("HOSTNAME", "agent"),
        role=settings.agent_role,
        model=model_id,
        workspace=settings.workspace_dir,
    )
