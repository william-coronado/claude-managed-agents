import logging

from src.config_loader import AgentConfig
from src.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, api_obj):
        self._obj = api_obj

    @property
    def id(self):
        return self._obj.id

    @property
    def name(self):
        return self._obj.name


def create_agent(client, config: AgentConfig, default_model: str, existing: bool = False) -> Agent:
    if existing:
        for page in client.beta.agents.list().iter_pages():
            for agent in page.data:
                if agent.name == config.name:
                    expected_model = config.model or default_model
                    actual_model = getattr(agent, "model", None)
                    if actual_model and actual_model != expected_model:
                        logger.warning(
                            "Reusing existing agent '%s' with model '%s'; config specifies '%s'.",
                            config.name, actual_model, expected_model,
                        )
                    return Agent(agent)
        raise ResourceNotFoundError(f"Existing agent '{config.name}' not found")
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
