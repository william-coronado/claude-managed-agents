"""Run a team of agents as one multiagent coordinator session.

A coordinator agent delegates to a roster of role agents. All agents share one
session container and filesystem, so a role that writes a file (the engineer)
and a role that must act on it (QA running the tests) see the *same* files —
unlike a chain of separate sessions, where each step gets a fresh container and
artifacts have to be pasted back in as text.

Combined with an outcome (a goal + a gradeable rubric), the coordinator plans,
delegates across subagent threads, and iterates until the rubric passes.

See ``shared/managed-agents-multiagent.md`` and ``shared/managed-agents-outcomes.md``.
"""
import logging
from pathlib import Path
from typing import Optional

from src.agent import Agent, create_agent
from src.config_loader import AgentConfig
from src.environment import Environment
from src.messaging import stream_session
from src.outcomes import OutcomeTracker, define_outcome
from src.outputs import download_session_outputs
from src.retry import with_retries
from src.session import create_session

logger = logging.getLogger(__name__)

_DEFAULT_TOOLS = [{"type": "agent_toolset_20260401"}]


def create_coordinator(
    client,
    name: str,
    system: str,
    members: list[Agent],
    default_model: str,
    model: Optional[str] = None,
    tools: Optional[list] = None,
    existing: bool = False,
) -> Agent:
    """Create (or look up) a coordinator whose multiagent roster is ``members``.

    The roster is resolved from the already-created role agents' IDs, so this
    must run *after* the role agents exist. In ``existing`` mode the coordinator
    is looked up by name and its stored roster is reused.
    """
    roster = [m.id for m in members]
    cfg = AgentConfig(
        name=name,
        system=system,
        model=model,
        tools=tools if tools is not None else list(_DEFAULT_TOOLS),
        multiagent={"type": "coordinator", "agents": roster},
    )
    return create_agent(client, cfg, default_model, existing=existing)


def run_outcome_session(
    client,
    coordinator: Agent,
    environment: Environment,
    description: str,
    rubric: str,
    output_dir: Optional[Path] = None,
    resources: Optional[list] = None,
    vault_ids: Optional[list] = None,
    max_iterations: int = 5,
    agent_version: Optional[int] = None,
) -> OutcomeTracker:
    """Run one coordinator session driven by a graded outcome.

    Creates the session, sends a ``user.define_outcome`` kickoff, streams until
    the outcome reaches a terminal grade, and (if ``output_dir`` is set)
    downloads the deliverables written to /mnt/session/outputs/. Returns the
    :class:`OutcomeTracker` so the caller can inspect the final grade.
    """
    session = with_retries(
        lambda: create_session(
            client,
            coordinator.id,
            environment.id,
            title=description[:80],
            resources=resources,
            vault_ids=vault_ids,
            agent_version=agent_version,
        ),
        description="session create",
    )
    logger.info("Coordinator session %s created", session.id)

    tracker = OutcomeTracker()
    stream_session(
        client,
        session.id,
        kickoff=lambda: define_outcome(client, session.id, description, rubric, max_iterations),
        on_event=tracker,
    )

    if output_dir is not None:
        download_session_outputs(client, session.id, output_dir)

    if tracker.satisfied:
        logger.info("Outcome satisfied")
    elif tracker.last_result is not None:
        logger.warning("Outcome did not pass — final grade: %s", tracker.last_result)
    else:
        logger.warning("Outcome ended without a grader result")
    return tracker
