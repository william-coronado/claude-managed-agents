"""Tests for src/downloads.py re-export and the download_outputs.py CLI."""
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_downloads_reexports_outputs_implementation():
    import src.downloads
    import src.outputs

    assert src.downloads.download_session_outputs is src.outputs.download_session_outputs


class TestDownloadOutputsCLI:
    def test_main_calls_download_with_parsed_args(self, tmp_path):
        import download_outputs

        mock_client = MagicMock()
        mock_cfg = MagicMock(api_key=None)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("download_outputs.load_global_config", return_value=mock_cfg), \
             patch("download_outputs.Anthropic", return_value=mock_client), \
             patch("download_outputs.download_session_outputs", return_value=2) as mock_dl, \
             patch("sys.argv", ["download_outputs.py", "--session-id", "sess-99",
                                "--output-dir", str(tmp_path)]):
            download_outputs.main()

        mock_dl.assert_called_once_with(mock_client, "sess-99", Path(str(tmp_path)))

    def test_main_errors_without_api_key(self, tmp_path):
        import download_outputs
        import pytest

        mock_cfg = MagicMock(api_key="")

        with patch.dict("os.environ", {}, clear=True), \
             patch("download_outputs.load_global_config", return_value=mock_cfg), \
             patch("sys.argv", ["download_outputs.py", "--session-id", "s",
                                "--output-dir", str(tmp_path)]):
            with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
                download_outputs.main()
