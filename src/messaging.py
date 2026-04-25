import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_OUTPUTS_PREFIX = "/mnt/session/outputs/"


def stream_message(
    client,
    session_id: str,
    text: str,
    output_dir: Optional[Path] = None,
    remote_dir: str = _OUTPUTS_PREFIX,
) -> str:
    """Open SSE stream, send user message, print agent output to stdout, and return it.

    If output_dir is set, 'write' tool calls targeting remote_dir are intercepted and
    saved locally in real time, preserving subdirectory structure under remote_dir.
    """
    if output_dir is not None and not remote_dir.endswith("/"):
        remote_dir = remote_dir + "/"
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
                    if output_dir is not None and tool_name == "write":
                        _capture_write_event(event.input, output_dir, remote_dir)
                case "session.error":
                    error_msg = getattr(event, "message", "unknown error")
                    print(f"\n[Error: {error_msg}]", flush=True)
                    raise RuntimeError(f"Session error: {error_msg}")
                case "session.status_idle":
                    print("\n[Done]")
                    break
    return "".join(output_parts)


def _capture_write_event(tool_input: dict, output_dir: Path, remote_dir: str) -> None:
    file_path = str(tool_input.get("file_path", ""))
    content = str(tool_input.get("content", ""))
    if not file_path.startswith(remote_dir):
        return
    rel_path = file_path[len(remote_dir):]
    if not rel_path:
        return
    dest = output_dir / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    logger.info("Captured %s -> %s", file_path, dest)
