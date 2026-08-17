"""Configuration loading for Jarvis.

Config is a small, human-edited YAML file. We parse it into plain
dataclasses rather than pulling in a validation library like pydantic —
the shape is small enough that explicit code is easier to read than a
schema description, and it keeps this module's only dependency PyYAML
(already required for the memory store's frontmatter).

This file is fully implemented as a worked example of the patterns used
elsewhere in the app: dataclasses for config shape, a small custom
exception for user-facing errors, and explicit (not magic) parsing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when the config file is missing, malformed, or incomplete."""


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key_env: str
    max_tokens: int = 4096
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def api_key(self) -> str:
        """Read the API key from the environment lazily.

        Lazy on purpose: loading/parsing config should never fail just
        because a key isn't set yet (e.g. during tests, or before the
        user has exported it) — only actually calling the LLM should.
        """
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ConfigError(
                f"Environment variable {self.api_key_env!r} is not set "
                f"(required by llm.api_key_env in your config)"
            )
        return key


@dataclass
class MemoryConfig:
    root_dir: Path
    user_id: str = "default"


@dataclass
class AgentConfig:
    system_prompt_file: Path | None = None


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class MCPServerConfig:
    """How to launch one MCP server as a subprocess (stdio transport).

    `command` must point at a Python interpreter that has the server's own
    dependencies installed (its venv), not just any Python on PATH — e.g.
    ["/path/to/weather-mcp/.venv/bin/python", "/path/to/weather-mcp/weather.py"].
    The server's code has to be physically present on this machine; see
    docs/PLAN.md's "MCP integrations" section for the network-transport
    alternative if that stops being true.
    """

    command: list[str]


@dataclass
class JarvisConfig:
    llm: LLMConfig
    memory: MemoryConfig
    agent: AgentConfig
    logging: LoggingConfig
    mcp_servers: dict[str, MCPServerConfig] = field(default_factory=dict)


def _require(data: dict[str, Any], section: str) -> dict[str, Any]:
    if section not in data:
        raise ConfigError(f"Missing required section {section!r} in config")
    return data[section]


def _parse_llm(data: dict[str, Any]) -> LLMConfig:
    try:
        return LLMConfig(
            provider=data["provider"],
            model=data["model"],
            api_key_env=data["api_key_env"],
            max_tokens=data.get("max_tokens", 4096),
            options=data.get("options", {}),
        )
    except KeyError as e:
        raise ConfigError(f"Missing required llm field: {e}") from e


def _parse_memory(data: dict[str, Any]) -> MemoryConfig:
    try:
        return MemoryConfig(
            root_dir=Path(data["root_dir"]).expanduser(),
            user_id=data.get("user_id", "default"),
        )
    except KeyError as e:
        raise ConfigError(f"Missing required memory field: {e}") from e


def _parse_agent(data: dict[str, Any]) -> AgentConfig:
    prompt_file = data.get("system_prompt_file")
    return AgentConfig(
        system_prompt_file=Path(prompt_file).expanduser() if prompt_file else None,
    )


def _parse_logging(data: dict[str, Any]) -> LoggingConfig:
    return LoggingConfig(level=data.get("level", "INFO"))


def _parse_mcp_servers(data: dict[str, Any]) -> dict[str, MCPServerConfig]:
    servers = {}
    for name, server_data in data.items():
        try:
            servers[name] = MCPServerConfig(command=server_data["command"])
        except KeyError as e:
            raise ConfigError(f"Missing required mcp_servers.{name} field: {e}") from e
    return servers


def _candidate_paths(explicit: str | Path | None) -> list[Path]:
    """Resolution order: explicit path > $JARVIS_CONFIG > ./config.yaml > ~/.jarvis/config.yaml."""
    if explicit is not None:
        return [Path(explicit).expanduser()]

    candidates: list[Path] = []
    env_path = os.environ.get("JARVIS_CONFIG")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.append(Path("config.yaml"))
    candidates.append(Path("~/.jarvis/config.yaml").expanduser())
    return candidates


def load_config(path: str | Path | None = None) -> JarvisConfig:
    """Load and parse the Jarvis config file.

    Resolution order when `path` is not given:
    1. $JARVIS_CONFIG environment variable
    2. ./config.yaml (current working directory)
    3. ~/.jarvis/config.yaml

    Raises ConfigError if no candidate path exists, or if the file is
    malformed / missing required fields.
    """
    candidates = _candidate_paths(path)
    resolved = next((c for c in candidates if c.is_file()), None)

    if resolved is None:
        if path is not None:
            raise ConfigError(f"Config file not found: {path}")
        searched = ", ".join(str(c) for c in candidates)
        raise ConfigError(f"No config file found. Searched: {searched}")

    try:
        raw = yaml.safe_load(resolved.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse {resolved}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"{resolved} must contain a YAML mapping at the top level")

    return JarvisConfig(
        llm=_parse_llm(_require(raw, "llm")),
        memory=_parse_memory(_require(raw, "memory")),
        agent=_parse_agent(raw.get("agent", {})),
        logging=_parse_logging(raw.get("logging", {})),
        mcp_servers=_parse_mcp_servers(raw.get("mcp_servers", {})),
    )
