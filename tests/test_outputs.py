"""Unit tests for src/outputs.py (session outputs via the Files API).

The Files API's `filename` is always a bare basename - confirmed against a
live session (see git history): writing /mnt/session/outputs/todo/main.py and
/mnt/session/outputs/utils/main.py in the same session and calling
files.list(scope_id=...) returns two entries both named "main.py", with no
other field to disambiguate them. `_file()` below reflects that: it never
takes a path, only a basename (and an optional size_bytes for collision
tests) - a test that wants subdirectory structure must supply it via
`write_events`, which src.outputs recovers by replaying the session's
'write' tool call events, not by inventing a path-shaped filename.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.constants import MANAGED_AGENTS_BETA
from src.outputs import download_session_outputs, list_session_output_files


def _file(id_, filename, size_bytes=None):
    return SimpleNamespace(id=id_, filename=filename, size_bytes=size_bytes)


def _make_download(content):
    """A fake Files download response exposing write_to_file()."""
    dl = MagicMock()

    def _write(path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")

    dl.write_to_file.side_effect = _write
    return dl


def _write_event(file_path: str, content: str):
    ev = MagicMock()
    ev.type = "agent.tool_use"
    ev.name = "write"
    ev.input = {"file_path": file_path, "content": content}
    return ev


def _client_with(files, contents, write_events=None):
    """files: list of file objects; contents: {file_id: content}.

    write_events: list of (file_path, content) tuples to replay as 'write'
    tool call events. Omitting it means none of the files are correlated to a
    write call, exercising the flat/basename-only fallback path (e.g. files
    produced by bash/code-exec) - the same behaviour this module had before
    event-replay was added.
    """
    client = MagicMock()
    client.beta.files.list.return_value = SimpleNamespace(data=files)
    client.beta.files.download.side_effect = lambda fid: _make_download(contents[fid])
    client.beta.sessions.events.list.return_value = [
        _write_event(path, content) for path, content in (write_events or [])
    ]
    return client


class TestDownloadSessionOutputs:
    def test_downloads_all_output_files(self, tmp_path):
        files = [_file("f1", "result.py"), _file("f2", "report.md")]
        client = _client_with(files, {"f1": "print('ok')", "f2": "# Report"})

        count = download_session_outputs(client, "sess-1", tmp_path)

        assert count == 2
        client.beta.files.list.assert_called_once_with(
            scope_id="sess-1", betas=[MANAGED_AGENTS_BETA]
        )
        assert (tmp_path / "result.py").read_text(encoding="utf-8") == "print('ok')"
        assert (tmp_path / "report.md").read_text(encoding="utf-8") == "# Report"

    def test_preserves_subdirectory_structure(self, tmp_path):
        # The Files API only ever reports basenames - the real path comes from
        # replaying the 'write' tool events, not from the listed filename.
        files = [_file("f1", "main.py"), _file("f2", "helpers.py")]
        client = _client_with(
            files,
            {"f1": "# main", "f2": "# helpers"},
            write_events=[
                ("/mnt/session/outputs/todo/main.py", "# main"),
                ("/mnt/session/outputs/todo/utils/helpers.py", "# helpers"),
            ],
        )

        download_session_outputs(client, "sess-2", tmp_path)

        assert (tmp_path / "todo" / "main.py").read_text(encoding="utf-8") == "# main"
        assert (tmp_path / "todo" / "utils" / "helpers.py").read_text(encoding="utf-8") == "# helpers"

    def test_disambiguates_duplicate_basenames_by_size(self, tmp_path):
        """Two files named 'main.py' in different subdirectories are
        indistinguishable in files.list() except by size - confirm the
        (basename, size) match routes each to the correct destination."""
        files = [
            _file("f1", "main.py", size_bytes=len(b"print(1)")),
            _file("f2", "main.py", size_bytes=len(b"print(22)")),
        ]
        client = _client_with(
            files,
            {"f1": "print(1)", "f2": "print(22)"},
            write_events=[
                ("/mnt/session/outputs/todo/main.py", "print(1)"),
                ("/mnt/session/outputs/utils/main.py", "print(22)"),
            ],
        )

        count = download_session_outputs(client, "sess-collide", tmp_path)

        assert count == 2
        assert (tmp_path / "todo" / "main.py").read_text(encoding="utf-8") == "print(1)"
        assert (tmp_path / "utils" / "main.py").read_text(encoding="utf-8") == "print(22)"

    def test_falls_back_when_duplicate_basename_and_size_are_ambiguous(self, tmp_path):
        """Two files with the same basename AND the same byte size can't be
        told apart - guessing would risk silently writing one file's bytes to
        the other's destination, so both fall back to their own logged
        content instead, and neither is downloaded via the Files API."""
        files = [
            _file("f1", "config.py", size_bytes=len(b"X = 1")),
            _file("f2", "config.py", size_bytes=len(b"X = 1")),
        ]
        client = _client_with(
            files,
            {},
            write_events=[
                ("/mnt/session/outputs/todo/config.py", "X = 1"),
                ("/mnt/session/outputs/utils/config.py", "X = 1"),
            ],
        )

        count = download_session_outputs(client, "sess-ambiguous", tmp_path)

        assert count == 2
        assert (tmp_path / "todo" / "config.py").read_text(encoding="utf-8") == "X = 1"
        assert (tmp_path / "utils" / "config.py").read_text(encoding="utf-8") == "X = 1"
        client.beta.files.download.assert_not_called()

    def test_falls_back_to_logged_content_when_files_list_raises(self, tmp_path):
        client = MagicMock()
        client.beta.sessions.events.list.return_value = [
            _write_event("/mnt/session/outputs/result.py", "print('ok')"),
        ]
        client.beta.files.list.side_effect = RuntimeError("API unavailable")

        count = download_session_outputs(client, "sess-outage", tmp_path)

        assert count == 1
        assert (tmp_path / "result.py").read_text(encoding="utf-8") == "print('ok')"
        client.beta.files.download.assert_not_called()

    def test_falls_back_to_logged_content_when_download_raises(self, tmp_path):
        client = MagicMock()
        client.beta.sessions.events.list.return_value = [
            _write_event("/mnt/session/outputs/result.py", "print('ok')"),
        ]
        client.beta.files.list.return_value = SimpleNamespace(
            data=[_file("f1", "result.py", size_bytes=len(b"print('ok')"))]
        )
        client.beta.files.download.side_effect = RuntimeError("download failed")

        count = download_session_outputs(client, "sess-dl-fail", tmp_path)

        assert count == 1
        assert (tmp_path / "result.py").read_text(encoding="utf-8") == "print('ok')"

    def test_falls_back_to_flat_files_api_listing_when_events_list_raises(self, tmp_path):
        """A sessions-events outage must not take down output retrieval entirely -
        it degrades to the flat basename-only behavior (no recovered paths),
        which is what this module did before event replay was added."""
        client = MagicMock()
        client.beta.sessions.events.list.side_effect = RuntimeError("events API unavailable")
        client.beta.files.list.return_value = SimpleNamespace(data=[_file("f1", "result.py")])
        client.beta.files.download.side_effect = lambda fid: _make_download("print('ok')")

        count = download_session_outputs(client, "sess-events-outage", tmp_path)

        assert count == 1
        assert (tmp_path / "result.py").read_text(encoding="utf-8") == "print('ok')"

    def test_handles_binary_content(self, tmp_path):
        files = [_file("f1", "chart.png")]
        client = _client_with(files, {"f1": b"\x89PNG\r\n"})

        download_session_outputs(client, "sess-3", tmp_path)

        assert (tmp_path / "chart.png").read_bytes() == b"\x89PNG\r\n"

    def test_follows_pagination_across_pages(self, tmp_path):
        # A real SDK page exposes iter_pages(); .data is only the current page.
        page1 = SimpleNamespace(data=[_file("f1", "a.txt")])
        page2 = SimpleNamespace(data=[_file("f2", "b.txt")])
        paged = SimpleNamespace(
            data=[_file("f1", "a.txt")],  # first page only — must NOT be used alone
            iter_pages=lambda: iter([page1, page2]),
        )
        client = MagicMock()
        client.beta.sessions.events.list.return_value = []
        client.beta.files.list.return_value = paged
        client.beta.files.download.side_effect = lambda fid: _make_download(fid)

        count = download_session_outputs(client, "sess-page", tmp_path)

        assert count == 2
        assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "f1"
        assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "f2"

    def test_accepts_plain_iterable_list_result(self, tmp_path):
        # files.list may return a directly-iterable page with no `.data`.
        client = MagicMock()
        client.beta.sessions.events.list.return_value = []
        client.beta.files.list.return_value = [_file("f1", "plain.txt")]
        client.beta.files.download.side_effect = lambda fid: _make_download("iter")

        count = download_session_outputs(client, "sess-iter", tmp_path)

        assert count == 1
        assert (tmp_path / "plain.txt").read_text(encoding="utf-8") == "iter"

    @pytest.mark.parametrize(
        "bad_name",
        ["../evil.txt", "/etc/passwd", "dir/../escape.txt", "..\\evil.txt", "C:\\evil.txt"],
    )
    def test_skips_unsafe_filenames(self, tmp_path, bad_name):
        files = [_file("f1", bad_name), _file("f2", "ok.txt")]
        client = _client_with(files, {"f1": "bad", "f2": "good"})

        before = {p.name for p in tmp_path.parent.iterdir()}
        count = download_session_outputs(client, "sess-4", tmp_path)

        assert count == 1
        assert (tmp_path / "ok.txt").read_text(encoding="utf-8") == "good"
        # Nothing escaped into the parent directory.
        assert {p.name for p in tmp_path.parent.iterdir()} == before

    def test_creates_output_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "out"
        client = _client_with([], {})

        download_session_outputs(client, "sess-5", new_dir, retries=0)

        assert new_dir.is_dir()

    def test_returns_zero_when_no_files(self, tmp_path):
        client = _client_with([], {})
        assert download_session_outputs(client, "sess-6", tmp_path, retries=0) == 0

    def test_retries_on_indexing_lag(self, tmp_path):
        client = MagicMock()
        client.beta.sessions.events.list.return_value = []
        # First list empty (indexing lag), second returns the file.
        client.beta.files.list.side_effect = [
            SimpleNamespace(data=[]),
            SimpleNamespace(data=[_file("f1", "late.txt")]),
        ]
        client.beta.files.download.side_effect = lambda fid: _make_download("here")

        with patch("src.outputs.time.sleep") as mock_sleep:
            count = download_session_outputs(client, "sess-7", tmp_path, retries=1, retry_delay=0.01)

        assert count == 1
        assert (tmp_path / "late.txt").read_text(encoding="utf-8") == "here"
        mock_sleep.assert_called_once()

    def test_retry_waits_for_the_specific_write_call_basename(self, tmp_path):
        """The retry loop must track whether the *requested* basename has
        landed, not just whether the list is non-empty - a different
        legitimate output file (e.g. one written via bash, not the 'write'
        tool) could otherwise satisfy 'non-empty' before the file a write
        call is actually waiting on has finished indexing. Both files are
        genuine session outputs (scope_id already restricts to those), so
        both are downloaded once the retry is satisfied."""
        client = MagicMock()
        client.beta.sessions.events.list.return_value = [
            _write_event("/mnt/session/outputs/result.py", "print('ok')"),
        ]
        client.beta.files.list.side_effect = [
            SimpleNamespace(data=[_file("bash-written", "input.csv")]),
            SimpleNamespace(data=[
                _file("bash-written", "input.csv"),
                _file("f1", "result.py", size_bytes=len(b"print('ok')")),
            ]),
        ]
        client.beta.files.download.side_effect = lambda fid: _make_download("print('ok')")

        with patch("src.outputs.time.sleep") as mock_sleep:
            count = download_session_outputs(client, "sess-unrelated", tmp_path, retries=1, retry_delay=0.01)

        assert count == 2
        assert client.beta.files.list.call_count == 2
        mock_sleep.assert_called_once()
        assert (tmp_path / "result.py").read_text(encoding="utf-8") == "print('ok')"
        assert (tmp_path / "input.csv").read_text(encoding="utf-8") == "print('ok')"

    def test_falls_back_to_id_when_filename_missing(self, tmp_path):
        files = [SimpleNamespace(id="f1", filename=None, size_bytes=None)]
        client = MagicMock()
        client.beta.sessions.events.list.return_value = []
        client.beta.files.list.return_value = SimpleNamespace(data=files)
        client.beta.files.download.side_effect = lambda fid: _make_download("data")

        count = download_session_outputs(client, "sess-8", tmp_path)

        assert count == 1
        assert (tmp_path / "f1").read_text(encoding="utf-8") == "data"


class TestListSessionOutputFiles:
    def test_returns_file_id_filename_pairs(self):
        files = [_file("f1", "draft.md"), _file("f2", "notes.txt")]
        client = _client_with(files, {})

        result = list_session_output_files(client, "sess-1")

        assert result == [("f1", "draft.md"), ("f2", "notes.txt")]

    def test_recovers_full_path_for_write_tool_files(self):
        files = [_file("f1", "main.py")]
        client = _client_with(
            files, {}, write_events=[("/mnt/session/outputs/todo/main.py", "# main")]
        )

        result = list_session_output_files(client, "sess-1")

        assert result == [("f1", "todo/main.py")]

    def test_falls_back_to_flat_listing_when_events_list_raises(self):
        client = MagicMock()
        client.beta.sessions.events.list.side_effect = RuntimeError("events API unavailable")
        client.beta.files.list.return_value = SimpleNamespace(data=[_file("f1", "draft.md")])

        result = list_session_output_files(client, "sess-1")

        assert result == [("f1", "draft.md")]

    def test_skips_ambiguous_duplicate_basenames(self):
        """Files that can't be safely correlated to a write call have no
        resolvable file_id/path pairing here (unlike download_session_outputs,
        there's no logged content to fall back to for a resource mount)."""
        files = [
            _file("f1", "config.py", size_bytes=len(b"X = 1")),
            _file("f2", "config.py", size_bytes=len(b"X = 1")),
        ]
        client = _client_with(
            files,
            {},
            write_events=[
                ("/mnt/session/outputs/todo/config.py", "X = 1"),
                ("/mnt/session/outputs/utils/config.py", "X = 1"),
            ],
        )

        result = list_session_output_files(client, "sess-1")

        assert result == []

    def test_skips_unsafe_filenames(self):
        files = [_file("f1", "../evil.txt"), _file("f2", "ok.txt")]
        client = _client_with(files, {})

        result = list_session_output_files(client, "sess-1")

        assert result == [("f2", "ok.txt")]

    def test_returns_empty_list_when_no_files(self):
        client = _client_with([], {})
        assert list_session_output_files(client, "sess-1", retries=0) == []

    def test_falls_back_to_id_when_filename_missing(self):
        files = [_file("f1", None)]
        client = _client_with(files, {})

        result = list_session_output_files(client, "sess-1")

        assert result == [("f1", "f1")]

    def test_unsafe_id_is_blocked_when_filename_missing(self):
        files = [_file("../evil", None)]
        client = _client_with(files, {})

        result = list_session_output_files(client, "sess-1")

        assert result == []
