from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class GlobalConfig:
    api_key: str
    default_model: str
    environments_config: str
    agents_config: str


@dataclass
class EnvironmentConfig:
    name: str
    description: str = ""
    config: dict = field(default_factory=dict)


@dataclass
class AgentConfig:
    name: str
    system: str
    model: Optional[str] = None
    description: str = ""
    tools: list = field(default_factory=list)
    mcp_servers: list = field(default_factory=list)
    skills: list = field(default_factory=list)


def load_global_config(path: str) -> GlobalConfig:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Global config file not found: {path}")
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse global config '{path}': {exc}")
    if not isinstance(data, dict):
        raise ValueError(f"Global config '{path}' must be a mapping at the top level")
    if not data.get("default_model"):
        raise ValueError("global config missing required field: default_model")
    if not data.get("environments_config"):
        raise ValueError("global config missing required field: environments_config")
    if not data.get("agents_config"):
        raise ValueError("global config missing required field: agents_config")
    return GlobalConfig(
        api_key=data.get("anthropic_api_key", ""),
        default_model=data["default_model"],
        environments_config=data["environments_config"],
        agents_config=data["agents_config"],
    )


def load_environments_config(path: str) -> list[EnvironmentConfig]:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Environments config file not found: {path}")
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse environments config '{path}': {exc}")
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid environments config structure in '{path}': expected a mapping at top level"
        )
    envs = data.get("environments", [])
    result = []
    for idx, item in enumerate(envs):
        if not item.get("name"):
            raise ValueError(f"environment entry {idx} missing required field: name")
        result.append(EnvironmentConfig(
            name=item["name"],
            description=item.get("description", ""),
            config=item.get("config", {}),
        ))
    return result


def load_agents_config(path: str) -> list[AgentConfig]:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Agents config file not found: {path}")
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse agents config '{path}': {exc}")
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid agents config structure in '{path}': expected a mapping at top level"
        )
    agents = data.get("agents", [])
    result = []
    for idx, item in enumerate(agents):
        if not item.get("name"):
            raise ValueError(f"agent entry {idx} missing required field: name")
        if not item.get("system"):
            raise ValueError(f"agent '{item.get('name')}' missing required field: system")
        result.append(AgentConfig(
            name=item["name"],
            model=item.get("model"),
            description=item.get("description", ""),
            system=item["system"],
            tools=item.get("tools", []),
            mcp_servers=item.get("mcp_servers", []),
            skills=item.get("skills", []),
        ))
    return result
