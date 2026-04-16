"""Unit tests for src/loader.py"""
import pytest
from unittest.mock import MagicMock, patch

from src.loader import load_resources
from src.exceptions import ResourceNotFoundError
from src.config_loader import EnvironmentConfig, AgentConfig


def _env_config(name):
    return EnvironmentConfig(name=name, description="", config={})


def _agent_config(name):
    return AgentConfig(name=name, system="Be helpful.")


def _make_env(name):
    m = MagicMock()
    m.name = name
    return m


def _make_agent(name):
    m = MagicMock()
    m.name = name
    return m


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

class TestLoadResourcesSuccess:
    def test_returns_dicts_keyed_by_name(self):
        client = MagicMock()
        env_cfg = [_env_config("env-a")]
        agent_cfg = [_agent_config("agent-a"), _agent_config("agent-b")]

        with (
            patch("src.loader.load_environments_config", return_value=env_cfg),
            patch("src.loader.load_agents_config", return_value=agent_cfg),
            patch("src.loader.create_environment", side_effect=lambda c, cfg, **kw: _make_env(cfg.name)) as mock_env,
            patch("src.loader.create_agent", side_effect=lambda c, cfg, dm, **kw: _make_agent(cfg.name)) as mock_agent,
        ):
            envs, agents = load_resources(client, "default-model", "envs.yaml", "agents.yaml")

        assert set(envs.keys()) == {"env-a"}
        assert set(agents.keys()) == {"agent-a", "agent-b"}
        assert envs["env-a"].name == "env-a"
        assert agents["agent-a"].name == "agent-a"

    def test_passes_default_model_to_create_agent(self):
        client = MagicMock()
        captured = {}

        def fake_create_agent(c, cfg, default_model, **kw):
            captured["model"] = default_model
            return _make_agent(cfg.name)

        with (
            patch("src.loader.load_environments_config", return_value=[]),
            patch("src.loader.load_agents_config", return_value=[_agent_config("a")]),
            patch("src.loader.create_agent", side_effect=fake_create_agent),
        ):
            load_resources(client, "my-model", "envs.yaml", "agents.yaml")

        assert captured["model"] == "my-model"

    def test_passes_existing_flag_through(self):
        client = MagicMock()
        captured = {}

        def fake_create_env(c, cfg, existing=False):
            captured["existing"] = existing
            return _make_env(cfg.name)

        with (
            patch("src.loader.load_environments_config", return_value=[_env_config("e")]),
            patch("src.loader.load_agents_config", return_value=[]),
            patch("src.loader.create_environment", side_effect=fake_create_env),
        ):
            load_resources(client, "model", "envs.yaml", "agents.yaml", existing=True)

        assert captured["existing"] is True


# ---------------------------------------------------------------------------
# Error path — single missing resource
# ---------------------------------------------------------------------------

class TestLoadResourcesSingleMissing:
    def test_exits_when_environment_not_found(self):
        client = MagicMock()

        with (
            patch("src.loader.load_environments_config", return_value=[_env_config("missing-env")]),
            patch("src.loader.load_agents_config", return_value=[]),
            patch("src.loader.create_environment", side_effect=ResourceNotFoundError("Existing environment 'missing-env' not found")),
        ):
            with pytest.raises(SystemExit) as exc_info:
                load_resources(client, "model", "envs.yaml", "agents.yaml", existing=True)

        assert "missing-env" in str(exc_info.value)

    def test_exits_when_agent_not_found(self):
        client = MagicMock()

        with (
            patch("src.loader.load_environments_config", return_value=[]),
            patch("src.loader.load_agents_config", return_value=[_agent_config("missing-agent")]),
            patch("src.loader.create_agent", side_effect=ResourceNotFoundError("Existing agent 'missing-agent' not found")),
        ):
            with pytest.raises(SystemExit) as exc_info:
                load_resources(client, "model", "envs.yaml", "agents.yaml", existing=True)

        assert "missing-agent" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Error path — multiple missing resources collected in one shot
# ---------------------------------------------------------------------------

class TestLoadResourcesMultipleMissing:
    def test_reports_all_missing_resources_before_exiting(self):
        client = MagicMock()
        env_cfgs = [_env_config("env-x"), _env_config("env-y")]
        agent_cfgs = [_agent_config("agent-z")]

        def missing_env(c, cfg, **kw):
            raise ResourceNotFoundError(f"Existing environment '{cfg.name}' not found")

        def missing_agent(c, cfg, dm, **kw):
            raise ResourceNotFoundError(f"Existing agent '{cfg.name}' not found")

        with (
            patch("src.loader.load_environments_config", return_value=env_cfgs),
            patch("src.loader.load_agents_config", return_value=agent_cfgs),
            patch("src.loader.create_environment", side_effect=missing_env),
            patch("src.loader.create_agent", side_effect=missing_agent),
        ):
            with pytest.raises(SystemExit) as exc_info:
                load_resources(client, "model", "envs.yaml", "agents.yaml", existing=True)

        error_text = str(exc_info.value)
        assert "env-x" in error_text
        assert "env-y" in error_text
        assert "agent-z" in error_text

    def test_continues_after_first_missing_resource(self):
        """load_resources must not short-circuit on the first error."""
        client = MagicMock()
        env_cfgs = [_env_config("env-1"), _env_config("env-2")]
        call_count = {"n": 0}

        def missing_env(c, cfg, **kw):
            call_count["n"] += 1
            raise ResourceNotFoundError(f"Existing environment '{cfg.name}' not found")

        with (
            patch("src.loader.load_environments_config", return_value=env_cfgs),
            patch("src.loader.load_agents_config", return_value=[]),
            patch("src.loader.create_environment", side_effect=missing_env),
        ):
            with pytest.raises(SystemExit):
                load_resources(client, "model", "envs.yaml", "agents.yaml", existing=True)

        assert call_count["n"] == 2
