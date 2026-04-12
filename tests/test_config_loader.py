"""Unit tests for src/config_loader.py"""
import os
import textwrap
import pytest
import yaml

from src.config_loader import (
    load_global_config,
    load_environments_config,
    load_agents_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_yaml(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content))
    return str(p)


# ---------------------------------------------------------------------------
# load_global_config
# ---------------------------------------------------------------------------

class TestLoadGlobalConfig:
    def test_valid_config(self, tmp_path):
        path = write_yaml(tmp_path, "global.yaml", """
            default_model: claude-test
            environments_config: config/environments.yaml
            agents_config: config/agents.yaml
        """)
        cfg = load_global_config(path)
        assert cfg.default_model == "claude-test"
        assert cfg.environments_config == "config/environments.yaml"
        assert cfg.agents_config == "config/agents.yaml"
        assert cfg.api_key == ""  # not present → defaults to ""

    def test_api_key_loaded_when_present(self, tmp_path):
        path = write_yaml(tmp_path, "global.yaml", """
            anthropic_api_key: sk-test-123
            default_model: claude-test
            environments_config: e.yaml
            agents_config: a.yaml
        """)
        cfg = load_global_config(path)
        assert cfg.api_key == "sk-test-123"

    def test_missing_default_model_raises(self, tmp_path):
        path = write_yaml(tmp_path, "global.yaml", """
            environments_config: e.yaml
            agents_config: a.yaml
        """)
        with pytest.raises(ValueError, match="default_model"):
            load_global_config(path)

    def test_missing_environments_config_raises(self, tmp_path):
        path = write_yaml(tmp_path, "global.yaml", """
            default_model: claude-test
            agents_config: a.yaml
        """)
        with pytest.raises(ValueError, match="environments_config"):
            load_global_config(path)

    def test_missing_agents_config_raises(self, tmp_path):
        path = write_yaml(tmp_path, "global.yaml", """
            default_model: claude-test
            environments_config: e.yaml
        """)
        with pytest.raises(ValueError, match="agents_config"):
            load_global_config(path)

    def test_file_not_found_raises_with_path(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="nonexistent.yaml"):
            load_global_config(str(tmp_path / "nonexistent.yaml"))

    def test_invalid_yaml_raises_value_error(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text(": invalid: yaml: {{{")
        with pytest.raises((ValueError, Exception)):
            load_global_config(str(p))


# ---------------------------------------------------------------------------
# load_environments_config
# ---------------------------------------------------------------------------

class TestLoadEnvironmentsConfig:
    def test_valid_config(self, tmp_path):
        path = write_yaml(tmp_path, "environments.yaml", """
            environments:
              - name: test-env
                description: A test environment
                config:
                  networking:
                    type: unrestricted
        """)
        envs = load_environments_config(path)
        assert len(envs) == 1
        assert envs[0].name == "test-env"
        assert envs[0].description == "A test environment"
        assert envs[0].config["networking"]["type"] == "unrestricted"

    def test_empty_environments_list(self, tmp_path):
        path = write_yaml(tmp_path, "environments.yaml", "environments: []\n")
        assert load_environments_config(path) == []

    def test_entry_missing_name_raises(self, tmp_path):
        path = write_yaml(tmp_path, "environments.yaml", """
            environments:
              - description: no name here
        """)
        with pytest.raises(ValueError, match="environment entry 0 missing required field: name"):
            load_environments_config(path)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="missing.yaml"):
            load_environments_config(str(tmp_path / "missing.yaml"))


# ---------------------------------------------------------------------------
# load_agents_config
# ---------------------------------------------------------------------------

class TestLoadAgentsConfig:
    def test_valid_config(self, tmp_path):
        path = write_yaml(tmp_path, "agents.yaml", """
            agents:
              - name: test-agent
                system: You are a helper.
                model: claude-test
                description: A test agent
        """)
        agents = load_agents_config(path)
        assert len(agents) == 1
        assert agents[0].name == "test-agent"
        assert agents[0].system == "You are a helper."
        assert agents[0].model == "claude-test"

    def test_optional_fields_default(self, tmp_path):
        path = write_yaml(tmp_path, "agents.yaml", """
            agents:
              - name: minimal-agent
                system: Hello.
        """)
        agents = load_agents_config(path)
        a = agents[0]
        assert a.model is None
        assert a.tools == []
        assert a.mcp_servers == []
        assert a.skills == []

    def test_entry_missing_name_raises(self, tmp_path):
        path = write_yaml(tmp_path, "agents.yaml", """
            agents:
              - system: no name
        """)
        with pytest.raises(ValueError, match="agent entry 0 missing required field: name"):
            load_agents_config(path)

    def test_entry_missing_system_raises(self, tmp_path):
        path = write_yaml(tmp_path, "agents.yaml", """
            agents:
              - name: my-agent
        """)
        with pytest.raises(ValueError, match="system"):
            load_agents_config(path)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="nope.yaml"):
            load_agents_config(str(tmp_path / "nope.yaml"))
