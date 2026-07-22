"""Outcome-oriented sessions: state a goal + rubric, let the platform iterate.

An *outcome* turns a session from a conversation into graded work. Instead of a
one-shot prompt, you send a ``user.define_outcome`` event with a description and
a rubric; the platform runs an iterate -> grade -> revise loop (an independent
grader scores each iteration against the rubric) until it is satisfied, hits
``max_iterations``, or fails. This replaces hand-rolled "fix until tests pass"
loops in a pipeline.

See ``shared/managed-agents-outcomes.md``.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Terminal grader results — the outcome loop has stopped on these.
TERMINAL_RESULTS = frozenset({"satisfied", "failed", "max_iterations_reached", "interrupted"})


def define_outcome(
    client,
    session_id: str,
    description: str,
    rubric: str,
    max_iterations: int = 3,
) -> None:
    """Send a ``user.define_outcome`` event to kick off a graded outcome.

    ``description`` is the task the agent works toward (no separate user.message
    is needed). ``rubric`` is markdown with explicit, independently gradeable
    criteria.
    """
    client.beta.sessions.events.send(
        session_id,
        events=[
            {
                "type": "user.define_outcome",
                "description": description,
                "rubric": {"type": "text", "content": rubric},
                "max_iterations": max_iterations,
            }
        ],
    )
    logger.info("Defined outcome for session %s (max_iterations=%d)", session_id, max_iterations)


class OutcomeTracker:
    """Collects outcome-grader results from a session event stream.

    Use as the ``on_event`` callback to ``stream_message``; afterwards read
    ``last_result`` / ``satisfied`` to see how the graded run ended.
    """

    def __init__(self) -> None:
        self.results: list[str] = []

    def __call__(self, event) -> None:
        if getattr(event, "type", None) == "span.outcome_evaluation_end":
            result = getattr(event, "result", None)
            if result is not None:
                self.results.append(result)
                logger.info(
                    "Outcome iteration %s -> %s",
                    getattr(event, "iteration", "?"),
                    result,
                )

    @property
    def last_result(self) -> Optional[str]:
        return self.results[-1] if self.results else None

    @property
    def satisfied(self) -> bool:
        return self.last_result == "satisfied"
