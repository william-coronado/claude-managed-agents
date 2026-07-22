"""Unit tests for src/retry.py"""
import pytest
from unittest.mock import patch

from src.retry import with_retries


class _HTTPish(Exception):
    def __init__(self, status_code, msg="boom"):
        super().__init__(msg)
        self.status_code = status_code


class TestWithRetries:
    def test_returns_result_on_first_success(self):
        assert with_retries(lambda: 42) == 42

    def test_retries_transient_then_succeeds(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise _HTTPish(529, "overloaded")
            return "ok"

        with patch("src.retry.time.sleep") as mock_sleep:
            assert with_retries(flaky, base_delay=0.01) == "ok"

        assert calls["n"] == 3
        assert mock_sleep.call_count == 2

    def test_non_transient_raises_immediately(self):
        calls = {"n": 0}

        def bad():
            calls["n"] += 1
            raise _HTTPish(400, "bad request")

        with pytest.raises(_HTTPish):
            with_retries(bad)
        assert calls["n"] == 1  # not retried

    def test_gives_up_after_attempts(self):
        def always_overloaded():
            raise _HTTPish(500, "server error")

        with patch("src.retry.time.sleep"):
            with pytest.raises(_HTTPish):
                with_retries(always_overloaded, attempts=3)

    def test_transient_by_message_when_no_status(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("connection reset")
            return "recovered"

        with patch("src.retry.time.sleep"):
            assert with_retries(flaky) == "recovered"
        assert calls["n"] == 2
