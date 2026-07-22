"""Unit tests for src/messaging.py"""
import pytest
from unittest.mock import MagicMock


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


def _stop(type_):
    sr = MagicMock()
    sr.type = type_
    return sr


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

    def test_returns_agent_message_text(self):
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
        assert "Printed text" in capsys.readouterr().out

    def test_tool_use_event_printed(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("agent.tool_use", name="bash"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "run tool")
        assert "[Tool: bash]" in capsys.readouterr().out

    def test_session_error_raises_runtime_error(self, capsys):
        from src.messaging import stream_message

        events = [_make_event("session.error", message="something went wrong")]
        client = self._make_client(events)
        with pytest.raises(RuntimeError, match="Session error: something went wrong"):
            stream_message(client, "sess-1", "hi")
        assert "[Error: something went wrong]" in capsys.readouterr().out

    def test_returns_empty_string_when_no_message_blocks(self):
        from src.messaging import stream_message

        events = [_make_event("session.status_idle")]
        client = self._make_client(events)
        assert stream_message(client, "sess-1", "hi") == ""

    def test_accumulates_multiple_messages(self):
        from src.messaging import stream_message

        events = [
            _make_event("agent.message", content=[_make_block("Part1")]),
            _make_event("agent.message", content=[_make_block("Part2")]),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        assert stream_message(client, "sess-1", "hi") == "Part1Part2"

    def test_non_text_blocks_in_agent_message_are_skipped(self):
        from src.messaging import stream_message

        non_text_block = MagicMock(spec=[])  # no attributes at all
        events = [
            _make_event("agent.message", content=[_make_block("Hello"), non_text_block]),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        assert stream_message(client, "sess-1", "hi") == "Hello"

    # ------------------------------------------------------------------
    # Corrected stream gate (idle / terminated / requires_action)
    # ------------------------------------------------------------------

    def test_terminated_event_breaks_stream(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("agent.message", content=[_make_block("bye")]),
            _make_event("session.status_terminated"),
            _make_event("agent.message", content=[_make_block("SHOULD NOT APPEAR")]),
        ]
        client = self._make_client(events)
        result = stream_message(client, "sess-1", "hi")
        assert result == "bye"
        assert "[Terminated]" in capsys.readouterr().out

    def test_terminal_idle_breaks(self):
        from src.messaging import stream_message

        events = [
            _make_event("agent.message", content=[_make_block("done")]),
            _make_event("session.status_idle", stop_reason=_stop("end_turn")),
            _make_event("agent.message", content=[_make_block("AFTER")]),
        ]
        client = self._make_client(events)
        assert stream_message(client, "sess-1", "hi") == "done"

    def test_requires_action_idle_does_not_break(self):
        from src.messaging import stream_message

        # A transient idle (waiting on the client) must not end the turn;
        # streaming continues until a terminal idle.
        events = [
            _make_event("agent.message", content=[_make_block("A")]),
            _make_event("session.status_idle", stop_reason=_stop("requires_action")),
            _make_event("agent.message", content=[_make_block("B")]),
            _make_event("session.status_idle", stop_reason=_stop("end_turn")),
        ]
        client = self._make_client(events)
        assert stream_message(client, "sess-1", "hi") == "AB"

    def test_on_event_callback_invoked_for_every_event(self):
        from src.messaging import stream_message

        seen = []
        events = [
            _make_event("agent.tool_use", name="bash"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "hi", on_event=lambda e: seen.append(e.type))
        assert seen == ["agent.tool_use", "session.status_idle"]

    def test_outcome_grade_printed(self, capsys):
        from src.messaging import stream_message

        events = [
            _make_event("span.outcome_evaluation_end", result="satisfied"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "hi")
        assert "[Outcome grade: satisfied]" in capsys.readouterr().out
