"""Application settings.

Loads ``config/default.yaml``, then applies a small set of environment-variable
overrides (the ones Docker injects). The resulting nested dict is what feeds the
dependency-injector ``Container`` configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Repo root: src/jarvis/config/settings.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "default.yaml"


class TemporalSettings(BaseModel):
    host: str = "localhost:4004"
    namespace: str = "default"
    task_queue: str = "jarvis-agent-queue"


class ScheduleSettings(BaseModel):
    cron: str = "*/15 8-17 * * 1-5"
    timezone: str = "Europe/Berlin"
    enabled: bool = True


class LLMSettings(BaseModel):
    default_model: str = "openai:gpt-5.5"
    interactive_model: str | None = None  # model for user chat; falls back to default_model
    model_override: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4096


class PostgresSettings(BaseModel):
    dsn: str = "postgresql://temporal:temporal@localhost:4003/jarvis"
    pool_min_size: int = 2
    pool_max_size: int = 10


class EmbeddingSettings(BaseModel):
    model: str = "nomic-ai/nomic-embed-text-v1.5"
    dim: int = 768


class MCPSettings(BaseModel):
    config_path: str = str(_REPO_ROOT / "mcp" / "servers.yaml")


class UISettings(BaseModel):
    static_dir: str = str(_REPO_ROOT / "web" / "dist")


class AppSettings(BaseModel):
    port: int = 4000
    log_level: str = "info"
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    ui: UISettings = Field(default_factory=UISettings)


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply the handful of env vars Docker sets. Mutates and returns ``raw``."""
    if v := os.environ.get("JARVIS_PORT"):
        raw["port"] = int(v)
    if v := os.environ.get("TEMPORAL_HOST"):
        raw.setdefault("temporal", {})["host"] = v
    if v := os.environ.get("POSTGRES_DSN"):
        raw.setdefault("postgres", {})["dsn"] = v
    if v := os.environ.get("JARVIS_DEFAULT_MODEL"):
        raw.setdefault("llm", {})["default_model"] = v
    if v := os.environ.get("JARVIS_INTERACTIVE_MODEL"):
        raw.setdefault("llm", {})["interactive_model"] = v
    if v := os.environ.get("JARVIS_MODEL_OVERRIDE"):
        raw.setdefault("llm", {})["model_override"] = v
    if v := os.environ.get("JARVIS_MCP_CONFIG"):
        raw.setdefault("mcp", {})["config_path"] = v
    if v := os.environ.get("JARVIS_UI_STATIC_DIR"):
        raw.setdefault("ui", {})["static_dir"] = v
    if v := os.environ.get("JARVIS_SCHEDULE_CRON"):
        raw.setdefault("schedule", {})["cron"] = v
    if v := os.environ.get("JARVIS_SCHEDULE_TIMEZONE"):
        raw.setdefault("schedule", {})["timezone"] = v
    if v := os.environ.get("JARVIS_SCHEDULE_ENABLED"):
        raw.setdefault("schedule", {})["enabled"] = v.lower() in ("1", "true", "yes")
    if v := os.environ.get("OLLAMA_BASE_URL"):
        pass  # consumed directly in model_factory.py
    if v := os.environ.get("AWS_REGION"):
        pass  # consumed directly in model_factory.py
    return raw


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    """Load YAML config + env overrides into a validated ``AppSettings``."""
    path = Path(config_path) if config_path else _DEFAULT_CONFIG
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open() as f:
            loaded = yaml.safe_load(f) or {}
        # default.yaml nests app-level keys under "app"; flatten those up.
        app_section = loaded.pop("app", {}) or {}
        raw = {**loaded, **app_section}
    raw = _apply_env_overrides(raw)
    return AppSettings.model_validate(raw)
