from src.config_loader import load_environments_config, load_agents_config
from src.environment import create_environment
from src.agent import create_agent
from src.exceptions import ResourceNotFoundError


def load_resources(client, cfg, env_config_path: str, agent_config_path: str, existing: bool = False):
    """Create (or look up) all environments and agents defined in the given config files.

    Returns a tuple of (envs, agents) dicts keyed by name.
    Raises SystemExit with a user-facing message if a resource is not found in existing mode.
    """
    try:
        envs = {
            e.name: create_environment(client, e, existing=existing)
            for e in load_environments_config(env_config_path)
        }
        agents = {
            a.name: create_agent(client, a, cfg.default_model, existing=existing)
            for a in load_agents_config(agent_config_path)
        }
    except ResourceNotFoundError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    return envs, agents
