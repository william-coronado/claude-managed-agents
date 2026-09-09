"""Download files an agent wrote during a session, using the Files API.

The managed-agents platform captures anything the agent writes under
``/mnt/session/outputs/`` and exposes it through the Files API scoped to the
session, and this module downloads via that path so binary artifacts
(``.xlsx``, ``.pptx``, ``.pdf``, images, ...) are supported.

**The Files API's ``filename`` is always a bare basename - never a path.**
Confirmed against a live session: writing ``/mnt/session/outputs/todo/main.py``
and ``/mnt/session/outputs/utils/main.py`` in the same session, then calling
``files.list(scope_id=session_id, ...)``, returns two entries both named
``"main.py"`` with no other field to tell them apart. Listing basenames alone
therefore cannot preserve subdirectory structure or disambiguate two files
that happen to share a name in different directories - doing so would risk
silently writing one file's bytes to another file's destination.

To recover the real path, this module replays the session's ``agent.tool_use``
'write' events (which do carry the full ``file_path``) and correlates each one
to a Files API entry by ``(basename, byte size)``, using a match only when
it's unambiguous. Output files not produced by the 'write' tool (e.g. written
via ``bash`` or code execution) have no event to recover a path from, so they
are saved flat under ``output_dir`` by basename, same as before.

See ``shared/managed-agents-environments.md`` -> "Session outputs":
    client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
    client.beta.files.download(file_id)
"""
import logging
import time
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Optional

from src.constants import MANAGED_AGENTS_BETA

logger = logging.getLogger(__name__)

_OUTPUTS_PREFIX = "/mnt/session/outputs/"


def _iter_files(list_result):
    """Return *all* file objects from a files.list() result, across pages.

    The SDK returns a paginated page whose ``.data`` is only the current page;
    ``.iter_pages()`` walks the rest. Use it (the same pattern as agent.py /
    environment.py) so a session that writes more than one page of outputs
    doesn't silently drop the remaining deliverables. Falls back to ``.data``
    or direct iteration for simpler/mocked shapes.
    """
    iter_pages = getattr(list_result, "iter_pages", None)
    if callable(iter_pages):
        files: list = []
        for page in iter_pages():
            files.extend(getattr(page, "data", None) or [])
        return files
    data = getattr(list_result, "data", None)
    if data is not None:
        return list(data)
    return list(list_result)


def _list_session_files(
    client, session_id, retries, retry_delay, expected_by_basename: Optional[Counter] = None,
):
    """List session-output files, retrying briefly to cover indexing lag.

    There is a ~1-3s lag between ``session.status_idle`` and outputs appearing
    in ``files.list``; retry a couple of times when the first list is empty.

    When ``expected_by_basename`` is given, retries until every expected
    basename has at least that many candidates present, not just until the
    list is non-empty - ``scope_id`` can include files unrelated to a specific
    caller's expectations (e.g. mounted input resources), which would
    otherwise let the loop stop before the actually-needed files have landed.
    """
    files: list = []
    for attempt in range(retries + 1):
        result = client.beta.files.list(
            scope_id=session_id,
            betas=[MANAGED_AGENTS_BETA],
        )
        files = _iter_files(result)
        if expected_by_basename is not None:
            counts = Counter(getattr(f, "filename", None) for f in files)
            satisfied = all(counts.get(name, 0) >= n for name, n in expected_by_basename.items())
        else:
            satisfied = bool(files)
        if satisfied or attempt == retries:
            return files
        time.sleep(retry_delay)
    return files


def _safe_relpath(filename: str):
    """Return a path-traversal-safe relative path, or None if it escapes.

    Intentionally strict and POSIX-only: rejects backslashes (Windows/UNC
    separators), drive/anchor components (``C:foo``), leading separators, and
    any ``..`` component, so behaviour is consistent regardless of host OS.
    """
    filename = (filename or "").strip()
    if not filename:
        return None
    # Windows/UNC separators or mixed-separator paths are never valid here.
    if "\\" in filename:
        return None
    # Parse as POSIX only, so a stray host-specific rule can't change semantics.
    posix = PurePosixPath(filename)
    if posix.is_absolute():  # leading "/" — reject rather than silently relativize
        return None
    parts = [p for p in posix.parts if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    # Reject drive/anchor components (e.g. "C:foo", "C:/bar").
    if ":" in parts[0]:
        return None
    return Path(*parts)


def _replay_write_paths(client, session_id) -> list[tuple[str, str]]:
    """Return (relative path, logged content) for every 'write' tool call
    that targeted /mnt/session/outputs/ in this session.

    This is the only source of a file's real directory structure - see the
    module docstring for why the Files API's basename-only listing can't
    provide it.
    """
    calls: list[tuple[str, str]] = []
    for event in client.beta.sessions.events.list(session_id):
        if event.type != "agent.tool_use" or getattr(event, "name", None) != "write":
            continue
        tool_input = getattr(event, "input", {}) or {}
        file_path = str(tool_input.get("file_path", ""))
        content = str(tool_input.get("content", ""))
        if not file_path.startswith(_OUTPUTS_PREFIX):
            continue
        rel_path = file_path[len(_OUTPUTS_PREFIX):]
        if not rel_path:
            continue
        calls.append((rel_path, content))
    return calls


def _match_candidate(candidates: list, byte_length: int, rel_path: str, basename: str):
    """Pick the single unambiguous Files API candidate for a write call, or None.

    A match is used only when it can't be confused with another candidate of
    the same basename: exactly one candidate has the expected byte size, or
    exactly one candidate of that basename exists at all. Ties (e.g. two
    same-named files that also happen to have the same byte length) are never
    guessed at - picking wrong would silently write one file's bytes to
    another file's destination, which is worse than falling back.
    """
    exact_matches = [c for c in candidates if getattr(c, "size_bytes", None) == byte_length]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if not exact_matches and len(candidates) == 1:
        return candidates[0]
    if len(exact_matches) > 1 or len(candidates) > 1:
        logger.warning(
            "Ambiguous Files API match for %s (%d candidate(s) named %r); "
            "falling back to logged tool content rather than guessing",
            rel_path, len(candidates), basename,
        )
    return None


def list_session_output_files(
    client, session_id, retries: int = 3, retry_delay: float = 1.5
) -> list[tuple[str, str]]:
    """Return (file_id, filename) pairs for files an agent wrote during a session.

    Prefers the real relative path recovered from 'write' tool call replay
    (see module docstring); falls back to a flat basename for files produced
    another way (bash, code execution). Only returns entries that resolved to
    an actual Files API file_id - an ambiguous or unmatched write call has no
    file_id to mount as a resource, so it's omitted here (unlike
    ``download_session_outputs``, which can still write out logged content).
    """
    write_calls = _replay_write_paths(client, session_id)
    expected_by_basename = Counter(rel.rsplit("/", 1)[-1] for rel, _ in write_calls) or None
    files = _list_session_files(client, session_id, retries, retry_delay, expected_by_basename)

    files_by_basename: dict[str, list] = {}
    for f in files:
        filename = getattr(f, "filename", None) or getattr(f, "id", "")
        files_by_basename.setdefault(str(filename), []).append(f)

    result: list[tuple[str, str]] = []
    seen_paths: set[str] = set()
    claimed_ids: set = set()

    def _emit(file_id: str, rel: Path) -> None:
        # Two different files resolving to the same relative path would mount
        # at the same path in a follow-up session, silently clobbering one -
        # keep only the first and warn, rather than emit both.
        rel_str = str(rel)
        if rel_str in seen_paths:
            logger.warning("Skipping duplicate resource path %r (file_id=%s)", rel_str, file_id)
            return
        seen_paths.add(rel_str)
        result.append((file_id, rel_str))

    for rel_path, content in write_calls:
        safe_rel = _safe_relpath(rel_path)
        if safe_rel is None:
            continue
        basename = safe_rel.name
        candidates = files_by_basename.get(basename, [])
        match = _match_candidate(candidates, len(content.encode("utf-8")), rel_path, basename)
        if match is not None:
            candidates.remove(match)
            claimed_ids.add(match.id)
            _emit(match.id, safe_rel)

    # Files not produced by a 'write' tool call (e.g. bash/code exec) have no
    # recovered path - fall back to a flat basename, same as before. A
    # basename that *was* targeted by a write call is skipped even when
    # unclaimed (an ambiguous tie): it has no logged-content fallback to lean
    # on here, and emitting it flat would silently guess which candidate it
    # is - exactly what the ambiguity guard exists to prevent.
    write_basenames = set(expected_by_basename or ())
    for f in files:
        if f.id in claimed_ids:
            continue
        filename = getattr(f, "filename", None) or getattr(f, "id", "")
        if str(filename) in write_basenames:
            continue
        safe_rel = _safe_relpath(str(filename))
        if safe_rel is None:
            continue
        _emit(f.id, safe_rel)

    return result


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
    into ``output_dir`` (created if missing). Files produced by the 'write'
    tool are placed at their real relative path, recovered by replaying
    session events (see module docstring for why the Files API's basename-only
    listing can't do this alone); a write call that can't be unambiguously
    correlated to a Files API entry - or an entry the Files API failed to
    serve - falls back to that event's own logged content so it's never
    silently dropped or swapped with another file. Files not produced by the
    'write' tool (bash, code execution) are saved flat by basename, as before.

    Returns the number of files saved.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_calls = _replay_write_paths(client, session_id)
    expected_by_basename = Counter(rel.rsplit("/", 1)[-1] for rel, _ in write_calls) or None

    try:
        files = _list_session_files(client, session_id, retries, retry_delay, expected_by_basename)
    except Exception as exc:
        logger.warning(
            "Files API listing failed for session %s (%s); falling back to logged tool content "
            "for any 'write' tool calls found",
            session_id, exc,
        )
        files = []

    files_by_basename: dict[str, list] = {}
    for f in files:
        filename = getattr(f, "filename", None) or getattr(f, "id", "")
        files_by_basename.setdefault(str(filename), []).append(f)

    count = 0
    claimed_ids: set = set()
    for rel_path, content in write_calls:
        safe_rel = _safe_relpath(rel_path)
        if safe_rel is None:
            logger.warning("Skipping write event with unsafe path %r", rel_path)
            continue
        basename = safe_rel.name
        dest = output_dir / safe_rel

        candidates = files_by_basename.get(basename, [])
        match = _match_candidate(candidates, len(content.encode("utf-8")), rel_path, basename)

        if match is not None:
            candidates.remove(match)
            claimed_ids.add(match.id)
            try:
                download = client.beta.files.download(match.id)
                _save_download(download, dest)
                logger.info("Downloaded %s -> %s (files API id=%s)", rel_path, dest, match.id)
            except Exception as exc:
                logger.warning(
                    "Files API download failed for %s (id=%s): %s; falling back to logged tool content",
                    rel_path, match.id, exc,
                )
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            logger.warning("No Files API match for %s; wrote logged tool content instead", rel_path)

        count += 1

    # Files not produced by a 'write' tool call (e.g. bash/code exec) have no
    # recovered path - save flat by basename, same as before this change.
    # A basename that *was* targeted by a write call is skipped here even when
    # unclaimed (an ambiguous tie) - it already got its logged-content
    # fallback above, and downloading it flat here would silently guess which
    # candidate it is, exactly what the ambiguity guard exists to prevent.
    write_basenames = set(expected_by_basename or ())
    for f in files:
        if f.id in claimed_ids:
            continue
        filename = getattr(f, "filename", None) or getattr(f, "id", "")
        if str(filename) in write_basenames:
            continue
        safe_rel = _safe_relpath(str(filename))
        if safe_rel is None:
            logger.warning("Skipping file with unsafe name %r", filename)
            continue
        dest = output_dir / safe_rel
        download = client.beta.files.download(f.id)
        _save_download(download, dest)
        logger.info("Downloaded %s -> %s", filename, dest)
        count += 1

    if count:
        logger.info("Downloaded %d file(s) to %s", count, output_dir)
    else:
        logger.debug("No session output files found for session %s", session_id)
    return count
