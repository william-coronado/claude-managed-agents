import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from anthropic import Anthropic

from src.agent import Agent
from src.environment import Environment
from src.session import create_session
from src.messaging import stream_message
from src.outputs import download_session_outputs, list_session_output_files
from src.retry import with_retries

logger = logging.getLogger(__name__)

UPLOADS_MOUNT_DIR = "/mnt/session/uploads"


@dataclass
class StepResult:
    """Result of one pipeline step: its text reply plus its output files.

    ``resources`` is ready to pass as the next step's ``resources=`` argument,
    mounting each file this step wrote to /mnt/session/outputs/ into the next
    step's (otherwise separate) session container.
    """
    text: str
    resources: list[dict[str, Any]] = field(default_factory=list)


def run_agent_step(
    client: Anthropic,
    agents: dict[str, Agent],
    envs: dict[str, Environment],
    agent_name: str,
    env_name: str,
    prompt: str,
    output_dir: Optional[Path] = None,
    resources: Optional[list[dict[str, Any]]] = None,
) -> StepResult:
    """Run one agent as its own session and return its text output plus its output files.

    When ``output_dir`` is set, files the agent wrote to /mnt/session/outputs/
    are downloaded (via the Files API) into ``output_dir/<agent_name>`` after
    the turn completes. ``resources`` (e.g. a prior step's ``StepResult.resources``)
    is mounted into this step's session at creation, since each step otherwise
    gets its own isolated container.
    """
    logger.info("\n%s\n[%s]\n%s", "=" * 60, agent_name.upper(), "=" * 60)
    if agent_name not in agents:
        raise KeyError(f"agent '{agent_name}' not found in loaded agents")
    if env_name not in envs:
        raise KeyError(f"environment '{env_name}' not found in loaded environments")
    agent = agents[agent_name]
    env = envs[env_name]
    session = with_retries(
        lambda: create_session(
            client, agent.id, env.id, title=prompt[:80],
            **({"resources": resources} if resources is not None else {}),
        ),
        description="session create",
    )
    output = stream_message(client, session.id, prompt)
    if output_dir is not None:
        download_session_outputs(client, session.id, output_dir / agent_name)
    next_resources = [
        {"type": "file", "file_id": file_id, "mount_path": f"/{filename}"}
        for file_id, filename in list_session_output_files(client, session.id)
    ]
    return StepResult(text=output, resources=next_resources)
