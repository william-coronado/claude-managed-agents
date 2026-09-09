import logging
import time
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger(__name__)

_OUTPUTS_PREFIX = "/mnt/session/outputs/"
_MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"
_FILES_LIST_ATTEMPTS = 3
_FILES_LIST_RETRY_DELAY_SECONDS = 2.0


def download_session_outputs(
    client: Anthropic,
    session_id: str,
    output_dir: Path,
    remote_dir: str = _OUTPUTS_PREFIX,
) -> int:
    """Download files the agent wrote to remote_dir during a session.

    Combines two data sources, since neither is sufficient alone:
    - Replaying session events (agent.tool_use 'write' calls) gives the full remote path
      of every file written. The Files API only reports a basename, so two files with the
      same name in different subdirectories would otherwise be indistinguishable.
    - The Files API (files.list(scope_id=...) / files.download()) gives the platform's own
      stored bytes for each file, rather than trusting the tool call's logged 'content'
      input, which the event stream truncates for very large writes.

    Each write event is matched to a Files API entry by (basename, byte size) - the closest
    correlation available, since the Files API exposes no path. If no match is found (a
    lagging index, or a file written via bash/code-exec rather than the 'write' tool), the
    event's own 'content' is written instead so no file is silently dropped.

    Preserves subdirectory structure under remote_dir. Returns the count of files saved.
    """
    if not remote_dir.endswith("/"):
        remote_dir = remote_dir + "/"

    write_calls: list[tuple[str, str]] = []  # (path relative to remote_dir, logged content)
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
        write_calls.append((rel_path, content))

    output_dir.mkdir(parents=True, exist_ok=True)
    if not write_calls:
        logger.debug("No write tool calls found targeting %s in session %s", remote_dir, session_id)
        return 0

    files_by_basename = _list_session_files_with_retry(client, session_id, expected=len(write_calls))

    count = 0
    for rel_path, content in write_calls:
        basename = rel_path.rsplit("/", 1)[-1]
        dest = output_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        candidates = files_by_basename.get(basename, [])
        byte_length = len(content.encode("utf-8"))
        match = next((c for c in candidates if getattr(c, "size_bytes", None) == byte_length), None)
        if match is None and candidates:
            match = candidates[0]

        if match is not None:
            candidates.remove(match)
            response = client.beta.files.download(match.id)
            response.write_to_file(dest)
            logger.info("Saved %s -> %s (files API id=%s)", rel_path, dest, match.id)
        else:
            dest.write_text(content, encoding="utf-8")
            logger.warning("No Files API match for %s; wrote logged tool content instead", rel_path)

        count += 1

    logger.info("Downloaded %d file(s) to %s", count, output_dir)
    return count


def _list_session_files_with_retry(client: Anthropic, session_id: str, expected: int) -> dict:
    """List files scoped to a session, retrying to absorb the platform's brief
    (~1-3s) indexing lag between session idle and output files appearing in files.list.
    """
    files_by_basename: dict = {}
    for attempt in range(_FILES_LIST_ATTEMPTS):
        files_by_basename = {}
        for f in client.beta.files.list(scope_id=session_id, betas=[_MANAGED_AGENTS_BETA]):
            files_by_basename.setdefault(f.filename, []).append(f)
        if sum(len(v) for v in files_by_basename.values()) >= expected:
            break
        if attempt < _FILES_LIST_ATTEMPTS - 1:
            time.sleep(_FILES_LIST_RETRY_DELAY_SECONDS)
    return files_by_basename
