import logging
from pathlib import Path
from typing import Optional

from anthropic import Anthropic

from src.agent import Agent
from src.downloads import download_session_outputs
from src.environment import Environment
from src.session import create_session
from src.messaging import stream_message

logger = logging.getLogger(__name__)


def run_agent_step(
    client: Anthropic,
    agents: dict[str, Agent],
    envs: dict[str, Environment],
    agent_name: str,
    env_name: str,
    prompt: str,
    output_dir: Optional[Path] = None,
) -> str:
    logger.info("\n%s\n[%s]\n%s", "=" * 60, agent_name.upper(), "=" * 60)
    if agent_name not in agents:
        raise KeyError(f"agent '{agent_name}' not found in loaded agents")
    if env_name not in envs:
        raise KeyError(f"environment '{env_name}' not found in loaded environments")
    agent = agents[agent_name]
    env = envs[env_name]
    session = create_session(client, agent.id, env.id, title=prompt[:80])
    result = stream_message(client, session.id, prompt)
    if output_dir is not None:
        download_session_outputs(client, session.id, output_dir)
    return result
