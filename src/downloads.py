import logging
from pathlib import Path

from anthropic import Anthropic

logger = logging.getLogger(__name__)


def download_session_outputs(client: Anthropic, session_id: str, output_dir: Path) -> int:
    """Download all session-scoped files to output_dir. Returns count of files saved.

    Files created by the agent and registered to the session scope are listed via
    the Files API (scope_id=session_id). Non-downloadable files are skipped.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for file_meta in client.beta.files.list(scope_id=session_id):
        if file_meta.downloadable is False:
            logger.debug("Skipping non-downloadable file %s (%s)", file_meta.filename, file_meta.id)
            continue
        dest = output_dir / file_meta.filename
        client.beta.files.download(file_meta.id).write_to_file(dest)
        logger.info("Downloaded %s -> %s", file_meta.filename, dest)
        count += 1
    if count:
        logger.info("Downloaded %d file(s) to %s", count, output_dir)
    else:
        logger.debug("No downloadable output files found for session %s", session_id)
    return count
