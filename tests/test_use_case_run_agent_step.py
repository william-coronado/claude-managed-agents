"""Tests for run_agent_step in the use-case pipeline runners."""
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_agent(id_="agent-id"):
    a = MagicMock()
    a.id = id_
    return a


def _make_mock_env(id_="env-id"):
    e = MagicMock()
    e.id = id_
    return e


def _make_mock_session(id_="sess-id"):
    s = MagicMock()
    s.id = id_
    return s


# ---------------------------------------------------------------------------
# software_engineering use case
# ---------------------------------------------------------------------------

class TestSERunAgentStep:
    def _import(self):
        from use_cases.software_engineering.run import run_agent_step
        return run_agent_step

    def test_happy_path_returns_stream_output(self):
        run_agent_step = self._import()
        client = MagicMock()
        agents = {"se-planner": _make_mock_agent("a1")}
        envs = {"se-env": _make_mock_env("e1")}
        mock_session = _make_mock_session("sess-1")

        with patch("src.pipeline.create_session", return_value=mock_session) as mock_cs, \
             patch("src.pipeline.stream_message", return_value="step output") as mock_sm:
            result = run_agent_step(client, agents, envs, "se-planner", "se-env", "do the thing")

        assert result == "step output"
        mock_cs.assert_called_once_with(client, "a1", "e1", title="do the thing")
        mock_sm.assert_called_once_with(client, "sess-1", "do the thing")

    def test_unknown_agent_raises_key_error(self):
        run_agent_step = self._import()
        client = MagicMock()
        agents = {}
        envs = {"se-env": _make_mock_env()}

        with pytest.raises(KeyError, match="unknown-agent"):
            run_agent_step(client, agents, envs, "unknown-agent", "se-env", "prompt")

    def test_unknown_env_raises_key_error(self):
        run_agent_step = self._import()
        client = MagicMock()
        agents = {"se-planner": _make_mock_agent()}
        envs = {}

        with pytest.raises(KeyError, match="unknown-env"):
            run_agent_step(client, agents, envs, "se-planner", "unknown-env", "prompt")


# ---------------------------------------------------------------------------
# content_creator use case
# ---------------------------------------------------------------------------

class TestCCRunAgentStep:
    def _import(self):
        from use_cases.content_creator.run import run_agent_step
        return run_agent_step

    def test_happy_path_returns_stream_output(self):
        run_agent_step = self._import()
        client = MagicMock()
        agents = {"cc-researcher": _make_mock_agent("a2")}
        envs = {"cc-env": _make_mock_env("e2")}
        mock_session = _make_mock_session("sess-2")

        with patch("src.pipeline.create_session", return_value=mock_session) as mock_cs, \
             patch("src.pipeline.stream_message", return_value="research output") as mock_sm:
            result = run_agent_step(client, agents, envs, "cc-researcher", "cc-env", "research AI")

        assert result == "research output"
        mock_cs.assert_called_once_with(client, "a2", "e2", title="research AI")
        mock_sm.assert_called_once_with(client, "sess-2", "research AI")

    def test_unknown_agent_raises_key_error(self):
        run_agent_step = self._import()
        client = MagicMock()
        agents = {}
        envs = {"cc-env": _make_mock_env()}

        with pytest.raises(KeyError, match="unknown-agent"):
            run_agent_step(client, agents, envs, "unknown-agent", "cc-env", "prompt")

    def test_unknown_env_raises_key_error(self):
        run_agent_step = self._import()
        client = MagicMock()
        agents = {"cc-researcher": _make_mock_agent()}
        envs = {}

        with pytest.raises(KeyError, match="unknown-env"):
            run_agent_step(client, agents, envs, "cc-researcher", "unknown-env", "prompt")
