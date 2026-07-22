"""Post-session output download.

Historically this module replayed session events and re-derived file content
from ``write`` tool calls, because the platform did not expose agent-created
files after a session. The platform now captures anything written under
``/mnt/session/outputs/`` and serves it through the Files API, so the canonical
implementation lives in ``src.outputs``. This module re-exports it for
backward compatibility.
"""
from src.outputs import download_session_outputs

__all__ = ["download_session_outputs"]
