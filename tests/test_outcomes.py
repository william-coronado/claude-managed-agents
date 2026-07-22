"""Unit tests for src/outcomes.py"""
from unittest.mock import MagicMock

from src.outcomes import define_outcome, OutcomeTracker


def _make_event(type_, **kwargs):
    ev = MagicMock()
    ev.type = type_
    for k, v in kwargs.items():
        setattr(ev, k, v)
    return ev


class TestDefineOutcome:
    def test_sends_define_outcome_event(self):
        client = MagicMock()
        define_outcome(client, "sess-1", "Build a DCF model", "- has revenue\n- has WACC", max_iterations=5)

        client.beta.sessions.events.send.assert_called_once_with(
            "sess-1",
            events=[{
                "type": "user.define_outcome",
                "description": "Build a DCF model",
                "rubric": {"type": "text", "content": "- has revenue\n- has WACC"},
                "max_iterations": 5,
            }],
        )

    def test_default_max_iterations(self):
        client = MagicMock()
        define_outcome(client, "sess-1", "task", "rubric")
        sent = client.beta.sessions.events.send.call_args.kwargs["events"][0]
        assert sent["max_iterations"] == 3


class TestOutcomeTracker:
    def test_collects_results_in_order(self):
        tracker = OutcomeTracker()
        tracker(_make_event("span.outcome_evaluation_end", result="needs_revision", iteration=0))
        tracker(_make_event("agent.message"))  # ignored
        tracker(_make_event("span.outcome_evaluation_end", result="satisfied", iteration=1))

        assert tracker.results == ["needs_revision", "satisfied"]
        assert tracker.last_result == "satisfied"
        assert tracker.satisfied is True

    def test_not_satisfied_when_last_result_is_failure(self):
        tracker = OutcomeTracker()
        tracker(_make_event("span.outcome_evaluation_end", result="failed", iteration=0))
        assert tracker.satisfied is False
        assert tracker.last_result == "failed"

    def test_empty_tracker(self):
        tracker = OutcomeTracker()
        assert tracker.last_result is None
        assert tracker.satisfied is False
