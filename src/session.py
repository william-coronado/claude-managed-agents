from typing import Optional


class Session:
    def __init__(self, api_obj):
        self._obj = api_obj

    @property
    def id(self):
        return self._obj.id


def create_session(client, agent_id: str, environment_id: str, title: Optional[str] = None) -> Session:
    kwargs = {"agent": agent_id, "environment_id": environment_id}
    if title:
        # Strip Unicode control/format characters (newlines, tabs, etc.)
        kwargs["title"] = "".join(c for c in title if c.isprintable())
    obj = client.beta.sessions.create(**kwargs)
    return Session(obj)
