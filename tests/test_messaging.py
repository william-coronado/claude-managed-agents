"""Unit tests for src/messaging.py"""
import pytest
from pathlib import Path
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


def _make_write_event(file_path: str, content: str):
    ev = _make_event("agent.tool_use", name="write")
    ev.input = {"file_path": file_path, "content": content}
    return ev


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

    def test_non_text_blocks_in_agent_message_are_skipped(self):
        from src.messaging import stream_message

        # A block without a .text attribute (e.g. a tool-result block) should
        # not cause an AttributeError; only text blocks contribute to output.
        non_text_block = MagicMock(spec=[])  # spec=[] → no attributes at all
        events = [
            _make_event("agent.message", content=[_make_block("Hello"), non_text_block]),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        result = stream_message(client, "sess-1", "hi")
        assert result == "Hello"

    # ------------------------------------------------------------------
    # write-tool file capture
    # ------------------------------------------------------------------

    def test_write_event_saves_file_when_output_dir_set(self, tmp_path):
        from src.messaging import stream_message

        events = [
            _make_write_event("/mnt/session/outputs/result.py", "print('hi')"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "go", output_dir=tmp_path)

        assert (tmp_path / "result.py").read_text() == "print('hi')"

    def test_write_event_preserves_subdirectory_structure(self, tmp_path):
        from src.messaging import stream_message

        events = [
            _make_write_event("/mnt/session/outputs/todo/main.py", "# main"),
            _make_write_event("/mnt/session/outputs/todo/utils/helpers.py", "# helpers"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "go", output_dir=tmp_path)

        assert (tmp_path / "todo" / "main.py").read_text() == "# main"
        assert (tmp_path / "todo" / "utils" / "helpers.py").read_text() == "# helpers"

    def test_write_event_skips_files_outside_remote_dir(self, tmp_path):
        from src.messaging import stream_message

        events = [
            _make_write_event("/mnt/session/uploads/secret.txt", "secret"),
            _make_write_event("/mnt/session/outputs/ok.txt", "ok"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "go", output_dir=tmp_path)

        assert not (tmp_path / "secret.txt").exists()
        assert (tmp_path / "ok.txt").read_text() == "ok"

    def test_write_event_custom_remote_dir(self, tmp_path):
        from src.messaging import stream_message

        events = [
            _make_write_event("/mnt/session/outputs/todo/main.py", "# main"),
            _make_write_event("/mnt/session/outputs/notes/readme.md", "# notes"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "go", output_dir=tmp_path,
                       remote_dir="/mnt/session/outputs/todo")

        assert (tmp_path / "main.py").read_text() == "# main"
        assert not (tmp_path / "readme.md").exists()

    def test_write_event_not_saved_when_no_output_dir(self, tmp_path):
        from src.messaging import stream_message

        events = [
            _make_write_event("/mnt/session/outputs/result.py", "print('hi')"),
            _make_event("session.status_idle"),
        ]
        client = self._make_client(events)
        stream_message(client, "sess-1", "go")  # no output_dir

        assert not (tmp_path / "result.py").exists()

    def test_non_write_tool_not_saved(self, tmp_path):
        from src.messaging import stream_message

        bash_event = _make_event("agent.tool_use", name="bash")
        bash_event.input = {"command": "echo hello > /mnt/session/outputs/out.txt"}
        events = [bash_event, _make_event("session.status_idle")]
        client = self._make_client(events)
        stream_message(client, "sess-1", "go", output_dir=tmp_path)

        assert not list(tmp_path.iterdir())
