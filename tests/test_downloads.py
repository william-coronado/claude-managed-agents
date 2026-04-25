"""Unit tests for src/downloads.py and download_outputs.py CLI."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


def _make_client():
    return MagicMock()


def _make_file_meta(id_: str, filename: str, downloadable=True):
    m = MagicMock()
    m.id = id_
    m.filename = filename
    m.downloadable = downloadable
    return m


class TestDownloadSessionOutputs:
    def _call(self, client, session_id, output_dir):
        from src.downloads import download_session_outputs
        return download_session_outputs(client, session_id, output_dir)

    def test_downloads_all_downloadable_files(self, tmp_path):
        client = _make_client()
        files = [
            _make_file_meta("f1", "result.py", downloadable=True),
            _make_file_meta("f2", "report.md", downloadable=True),
        ]
        client.beta.files.list.return_value = files
        mock_binary = MagicMock()
        client.beta.files.download.return_value = mock_binary

        count = self._call(client, "sess-1", tmp_path)

        assert count == 2
        client.beta.files.list.assert_called_once_with(scope_id="sess-1")
        assert client.beta.files.download.call_count == 2
        client.beta.files.download.assert_any_call("f1")
        client.beta.files.download.assert_any_call("f2")
        mock_binary.write_to_file.assert_any_call(tmp_path / "result.py")
        mock_binary.write_to_file.assert_any_call(tmp_path / "report.md")

    def test_skips_non_downloadable_files(self, tmp_path):
        client = _make_client()
        files = [
            _make_file_meta("f1", "ok.py", downloadable=True),
            _make_file_meta("f2", "blocked.bin", downloadable=False),
        ]
        client.beta.files.list.return_value = files
        client.beta.files.download.return_value = MagicMock()

        count = self._call(client, "sess-2", tmp_path)

        assert count == 1
        client.beta.files.download.assert_called_once_with("f1")

    def test_downloadable_none_treated_as_downloadable(self, tmp_path):
        client = _make_client()
        files = [_make_file_meta("f1", "file.txt", downloadable=None)]
        client.beta.files.list.return_value = files
        client.beta.files.download.return_value = MagicMock()

        count = self._call(client, "sess-3", tmp_path)

        assert count == 1
        client.beta.files.download.assert_called_once_with("f1")

    def test_returns_zero_when_no_files(self, tmp_path):
        client = _make_client()
        client.beta.files.list.return_value = []

        count = self._call(client, "sess-4", tmp_path)

        assert count == 0
        client.beta.files.download.assert_not_called()

    def test_creates_output_dir_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "output"
        client = _make_client()
        client.beta.files.list.return_value = []

        self._call(client, "sess-5", new_dir)

        assert new_dir.is_dir()

    def test_write_to_file_called_with_correct_path(self, tmp_path):
        client = _make_client()
        files = [_make_file_meta("f1", "my_file.py")]
        client.beta.files.list.return_value = files
        mock_binary = MagicMock()
        client.beta.files.download.return_value = mock_binary

        self._call(client, "sess-6", tmp_path / "out")

        mock_binary.write_to_file.assert_called_once_with(tmp_path / "out" / "my_file.py")


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

        mock_dl.assert_called_once_with(mock_client, "sess-99", Path(str(tmp_path)))
