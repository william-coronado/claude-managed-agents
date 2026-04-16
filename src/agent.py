from src.config_loader import AgentConfig


class Agent:
    def __init__(self, api_obj):
        self._obj = api_obj

    @property
    def id(self):
        return self._obj.id

    @property
    def name(self):
        return self._obj.name

    @property
    def version(self):
        return self._obj.version


def create_agent(client, config: AgentConfig, default_model: str, existing: bool = False) -> Agent:
    if existing:
        for page in client.beta.agents.list().iter_pages():
            for agent in page.data:
                if agent.name == config.name:
                    return Agent(agent)
        raise LookupError(f"Existing agent '{config.name}' not found")
    model = config.model or default_model
    obj = client.beta.agents.create(
        name=config.name,
        model=model,
        system=config.system,
        tools=config.tools,
        mcp_servers=config.mcp_servers or [],
        skills=config.skills or [],
        description=config.description or None,
    )
    return Agent(obj)
