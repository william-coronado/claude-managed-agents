"""Unit tests for the ai_delivery_team runner helpers (no live API)."""
import argparse
import pytest
from unittest.mock import patch

from use_cases.ai_delivery_team.run import _resolve_text, _build_resources


def _args(**kw):
    defaults = dict(repo=None, repo_token=None, branch="main", memory_store=None)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


class TestResolveText:
    def test_literal_text(self):
        assert _resolve_text("just a brief", "brief") == "just a brief"

    def test_reads_file_when_prefixed(self, tmp_path):
        f = tmp_path / "brief.md"
        f.write_text("brief from file")
        assert _resolve_text(f"@{f}", "brief") == "brief from file"

    def test_missing_file_raises_clean_systemexit(self, tmp_path):
        missing = tmp_path / "nope.md"
        with pytest.raises(SystemExit, match="brief file not found"):
            _resolve_text(f"@{missing}", "brief")


class TestBuildResources:
    def test_empty_when_no_repo_or_memory(self):
        assert _build_resources(_args()) == []

    def test_github_repo_resource_from_flag_token(self):
        res = _build_resources(_args(repo="https://github.com/acme/widget", repo_token="ghp_x"))
        assert res == [{
            "type": "github_repository",
            "url": "https://github.com/acme/widget",
            "authorization_token": "ghp_x",
            "checkout": {"type": "branch", "name": "main"},
        }]

    def test_github_repo_token_from_env(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_env"}):
            res = _build_resources(_args(repo="https://github.com/acme/widget"))
        assert res[0]["authorization_token"] == "ghp_env"

    def test_repo_without_token_errors(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(SystemExit, match="GITHUB_TOKEN"):
                _build_resources(_args(repo="https://github.com/acme/widget"))

    def test_memory_store_resource(self):
        res = _build_resources(_args(memory_store="memstore_1"))
        assert res == [{"type": "memory_store", "memory_store_id": "memstore_1", "access": "read_write"}]

    def test_repo_and_memory_together(self):
        res = _build_resources(_args(repo="https://github.com/a/b", repo_token="t", memory_store="ms1"))
        assert {r["type"] for r in res} == {"github_repository", "memory_store"}
