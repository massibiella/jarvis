from pathlib import Path

import pytest

from jarvis.config import ConfigError, load_config

VALID_YAML = """
llm:
  provider: anthropic
  model: claude-opus-5
  api_key_env: TEST_API_KEY
  max_tokens: 2048

memory:
  root_dir: ./data/memory
  user_id: default

logging:
  level: DEBUG
"""


def test_load_valid_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)

    config = load_config(config_file)

    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-opus-5"
    assert config.llm.max_tokens == 2048
    assert config.memory.user_id == "default"
    assert config.logging.level == "DEBUG"


def test_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(ConfigError, match="not found"):
        load_config(missing)


def test_missing_required_section_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("llm:\n  provider: anthropic\n  model: x\n  api_key_env: X\n")

    with pytest.raises(ConfigError, match="memory"):
        load_config(config_file)


def test_api_key_reads_env_lazily(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)
    config = load_config(config_file)

    monkeypatch.delenv("TEST_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="TEST_API_KEY"):
        _ = config.llm.api_key

    monkeypatch.setenv("TEST_API_KEY", "sk-fake")
    assert config.llm.api_key == "sk-fake"


def test_resolution_order_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "somewhere.yaml"
    config_file.write_text(VALID_YAML)
    monkeypatch.setenv("JARVIS_CONFIG", str(config_file))

    config = load_config()

    assert config.llm.provider == "anthropic"


def test_mcp_servers_default_empty(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_YAML)

    config = load_config(config_file)

    assert config.mcp_servers == {}


def test_mcp_servers_parsed(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_YAML
        + """
mcp_servers:
  weather:
    command: ["/path/to/.venv/bin/python", "/path/to/weather.py"]
"""
    )

    config = load_config(config_file)

    assert config.mcp_servers["weather"].command == [
        "/path/to/.venv/bin/python",
        "/path/to/weather.py",
    ]


def test_mcp_servers_missing_command_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_YAML
        + """
mcp_servers:
  weather:
    not_command: nope
"""
    )

    with pytest.raises(ConfigError, match="mcp_servers.weather"):
        load_config(config_file)
