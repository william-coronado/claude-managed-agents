def stream_message(client, session_id: str, text: str) -> None:
    """Open SSE stream, send user message, print agent output to stdout."""
    with client.beta.sessions.events.stream(session_id) as stream:
        client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        )
        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        print(block.text, end="", flush=True)
                case "agent.tool_use":
                    print(f"\n[Tool: {event.name}]", flush=True)
                case "session.status_idle":
                    print("\n[Done]")
                    break
