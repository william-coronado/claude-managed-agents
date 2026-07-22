from typing import Optional


class Session:
    def __init__(self, api_obj):
        self._obj = api_obj

    @property
    def id(self):
        return self._obj.id


def create_session(
    client,
    agent_id: str,
    environment_id: str,
    title: Optional[str] = None,
    resources: Optional[list] = None,
    vault_ids: Optional[list] = None,
    agent_version: Optional[int] = None,
) -> Session:
    """Create a session referencing a pre-created agent.

    ``agent_version`` pins the session to a specific agent version for
    reproducibility (defaults to latest via the string-ID shorthand).
    ``resources`` attaches files / GitHub repos / memory stores; ``vault_ids``
    supplies MCP and environment-variable credentials.
    """
    agent = agent_id if agent_version is None else {"type": "agent", "id": agent_id, "version": agent_version}
    kwargs = {"agent": agent, "environment_id": environment_id}
    if title:
        # Strip Unicode control/format characters (newlines, tabs, etc.)
        clean_title = "".join(c for c in title if c.isprintable()).strip()
        if clean_title:
            kwargs["title"] = clean_title
    if resources:
        kwargs["resources"] = resources
    if vault_ids:
        kwargs["vault_ids"] = vault_ids
    obj = client.beta.sessions.create(**kwargs)
    return Session(obj)
