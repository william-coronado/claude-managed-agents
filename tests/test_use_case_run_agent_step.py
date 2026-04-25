"""Tests for run_agent_step in the use-case pipeline runners."""
import pytest
from pathlib import Path
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


# ---------------------------------------------------------------------------
# run_agent_step download integration
# ---------------------------------------------------------------------------

class TestRunAgentStepOutputDownload:
    def _import(self):
        from src.pipeline import run_agent_step
        return run_agent_step

    def _setup(self):
        agents = {"my-agent": _make_mock_agent("agent-id")}
        envs = {"my-env": _make_mock_env("env-id")}
        return MagicMock(), agents, envs

    def test_calls_download_in_agent_subdirectory(self, tmp_path):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-dl")

        with patch("src.pipeline.create_session", return_value=session), \
             patch("src.pipeline.stream_message", return_value="out"), \
             patch("src.pipeline.download_session_outputs") as mock_dl:
            result = run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt", tmp_path)

        assert result == "out"
        mock_dl.assert_called_once_with(client, "sess-dl", tmp_path / "my-agent")

    def test_skips_download_when_output_dir_is_none(self):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-nodl")

        with patch("src.pipeline.create_session", return_value=session), \
             patch("src.pipeline.stream_message", return_value="out"), \
             patch("src.pipeline.download_session_outputs") as mock_dl:
            result = run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt")

        assert result == "out"
        mock_dl.assert_not_called()

    def test_downloads_even_when_stream_message_raises(self, tmp_path):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-err")

        with patch("src.pipeline.create_session", return_value=session), \
             patch("src.pipeline.stream_message", side_effect=RuntimeError("boom")), \
             patch("src.pipeline.download_session_outputs") as mock_dl:
            with pytest.raises(RuntimeError, match="boom"):
                run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt", tmp_path)

        mock_dl.assert_called_once_with(client, "sess-err", tmp_path / "my-agent")
