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


def _make_file(file_id: str, filename: str, size_bytes: int):
    f = MagicMock()
    f.id = file_id
    f.filename = filename
    f.size_bytes = size_bytes
    return f


def _wire_files_api(client, files, contents_by_id=None):
    """Configure client.beta.files.list()/download() to serve the given files.

    files: list of File mocks (from _make_file). contents_by_id: optional {id: bytes/str}
    to write when download(id) is called; defaults to a marker string per id.
    """
    client.beta.files.list.return_value = files
    contents_by_id = contents_by_id or {}

    def _download(file_id):
        response = MagicMock()
        data = contents_by_id.get(file_id, f"<content of {file_id}>")

        def _write(dest, _data=data):
            Path(dest).write_text(_data, encoding="utf-8")

        response.write_to_file.side_effect = _write
        return response

    client.beta.files.download.side_effect = _download


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
        _wire_files_api(client, [
            _make_file("file_1", "result.py", len(b"print('ok')")),
            _make_file("file_2", "report.md", len(b"# Report")),
        ], contents_by_id={"file_1": "print('ok')", "file_2": "# Report"})

        count = self._call(client, "sess-1", tmp_path)

        assert count == 2
        client.beta.sessions.events.list.assert_called_once_with("sess-1")
        client.beta.files.list.assert_called_once_with(
            scope_id="sess-1", betas=["managed-agents-2026-04-01"]
        )
        assert (tmp_path / "result.py").read_text() == "print('ok')"
        assert (tmp_path / "report.md").read_text() == "# Report"

    def test_skips_non_write_tool_events(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_other_event("agent.message"),
            _make_bash_event("ls /mnt/session/outputs/"),
            _make_write_event("/mnt/session/outputs/result.py", "data"),
        ]
        _wire_files_api(client, [_make_file("file_1", "result.py", len(b"data"))],
                         contents_by_id={"file_1": "data"})

        count = self._call(client, "sess-2", tmp_path)

        assert count == 1
        assert (tmp_path / "result.py").read_text() == "data"

    def test_skips_files_outside_remote_dir(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/uploads/input.py", "upload"),
            _make_write_event("/mnt/session/outputs/out.py", "output"),
        ]
        _wire_files_api(client, [_make_file("file_1", "out.py", len(b"output"))],
                         contents_by_id={"file_1": "output"})

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
        client.beta.files.list.assert_not_called()

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
        _wire_files_api(client, [
            _make_file("file_1", "main.py", len(b"# main")),
            _make_file("file_2", "helpers.py", len(b"# helpers")),
        ], contents_by_id={"file_1": "# main", "file_2": "# helpers"})

        self._call(client, "sess-6", tmp_path)

        assert (tmp_path / "todo" / "main.py").read_text() == "# main"
        assert (tmp_path / "todo" / "utils" / "helpers.py").read_text() == "# helpers"

    def test_custom_remote_dir_filters_and_strips_prefix(self, tmp_path):
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/todo/main.py", "# main"),
            _make_write_event("/mnt/session/outputs/notes/readme.md", "# notes"),
        ]
        _wire_files_api(client, [_make_file("file_1", "main.py", len(b"# main"))],
                         contents_by_id={"file_1": "# main"})

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
        _wire_files_api(client, [_make_file("file_1", "result.py", len(b"data"))],
                         contents_by_id={"file_1": "data"})

        from src.downloads import download_session_outputs
        count = download_session_outputs(client, "sess-8", tmp_path, "/mnt/session/outputs")

        assert count == 1
        assert (tmp_path / "result.py").read_text() == "data"

    def test_disambiguates_duplicate_basenames_by_size(self, tmp_path):
        """The Files API only reports a basename - two files named 'main.py' in different
        subdirectories are indistinguishable except by size. This confirms the (basename,
        size) match routes each one to the right destination."""
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/todo/main.py", "print(1)"),
            _make_write_event("/mnt/session/outputs/utils/main.py", "print(22)"),
        ]
        _wire_files_api(client, [
            _make_file("file_1", "main.py", len(b"print(1)")),
            _make_file("file_2", "main.py", len(b"print(22)")),
        ], contents_by_id={"file_1": "print(1)", "file_2": "print(22)"})

        count = self._call(client, "sess-9", tmp_path)

        assert count == 2
        assert (tmp_path / "todo" / "main.py").read_text() == "print(1)"
        assert (tmp_path / "utils" / "main.py").read_text() == "print(22)"

    def test_falls_back_to_logged_content_when_no_files_api_match(self, tmp_path):
        """If the Files API never reports a matching file (e.g. an indexing failure),
        the event's own logged content is written so the file isn't silently dropped."""
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/result.py", "print('ok')"),
        ]
        _wire_files_api(client, [])  # Files API never sees the file

        with patch("src.downloads.time.sleep"):
            count = self._call(client, "sess-10", tmp_path)

        assert count == 1
        assert (tmp_path / "result.py").read_text() == "print('ok')"
        client.beta.files.download.assert_not_called()

    def test_retries_files_list_on_indexing_lag(self, tmp_path):
        """files.list can lag briefly behind session idle; an empty/incomplete first
        response should be retried before falling back."""
        client = _make_client()
        client.beta.sessions.events.list.return_value = [
            _make_write_event("/mnt/session/outputs/result.py", "print('ok')"),
        ]
        empty_then_full = [[], [_make_file("file_1", "result.py", len(b"print('ok')"))]]
        client.beta.files.list.side_effect = empty_then_full

        def _download(file_id):
            response = MagicMock()
            response.write_to_file.side_effect = (
                lambda dest: Path(dest).write_text("print('ok')", encoding="utf-8")
            )
            return response

        client.beta.files.download.side_effect = _download

        with patch("src.downloads.time.sleep") as mock_sleep:
            count = self._call(client, "sess-11", tmp_path)

        assert count == 1
        assert client.beta.files.list.call_count == 2
        mock_sleep.assert_called_once()
        assert (tmp_path / "result.py").read_text() == "print('ok')"


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
