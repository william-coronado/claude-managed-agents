"""Unit tests for src/agent.py"""
import pytest
from unittest.mock import MagicMock, call

from src.agent import create_agent, Agent
from src.config_loader import AgentConfig


def _make_config(name="test-agent", system="You are helpful.", model=None):
    return AgentConfig(name=name, system=system, model=model)


def _make_api_agent(name, id_="agent-id-1"):
    a = MagicMock()
    a.name = name
    a.id = id_
    a.version = 1
    return a


def _make_paginated_client(pages):
    """Build a client whose agents.list().iter_pages() yields the given pages."""
    client = MagicMock()
    list_result = MagicMock()
    list_result.iter_pages.return_value = iter(pages)
    client.beta.agents.list.return_value = list_result
    return client


# ---------------------------------------------------------------------------
# create_agent — new resource
# ---------------------------------------------------------------------------

class TestCreateAgentNew:
    def test_creates_via_api_and_returns_agent(self):
        api_obj = _make_api_agent("test-agent")
        client = MagicMock()
        client.beta.agents.create.return_value = api_obj

        config = _make_config(name="test-agent", system="Be helpful.", model="claude-test")
        agent = create_agent(client, config, default_model="default-model")

        assert isinstance(agent, Agent)
        assert agent.id == api_obj.id
        client.beta.agents.create.assert_called_once_with(
            name="test-agent",
            model="claude-test",
            system="Be helpful.",
            tools=[],
            mcp_servers=[],
            skills=[],
            description=None,
        )

    def test_falls_back_to_default_model_when_config_model_is_none(self):
        client = MagicMock()
        client.beta.agents.create.return_value = _make_api_agent("agent")

        create_agent(client, _make_config(model=None), default_model="fallback-model")

        assert client.beta.agents.create.call_args.kwargs["model"] == "fallback-model"


# ---------------------------------------------------------------------------
# create_agent — existing resource (pagination)
# ---------------------------------------------------------------------------

class TestCreateAgentExisting:
    def test_finds_agent_across_pages(self):
        page1 = MagicMock()
        page1.data = [_make_api_agent("other-agent", "id-other")]
        page2 = MagicMock()
        target = _make_api_agent("wanted-agent", "id-wanted")
        page2.data = [target]

        client = _make_paginated_client([page1, page2])
        config = _make_config(name="wanted-agent")

        agent = create_agent(client, config, default_model="m", existing=True)

        assert agent.id == "id-wanted"

    def test_raises_lookup_error_when_not_found(self):
        page = MagicMock()
        page.data = [_make_api_agent("other-agent")]
        client = _make_paginated_client([page])
        config = _make_config(name="missing-agent")

        with pytest.raises(LookupError, match="missing-agent"):
            create_agent(client, config, default_model="m", existing=True)

    def test_raises_lookup_error_when_pages_empty(self):
        client = _make_paginated_client([])
        config = _make_config(name="any-agent")

        with pytest.raises(LookupError, match="any-agent"):
            create_agent(client, config, default_model="m", existing=True)
