"""Download files an agent wrote during a session, using the Files API.

The managed-agents platform captures anything the agent writes under
``/mnt/session/outputs/`` and exposes it through the Files API scoped to the
session. This replaces the older approach of intercepting ``write`` tool
events (which only worked for text files and re-derived content from the event
stream). Session outputs support binary artifacts (``.xlsx``, ``.pptx``,
``.pdf`` images, ...) and are the platform's supported retrieval path.

See ``shared/managed-agents-environments.md`` -> "Session outputs":
    client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
    client.beta.files.download(file_id)
"""
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# The files.* resource auto-adds only the files-api beta header, so the
# managed-agents beta must be passed explicitly for the scope_id filter.
_MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


def _iter_files(list_result):
    """Return the file objects from a files.list() result.

    The SDK returns a page object exposing ``.data``; older/newer shapes may be
    directly iterable. Support both so we don't depend on one SDK minor.
    """
    data = getattr(list_result, "data", None)
    if data is not None:
        return list(data)
    return list(list_result)


def _list_session_files(client, session_id, retries, retry_delay):
    """List session-output files, retrying briefly to cover indexing lag.

    There is a ~1-3s lag between ``session.status_idle`` and outputs appearing
    in ``files.list``; retry a couple of times when the first list is empty.
    """
    files: list = []
    for attempt in range(retries + 1):
        result = client.beta.files.list(
            scope_id=session_id,
            betas=[_MANAGED_AGENTS_BETA],
        )
        files = _iter_files(result)
        if files or attempt == retries:
            return files
        time.sleep(retry_delay)
    return files


def _safe_relpath(filename: str):
    """Return a path-traversal-safe relative path, or None if it escapes."""
    filename = (filename or "").lstrip("/")
    if not filename:
        return None
    # Reject any component that would climb out of output_dir.
    parts = [p for p in Path(filename).parts if p not in ("", ".")]
    if not parts or ".." in parts or os.path.isabs(filename):
        return None
    return Path(*parts)


def _save_download(download, dest: Path) -> None:
    """Write a downloaded file object to dest, handling text/binary uniformly."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # The SDK's download response exposes write_to_file(); prefer it so binary
    # content is handled correctly.
    write_to_file = getattr(download, "write_to_file", None)
    if callable(write_to_file):
        write_to_file(str(dest))
        return
    # Fallbacks for simpler/mocked objects.
    read = getattr(download, "read", None)
    content = read() if callable(read) else download
    if isinstance(content, str):
        dest.write_text(content, encoding="utf-8")
    else:
        dest.write_bytes(content)


def download_session_outputs(
    client,
    session_id: str,
    output_dir,
    retries: int = 3,
    retry_delay: float = 1.5,
) -> int:
    """Download files the agent wrote to /mnt/session/outputs/ during a session.

    Lists session-scoped output files via the Files API and downloads each one
    into ``output_dir`` (created if missing), preserving relative subdirectory
    structure. Returns the number of files saved.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _list_session_files(client, session_id, retries, retry_delay)
    count = 0
    for f in files:
        filename = getattr(f, "filename", None) or getattr(f, "id", "")
        rel = _safe_relpath(str(filename))
        if rel is None:
            logger.warning("Skipping file with unsafe name %r", filename)
            continue
        dest = output_dir / rel
        download = client.beta.files.download(f.id)
        _save_download(download, dest)
        logger.info("Downloaded %s -> %s", filename, dest)
        count += 1

    if count:
        logger.info("Downloaded %d file(s) to %s", count, output_dir)
    else:
        logger.debug("No session output files found for session %s", session_id)
    return count
