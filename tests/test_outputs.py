"""Unit tests for src/outputs.py (session outputs via the Files API)."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.constants import MANAGED_AGENTS_BETA
from src.outputs import download_session_outputs


def _file(id_, filename):
    return SimpleNamespace(id=id_, filename=filename)


def _make_download(content):
    """A fake Files download response exposing write_to_file()."""
    dl = MagicMock()

    def _write(path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)

    dl.write_to_file.side_effect = _write
    return dl


def _client_with(files, contents):
    """files: list of file objects; contents: {file_id: content}."""
    client = MagicMock()
    client.beta.files.list.return_value = SimpleNamespace(data=files)
    client.beta.files.download.side_effect = lambda fid: _make_download(contents[fid])
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
        assert (tmp_path / "result.py").read_text() == "print('ok')"
        assert (tmp_path / "report.md").read_text() == "# Report"

    def test_preserves_subdirectory_structure(self, tmp_path):
        files = [_file("f1", "todo/main.py"), _file("f2", "todo/utils/helpers.py")]
        client = _client_with(files, {"f1": "# main", "f2": "# helpers"})

        download_session_outputs(client, "sess-2", tmp_path)

        assert (tmp_path / "todo" / "main.py").read_text() == "# main"
        assert (tmp_path / "todo" / "utils" / "helpers.py").read_text() == "# helpers"

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
        client.beta.files.list.return_value = paged
        client.beta.files.download.side_effect = lambda fid: _make_download(fid)

        count = download_session_outputs(client, "sess-page", tmp_path)

        assert count == 2
        assert (tmp_path / "a.txt").read_text() == "f1"
        assert (tmp_path / "b.txt").read_text() == "f2"

    def test_accepts_plain_iterable_list_result(self, tmp_path):
        # files.list may return a directly-iterable page with no `.data`.
        client = MagicMock()
        client.beta.files.list.return_value = [_file("f1", "plain.txt")]
        client.beta.files.download.side_effect = lambda fid: _make_download("iter")

        count = download_session_outputs(client, "sess-iter", tmp_path)

        assert count == 1
        assert (tmp_path / "plain.txt").read_text() == "iter"

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
        assert (tmp_path / "ok.txt").read_text() == "good"
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
        # First list empty (indexing lag), second returns the file.
        client.beta.files.list.side_effect = [
            SimpleNamespace(data=[]),
            SimpleNamespace(data=[_file("f1", "late.txt")]),
        ]
        client.beta.files.download.side_effect = lambda fid: _make_download("here")

        with patch("src.outputs.time.sleep") as mock_sleep:
            count = download_session_outputs(client, "sess-7", tmp_path, retries=1, retry_delay=0.01)

        assert count == 1
        assert (tmp_path / "late.txt").read_text() == "here"
        mock_sleep.assert_called_once()

    def test_falls_back_to_id_when_filename_missing(self, tmp_path):
        files = [SimpleNamespace(id="f1", filename=None)]
        client = MagicMock()
        client.beta.files.list.return_value = SimpleNamespace(data=files)
        client.beta.files.download.side_effect = lambda fid: _make_download("data")

        count = download_session_outputs(client, "sess-8", tmp_path)

        assert count == 1
        assert (tmp_path / "f1").read_text() == "data"
