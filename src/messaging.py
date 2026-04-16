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
                        # Only text blocks carry a .text attribute; skip tool-result
                        # blocks or other structured content types gracefully.
                        block_text = getattr(block, "text", None)
                        if block_text is not None:
                            print(block_text, end="", flush=True)
                            output_parts.append(block_text)
                case "agent.tool_use":
                    print(f"\n[Tool: {event.name}]", flush=True)
                case "session.error":
                    error_msg = getattr(event, "message", "unknown error")
                    print(f"\n[Error: {error_msg}]", flush=True)
                    raise RuntimeError(f"Session error: {error_msg}")
                case "session.status_idle":
                    print("\n[Done]")
                    break
    return "".join(output_parts)
