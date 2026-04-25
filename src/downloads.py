import logging
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger(__name__)

_OUTPUTS_PREFIX = "/mnt/session/outputs/"


def download_session_outputs(
    client: Anthropic,
    session_id: str,
    output_dir: Path,
    remote_dir: str = _OUTPUTS_PREFIX,
) -> int:
    """Download files written by the agent during a session by replaying session events.

    Iterates through session events and captures content from 'write' tool calls
    targeting remote_dir. Subdirectory structure under remote_dir is preserved.
    Returns the count of files saved.
    """
    if not remote_dir.endswith("/"):
        remote_dir = remote_dir + "/"
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for event in client.beta.sessions.events.list(session_id):
        if event.type != "agent.tool_use":
            continue
        if getattr(event, "name", None) != "write":
            continue
        tool_input = getattr(event, "input", {}) or {}
        file_path = str(tool_input.get("file_path", ""))
        content = str(tool_input.get("content", ""))
        if not file_path.startswith(remote_dir):
            continue
        rel_path = file_path[len(remote_dir):]
        if not rel_path:
            continue
        dest = output_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        logger.info("Saved %s -> %s", file_path, dest)
        count += 1
    if count:
        logger.info("Downloaded %d file(s) to %s", count, output_dir)
    else:
        logger.debug("No write tool calls found targeting %s in session %s", remote_dir, session_id)
    return count
