from src.config_loader import load_environments_config, load_agents_config
from src.environment import create_environment
from src.agent import create_agent
from src.exceptions import ResourceNotFoundError


def load_resources(client, default_model: str, env_config_path: str, agent_config_path: str, existing: bool = False):
    """Create (or look up) all environments and agents defined in the given config files.

    Returns a tuple of (envs, agents) dicts keyed by name.
    If any resources are missing in existing mode, collects all missing names and
    raises SystemExit in one shot so the user can fix them all at once.
    """
    errors: list[str] = []

    envs: dict = {}
    for e in load_environments_config(env_config_path):
        try:
            envs[e.name] = create_environment(client, e, existing=existing)
        except ResourceNotFoundError as exc:
            errors.append(str(exc))

    agents: dict = {}
    for a in load_agents_config(agent_config_path):
        try:
            agents[a.name] = create_agent(client, a, default_model, existing=existing)
        except ResourceNotFoundError as exc:
            errors.append(str(exc))

    if errors:
        raise SystemExit("Error: " + "; ".join(errors))

    return envs, agents
