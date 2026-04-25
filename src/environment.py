import logging

from src.config_loader import EnvironmentConfig
from src.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class Environment:
    def __init__(self, api_obj):
        self._obj = api_obj

    @property
    def id(self):
        return self._obj.id

    @property
    def name(self):
        return self._obj.name


def create_environment(client, config: EnvironmentConfig, existing: bool = False) -> Environment:
    if existing:
        for page in client.beta.environments.list().iter_pages():
            for env in page.data:
                if env.name == config.name:
                    return Environment(env)
        raise ResourceNotFoundError(f"Existing environment '{config.name}' not found")
    api_config = {"type": "cloud", **config.config}
    obj = client.beta.environments.create(
        name=config.name,
        config=api_config,
    )
    return Environment(obj)
