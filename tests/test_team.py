"""Unit tests for src/team.py (coordinator + outcome session)."""
from unittest.mock import MagicMock, patch

from src.team import create_coordinator, run_outcome_session


def _member(id_):
    m = MagicMock()
    m.id = id_
    return m


class TestCreateCoordinator:
    def test_builds_roster_from_member_ids(self):
        client = MagicMock()
        created = MagicMock()
        created.id = "coord-id"
        client.beta.agents.create.return_value = created

        members = [_member("agent-a"), _member("agent-b")]
        coord = create_coordinator(
            client, name="lead", system="coordinate", members=members,
            default_model="claude-sonnet-5", model="claude-opus-4-8",
        )

        assert coord.id == "coord-id"
        kwargs = client.beta.agents.create.call_args.kwargs
        assert kwargs["name"] == "lead"
        assert kwargs["model"] == "claude-opus-4-8"
        assert kwargs["multiagent"] == {"type": "coordinator", "agents": ["agent-a", "agent-b"]}

    def test_existing_mode_looks_up_by_name(self):
        # In existing mode create_agent paginates; build a client that yields the coordinator.
        client = MagicMock()
        found = MagicMock()
        found.name = "lead"
        found.id = "coord-existing"
        found.version = 3
        page = MagicMock()
        page.data = [found]
        list_result = MagicMock()
        list_result.iter_pages.return_value = iter([page])
        client.beta.agents.list.return_value = list_result

        coord = create_coordinator(
            client, name="lead", system="s", members=[_member("a")],
            default_model="m", existing=True,
        )

        assert coord.id == "coord-existing"
        client.beta.agents.create.assert_not_called()


class TestRunOutcomeSession:
    def test_creates_session_defines_outcome_and_downloads(self, tmp_path):
        client = MagicMock()
        coordinator = _member("coord-id")
        env = _member("env-id")

        session = MagicMock()
        session.id = "sess-x"

        with patch("src.team.create_session", return_value=session) as mock_cs, \
             patch("src.team.define_outcome") as mock_define, \
             patch("src.team.stream_session") as mock_stream, \
             patch("src.team.download_session_outputs") as mock_dl:
            tracker = run_outcome_session(
                client, coordinator, env, "Build X", "- criterion",
                output_dir=tmp_path, max_iterations=4,
            )

        # session created against the coordinator + env
        assert mock_cs.call_args.args[1] == "coord-id"
        assert mock_cs.call_args.args[2] == "env-id"
        # streaming happened and outputs were downloaded
        mock_stream.assert_called_once()
        mock_dl.assert_called_once_with(client, "sess-x", tmp_path)
        assert tracker.last_result is None  # no grader events fed in this unit test

    def test_no_download_without_output_dir(self):
        client = MagicMock()
        session = MagicMock()
        session.id = "sess-y"

        with patch("src.team.create_session", return_value=session), \
             patch("src.team.define_outcome"), \
             patch("src.team.stream_session"), \
             patch("src.team.download_session_outputs") as mock_dl:
            run_outcome_session(client, _member("c"), _member("e"), "Build X", "- crit")

        mock_dl.assert_not_called()

    def test_resources_and_vaults_forwarded_to_create_session(self):
        client = MagicMock()
        session = MagicMock()
        session.id = "sess-r"
        resources = [{"type": "github_repository", "url": "https://github.com/a/b"}]
        vaults = ["vlt_1", "vlt_2"]

        with patch("src.team.create_session", return_value=session) as mock_cs, \
             patch("src.team.define_outcome"), \
             patch("src.team.stream_session"), \
             patch("src.team.download_session_outputs"):
            run_outcome_session(
                client, _member("c"), _member("e"), "Build X", "- crit",
                resources=resources, vault_ids=vaults,
            )

        kwargs = mock_cs.call_args.kwargs
        assert kwargs["resources"] == resources
        assert kwargs["vault_ids"] == vaults

    def test_max_iterations_forwarded_to_define_outcome(self):
        client = MagicMock()
        session = MagicMock()
        session.id = "sess-m"

        # stream_session runs the caller-supplied kickoff (which sends the outcome).
        def _run_kickoff(client, session_id, kickoff=None, on_event=None):
            kickoff()
            return ""

        with patch("src.team.create_session", return_value=session), \
             patch("src.team.define_outcome") as mock_define, \
             patch("src.team.stream_session", side_effect=_run_kickoff), \
             patch("src.team.download_session_outputs"):
            run_outcome_session(
                client, _member("c"), _member("e"), "Build X", "- crit",
                max_iterations=9,
            )

        # define_outcome(client, session_id, description, rubric, max_iterations)
        mock_define.assert_called_once()
        assert mock_define.call_args.args[4] == 9
