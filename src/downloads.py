<<<<<<< HEAD
"""Post-session output download.
=======
import logging
import time
from collections import Counter
from pathlib import Path
>>>>>>> 83c0e7f (Update .gitignore, remove obsolete .mcp.json, and enhance download logic with fallback mechanisms in downloads.py and corresponding tests)

Historically this module replayed session events and re-derived file content
from ``write`` tool calls, because the platform did not expose agent-created
files after a session. The platform now captures anything written under
``/mnt/session/outputs/`` and serves it through the Files API, so the canonical
implementation lives in ``src.outputs``. This module re-exports it for
backward compatibility.
"""
from src.outputs import download_session_outputs

<<<<<<< HEAD
__all__ = ["download_session_outputs"]
=======
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
      stored bytes for each file, rather than trusting the tool call's logged 'content' input.

    Each write event is matched to a Files API entry by (basename, byte size). A match is
    used only when it's unambiguous - exactly one candidate of that basename has the
    expected byte size, or exactly one candidate of that basename exists at all. Ties (e.g.
    two same-directory-less files with the same basename *and* the same size) are never
    guessed at, since picking wrong would silently write one file's bytes to another file's
    destination - worse than falling back. Any file that can't be resolved this way (an
    unresolved tie, a Files API failure, or a file written via bash/code-exec rather than
    the 'write' tool) falls back to the event's own logged 'content' so nothing is dropped.

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

    expected_by_basename = Counter(rel_path.rsplit("/", 1)[-1] for rel_path, _ in write_calls)
    try:
        files_by_basename = _list_session_files_with_retry(client, session_id, expected_by_basename)
    except Exception as exc:
        logger.warning(
            "Files API listing failed for session %s (%s); falling back to logged tool content for all files",
            session_id, exc,
        )
        files_by_basename = {}

    count = 0
    for rel_path, content in write_calls:
        basename = rel_path.rsplit("/", 1)[-1]
        dest = output_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        candidates = files_by_basename.get(basename, [])
        byte_length = len(content.encode("utf-8"))
        exact_matches = [c for c in candidates if getattr(c, "size_bytes", None) == byte_length]
        if len(exact_matches) == 1:
            match = exact_matches[0]
        elif not exact_matches and len(candidates) == 1:
            match = candidates[0]
        else:
            match = None
            if len(exact_matches) > 1 or len(candidates) > 1:
                logger.warning(
                    "Ambiguous Files API match for %s (%d candidate(s) named %r); "
                    "falling back to logged tool content rather than guessing",
                    rel_path, len(candidates), basename,
                )

        if match is not None:
            candidates.remove(match)
            try:
                response = client.beta.files.download(match.id)
                response.write_to_file(dest)
                logger.info("Saved %s -> %s (files API id=%s)", rel_path, dest, match.id)
            except Exception as exc:
                logger.warning(
                    "Files API download failed for %s (id=%s): %s; falling back to logged tool content",
                    rel_path, match.id, exc,
                )
                dest.write_text(content, encoding="utf-8")
        else:
            dest.write_text(content, encoding="utf-8")
            logger.warning("No Files API match for %s; wrote logged tool content instead", rel_path)

        count += 1

    logger.info("Downloaded %d file(s) to %s", count, output_dir)
    return count


def _list_session_files_with_retry(
    client: Anthropic, session_id: str, expected_by_basename: Counter,
) -> dict:
    """List files scoped to a session, retrying to absorb the platform's brief
    (~1-3s) indexing lag between session idle and output files appearing in files.list.

    Retries until every expected basename has at least as many candidates as write calls
    that produced it - not just until the *total* file count is large enough, since
    scope_id can also return session files unrelated to the requested writes (e.g. mounted
    input resources), which would otherwise let the loop stop before the actual targets land.
    """
    files_by_basename: dict = {}
    for attempt in range(_FILES_LIST_ATTEMPTS):
        files_by_basename = {}
        for f in client.beta.files.list(scope_id=session_id, betas=[_MANAGED_AGENTS_BETA]):
            files_by_basename.setdefault(f.filename, []).append(f)
        if all(
            len(files_by_basename.get(basename, [])) >= needed
            for basename, needed in expected_by_basename.items()
        ):
            break
        if attempt < _FILES_LIST_ATTEMPTS - 1:
            time.sleep(_FILES_LIST_RETRY_DELAY_SECONDS)
    return files_by_basename
>>>>>>> 83c0e7f (Update .gitignore, remove obsolete .mcp.json, and enhance download logic with fallback mechanisms in downloads.py and corresponding tests)
