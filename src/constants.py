"""Shared constants for the managed-agents integration.

Centralising the beta identifier keeps every call that must pass it (session
outputs, and any future managed-agents endpoints that take a managed-agents
parameter) in sync from one place.
"""

# The files.* resource auto-adds only the files-api beta header, so the
# managed-agents beta must be passed explicitly for the scope_id filter.
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"
