import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _stop_reason_type(event) -> Optional[str]:
    """Extract stop_reason.type from an idle event (object or dict shaped)."""
    sr = getattr(event, "stop_reason", None)
    if sr is None:
        return None
    if isinstance(sr, dict):
        return sr.get("type")
    return getattr(sr, "type", None)


def _is_terminal_idle(event) -> bool:
    """True when a session.status_idle event means the turn is finished.

    Idle is transient when the agent is blocked waiting on the client
    (stop_reason.type == "requires_action" — a tool confirmation or custom
    tool result). Any other stop reason (end_turn, retries_exhausted) is
    terminal for this turn.
    """
    return _stop_reason_type(event) != "requires_action"


def _consume_stream(stream, output_parts: list, on_event: Optional[Callable]) -> None:
    """Consume an open SSE stream, printing output and collecting agent text.

    Breaks on session.status_terminated or a terminal session.status_idle;
    keeps streaming through a transient idle (requires_action).
    """
    for event in stream:
        if on_event is not None:
            on_event(event)
        etype = getattr(event, "type", None)

        if etype == "agent.message":
            for block in event.content:
                block_text = getattr(block, "text", None)
                if block_text is None:
                    logger.debug(
                        "Skipping non-text block type=%r in agent.message",
                        getattr(block, "type", "<unknown>"),
                    )
                else:
                    print(block_text, end="", flush=True)
                    output_parts.append(block_text)
        elif etype == "agent.tool_use":
            print(f"\n[Tool: {getattr(event, 'name', '<unknown>')}]", flush=True)
        elif etype == "agent.custom_tool_use":
            print(f"\n[Custom tool: {getattr(event, 'name', '<unknown>')}]", flush=True)
        elif etype in ("agent.thread_message_sent", "agent.thread_message_received"):
            who = getattr(event, "to_agent_name", None) or getattr(event, "from_agent_name", "<agent>")
            verb = "->" if etype.endswith("sent") else "<-"
            print(f"\n[Thread {verb} {who}]", flush=True)
        elif etype == "session.thread_created":
            print(f"\n[Subagent started: {getattr(event, 'agent_name', '<agent>')}]", flush=True)
        elif etype == "span.outcome_evaluation_end":
            print(f"\n[Outcome grade: {getattr(event, 'result', '<unknown>')}]", flush=True)
        elif etype == "session.error":
            error_msg = getattr(event, "message", "unknown error")
            print(f"\n[Error: {error_msg}]", flush=True)
            raise RuntimeError(f"Session error: {error_msg}")
        elif etype == "session.status_terminated":
            print("\n[Terminated]")
            break
        elif etype == "session.status_idle":
            if _is_terminal_idle(event):
                print("\n[Done]")
                break
            # Transient idle (requires_action) — the agent is waiting on the
            # client; keep the stream open so a caller/on_event can respond.


def stream_session(
    client,
    session_id: str,
    kickoff: Callable[[], None],
    on_event: Optional[Callable[[object], None]] = None,
) -> str:
    """Open the SSE stream, run ``kickoff`` to send initial event(s), consume.

    Stream-first ordering: the stream is opened before ``kickoff`` fires, so no
    early events are missed. Returns the accumulated agent text. ``kickoff``
    sends whatever starts the turn — a ``user.message`` (see ``stream_message``)
    or a ``user.define_outcome`` (see ``src.team``).
    """
    output_parts: list[str] = []
    with client.beta.sessions.events.stream(session_id) as stream:
        kickoff()
        _consume_stream(stream, output_parts, on_event)
    return "".join(output_parts)


def stream_message(
    client,
    session_id: str,
    text: str,
    on_event: Optional[Callable[[object], None]] = None,
) -> str:
    """Send a user message and stream the agent's response, returning its text."""
    def _send() -> None:
        client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        )

    return stream_session(client, session_id, _send, on_event)
