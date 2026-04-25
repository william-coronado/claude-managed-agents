import logging

logger = logging.getLogger(__name__)


def stream_message(client, session_id: str, text: str) -> str:
    """Open SSE stream, send user message, print agent output to stdout, and return it."""
    output_parts: list[str] = []
    with client.beta.sessions.events.stream(session_id) as stream:
        client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        )
        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        block_text = getattr(block, "text", None)
                        if block_text is None:
                            logger.debug("Skipping non-text block type=%r in agent.message", getattr(block, "type", "<unknown>"))
                        else:
                            print(block_text, end="", flush=True)
                            output_parts.append(block_text)
                case "agent.tool_use":
                    tool_name = getattr(event, "name", "<unknown>")
                    print(f"\n[Tool: {tool_name}]", flush=True)
                case "session.error":
                    error_msg = getattr(event, "message", "unknown error")
                    print(f"\n[Error: {error_msg}]", flush=True)
                    raise RuntimeError(f"Session error: {error_msg}")
                case "session.status_idle":
                    print("\n[Done]")
                    break
    return "".join(output_parts)
