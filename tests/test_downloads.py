"""Unit tests for src/downloads.py and download_outputs.py CLI."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_client():
    return MagicMock()


def _make_write_event(file_path: str, content: str):
    ev = MagicMock()
    ev.type = "agent.tool_use"
    ev.name = "write"
    ev.input = {"file_path": file_path, "content": content}
    return ev


def _make_other_event(type_: str = "agent.message"):
    ev = MagicMock()
    ev.type = type_
    ev.name = None
    return ev


def _make_bash_event(command: str):
    ev = MagicMock()
    ev.type = "agent.tool_use"
    ev.name = "bash"
    ev.input = {"command": command}
    return ev


class TestDownloadSessionOutputs:
    def _call(self, client, session_id, output_dir, remote_dir=None):
        from src.downloads import download_session_outputs
        if remote_dir is not None:
            return download_session_outputs(client, session_id, output_dir, remote_dir)
        return download_session_outputs(client, session_id, output_dir)

    def test_downloads_all_output_files(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/result.py", "print('ok')"),
            _make_write_event("/mnt/session/outputs/report.md", "# Report"),
        ]

        count = self._call(client, "sess-1", tmp_path)

        assert count == 2
        client.beta.sessions.events.list.assert_called_once_with("sess-1")
        assert (tmp_path / "result.py").read_text() == "print('ok')"
        assert (tmp_path / "report.md").read_text() == "# Report"

    def test_skips_non_write_tool_events(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_other_event("agent.message"),
            _make_bash_event("ls /mnt/session/outputs/"),
            _make_write_event("/mnt/session/outputs/result.py", "data"),
        ]

        count = self._call(client, "sess-2", tmp_path)

        assert count == 1
        assert (tmp_path / "result.py").read_text() == "data"

    def test_skips_files_outside_remote_dir(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/uploads/input.py", "upload"),
            _make_write_event("/mnt/session/outputs/out.py", "output"),
        ]

        count = self._call(client, "sess-3", tmp_path)

        assert count == 1
        assert (tmp_path / "out.py").read_text() == "output"
        assert not (tmp_path / "input.py").exists()

    def test_returns_zero_when_no_write_events(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_other_event("session.status_idle"),
        ]

        count = self._call(client, "sess-4", tmp_path)

        assert count == 0

    def test_creates_output_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "output"
        client = _make_client()
        client.beta.sessions.events.list.return_value = []

        self._call(client, "sess-5", new_dir)

        assert new_dir.is_dir()

    def test_preserves_subdirectory_structure(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/todo/main.py", "# main"),
            _make_write_event("/mnt/session/outputs/todo/utils/helpers.py", "# helpers"),
        ]

        self._call(client, "sess-6", tmp_path)

        assert (tmp_path / "todo" / "main.py").read_text() == "# main"
        assert (tmp_path / "todo" / "utils" / "helpers.py").read_text() == "# helpers"

    def test_custom_remote_dir_filters_and_strips_prefix(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/todo/main.py", "# main"),
            _make_write_event("/mnt/session/outputs/notes/readme.md", "# notes"),
        ]

        from src.downloads import download_session_outputs
        count = download_session_outputs(client, "sess-7", tmp_path, "/mnt/session/outputs/todo")

        assert count == 1
        assert (tmp_path / "main.py").read_text() == "# main"
        assert not (tmp_path / "readme.md").exists()

    def test_remote_dir_without_trailing_slash_is_normalised(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/result.py", "data"),
        ]

        from src.downloads import download_session_outputs
        count = download_session_outputs(client, "sess-8", tmp_path, "/mnt/session/outputs")

        assert count == 1
        assert (tmp_path / "result.py").read_text() == "data"


# ---------------------------------------------------------------------------
# download_outputs.py CLI
# ---------------------------------------------------------------------------

class TestDownloadOutputsCLI:
    def test_main_calls_download_with_parsed_args(self, tmp_path):
        import download_outputs

        mock_client = MagicMock()
        mock_cfg = MagicMock(api_key=None)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("download_outputs.load_global_config", return_value=mock_cfg), \
             patch("download_outputs.Anthropic", return_value=mock_client), \
             patch("download_outputs.download_session_outputs") as mock_dl, \
             patch("sys.argv", ["download_outputs.py", "--session-id", "sess-99",
                                "--output-dir", str(tmp_path)]):
            download_outputs.main()

        mock_dl.assert_called_once_with(mock_client, "sess-99", Path(str(tmp_path)), "/mnt/session/outputs/")

    def test_main_passes_custom_remote_dir(self, tmp_path):
        import download_outputs

        mock_client = MagicMock()
        mock_cfg = MagicMock(api_key=None)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("download_outputs.load_global_config", return_value=mock_cfg), \
             patch("download_outputs.Anthropic", return_value=mock_client), \
             patch("download_outputs.download_session_outputs") as mock_dl, \
             patch("sys.argv", ["download_outputs.py", "--session-id", "sess-99",
                                "--output-dir", str(tmp_path),
                                "--remote-dir", "/mnt/session/outputs/todo/"]):
            download_outputs.main()

        mock_dl.assert_called_once_with(mock_client, "sess-99", Path(str(tmp_path)), "/mnt/session/outputs/todo/")
