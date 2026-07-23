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
# content_creator use case (the SE pipeline now uses a coordinator, not run_agent_step)
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
             patch("src.pipeline.stream_message", return_value="research output") as mock_sm, \
             patch("src.pipeline.list_session_output_files", return_value=[]):
            result = run_agent_step(client, agents, envs, "cc-researcher", "cc-env", "research AI")

        assert result.text == "research output"
        assert result.resources == []
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
# run_agent_step output capture
# ---------------------------------------------------------------------------

class TestRunAgentStepOutputCapture:
    def _import(self):
        from src.pipeline import run_agent_step
        return run_agent_step

    def _setup(self):
        agents = {"my-agent": _make_mock_agent("agent-id")}
        envs = {"my-env": _make_mock_env("env-id")}
        return MagicMock(), agents, envs

    def test_downloads_outputs_to_agent_subdir(self, tmp_path):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-dl")

        with patch("src.pipeline.create_session", return_value=session), \
             patch("src.pipeline.stream_message", return_value="out") as mock_sm, \
             patch("src.pipeline.download_session_outputs") as mock_dl, \
             patch("src.pipeline.list_session_output_files", return_value=[]):
            result = run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt", tmp_path)

        assert result.text == "out"
        mock_sm.assert_called_once_with(client, "sess-dl", "prompt")
        mock_dl.assert_called_once_with(client, "sess-dl", tmp_path / "my-agent")

    def test_no_download_when_output_dir_not_set(self):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-nodl")

        with patch("src.pipeline.create_session", return_value=session), \
             patch("src.pipeline.stream_message", return_value="out") as mock_sm, \
             patch("src.pipeline.download_session_outputs") as mock_dl, \
             patch("src.pipeline.list_session_output_files", return_value=[]):
            result = run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt")

        assert result.text == "out"
        mock_sm.assert_called_once_with(client, "sess-nodl", "prompt")
        mock_dl.assert_not_called()


# ---------------------------------------------------------------------------
# Carrying a step's output files forward as the next step's session resources
# ---------------------------------------------------------------------------

class TestRunAgentStepResourceHandoff:
    def _import(self):
        from src.pipeline import run_agent_step
        return run_agent_step

    def _setup(self):
        agents = {"my-agent": _make_mock_agent("agent-id")}
        envs = {"my-env": _make_mock_env("env-id")}
        return MagicMock(), agents, envs

    def test_returns_output_files_as_mountable_resources(self):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-out")

        with patch("src.pipeline.create_session", return_value=session), \
             patch("src.pipeline.stream_message", return_value="draft text"), \
             patch("src.pipeline.list_session_output_files", return_value=[("file_abc", "draft.md")]):
            result = run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt")

        assert result.text == "draft text"
        assert result.resources == [
            {"type": "file", "file_id": "file_abc", "mount_path": "/draft.md"}
        ]

    def test_incoming_resources_forwarded_to_create_session(self):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-in")
        incoming = [{"type": "file", "file_id": "file_abc", "mount_path": "/mnt/session/uploads/draft.md"}]

        with patch("src.pipeline.create_session", return_value=session) as mock_cs, \
             patch("src.pipeline.stream_message", return_value="edited"), \
             patch("src.pipeline.list_session_output_files", return_value=[]):
            run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt", resources=incoming)

        mock_cs.assert_called_once_with(
            client, "agent-id", "env-id", title="prompt", resources=incoming,
        )

    def test_no_resources_kwarg_when_none_incoming(self):
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-none")

        with patch("src.pipeline.create_session", return_value=session) as mock_cs, \
             patch("src.pipeline.stream_message", return_value="edited"), \
             patch("src.pipeline.list_session_output_files", return_value=[]):
            run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt")

        mock_cs.assert_called_once_with(client, "agent-id", "env-id", title="prompt")

    def test_explicit_empty_resources_list_still_forwarded(self):
        # An explicit [] is distinct from "not specified" (None) — a caller
        # that deliberately passes an empty list should have that reflected
        # in the create_session call, not silently dropped via truthiness.
        run_agent_step = self._import()
        client, agents, envs = self._setup()
        session = _make_mock_session("sess-empty")

        with patch("src.pipeline.create_session", return_value=session) as mock_cs, \
             patch("src.pipeline.stream_message", return_value="edited"), \
             patch("src.pipeline.list_session_output_files", return_value=[]):
            run_agent_step(client, agents, envs, "my-agent", "my-env", "prompt", resources=[])

        mock_cs.assert_called_once_with(client, "agent-id", "env-id", title="prompt", resources=[])
