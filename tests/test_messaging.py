"""Unit tests for src/messaging.py"""
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers — build fake event objects
# ---------------------------------------------------------------------------

def _make_event(type_, **kwargs):
    ev = MagicMock()
    ev.type = type_
    for k, v in kwargs.items():
        setattr(ev, k, v)
    return ev


def _make_block(text):
    b = MagicMock()
    b.text = text
    return b


def _make_stream(events):
    """Context-manager that yields events."""
    class FakeStream:
        def __enter__(self):
            return iter(events)

        def __exit__(self, *_):
            pass

    return FakeStream()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStreamMessage:
    def _make_client(self, events):
        client = MagicMock()
        client.beta.sessions.events.stream.return_value = _make_stream(events)
        return client

    def test_returns_agent_message_text(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("agent.message", content=[_make_block("Hello "), _make_block("world")]),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        result = stream_message(client, "sess-1", "hi")
        assert result == "Hello world"
        client.beta.sessions.events.send.assert_called_once_with(
            "sess-1",
            events=[{"type": "user.message", "content": [{"type": "text", "text": "hi"}]}],
        )

    def test_prints_agent_message_to_stdout(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("agent.message", content=[_make_block("Printed text")]),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "hi")
        captured = capsys.readouterr()
        assert "Printed text" in captured.out

    def test_tool_use_event_printed(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("agent.tool_use", name="bash"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "run tool")
        captured = capsys.readouterr()
        assert "[Tool: bash]" in captured.out

    def test_session_error_raises_runtime_error(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("session.error", message="something went wrong"),
        ]
        client = self._make_client(events)
        with pytest.raises(RuntimeError, match="Session error: something went wrong"):
            stream_message(client, "sess-1", "hi")
        captured = capsys.readouterr()
        assert "[Error: something went wrong]" in captured.out

    def test_returns_empty_string_when_no_message_blocks(self):
        from src.messaging import stream_message

        events = [_make_event("session.status_idle")]
        client = self._make_client(events)
        result = stream_message(client, "sess-1", "hi")
        assert result == ""

    def test_accumulates_multiple_messages(self):
        from src.messaging import stream_message

        events = [
            _make_event("agent.message", content=[_make_block("Part1")]),
            _make_event("agent.message", content=[_make_block("Part2")]),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        result = stream_message(client, "sess-1", "hi")
        assert result == "Part1Part2"
