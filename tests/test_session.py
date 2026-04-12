"""Unit tests for src/session.py"""
import pytest
from unittest.mock import MagicMock, patch

from src.session import create_session


class TestCreateSession:
    def _make_client(self, session_id="sess-123"):
        client = MagicMock()
        mock_session = MagicMock()
        mock_session.id = session_id
        client.beta.sessions.create.return_value = mock_session
        return client

    def test_basic_creation(self):
        client = self._make_client()
        session = create_session(client, "agent-1", "env-1")
        assert session.id == "sess-123"
        client.beta.sessions.create.assert_called_once_with(
            agent="agent-1", environment_id="env-1"
        )

    def test_title_passed_when_printable(self):
        client = self._make_client()
        create_session(client, "agent-1", "env-1", title="Hello World")
        client.beta.sessions.create.assert_called_once_with(
            agent="agent-1", environment_id="env-1", title="Hello World"
        )

    def test_title_strips_non_printable_chars(self):
        client = self._make_client()
        # Newlines, tabs and null bytes are non-printable
        create_session(client, "agent-1", "env-1", title="Line1\nLine2\t\x00End")
        kwargs = client.beta.sessions.create.call_args.kwargs
        assert kwargs["title"] == "Line1Line2End"

    def test_title_empty_after_stripping_is_omitted(self):
        client = self._make_client()
        # Title consists entirely of non-printable / whitespace chars
        create_session(client, "agent-1", "env-1", title="\n\t\r\x00")
        kwargs = client.beta.sessions.create.call_args.kwargs
        assert "title" not in kwargs

    def test_title_whitespace_only_is_omitted(self):
        client = self._make_client()
        create_session(client, "agent-1", "env-1", title="   ")
        kwargs = client.beta.sessions.create.call_args.kwargs
        assert "title" not in kwargs

    def test_none_title_omitted(self):
        client = self._make_client()
        create_session(client, "agent-1", "env-1", title=None)
        kwargs = client.beta.sessions.create.call_args.kwargs
        assert "title" not in kwargs

    def test_title_leading_trailing_whitespace_stripped(self):
        client = self._make_client()
        create_session(client, "agent-1", "env-1", title="  Hello  ")
        kwargs = client.beta.sessions.create.call_args.kwargs
        assert kwargs["title"] == "Hello"
