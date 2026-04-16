"""Unit tests for src/environment.py"""
import pytest
from unittest.mock import MagicMock

from src.environment import create_environment, Environment
from src.config_loader import EnvironmentConfig


def _make_config(name="test-env", description="", config=None):
    return EnvironmentConfig(name=name, description=description, config=config or {})


def _make_api_env(name, id_="env-id-1"):
    e = MagicMock()
    e.name = name
    e.id = id_
    return e


def _make_paginated_client(pages):
    client = MagicMock()
    list_result = MagicMock()
    list_result.iter_pages.return_value = iter(pages)
    client.beta.environments.list.return_value = list_result
    return client


# ---------------------------------------------------------------------------
# create_environment — new resource
# ---------------------------------------------------------------------------

class TestCreateEnvironmentNew:
    def test_creates_via_api_and_returns_environment(self):
        api_obj = _make_api_env("test-env")
        client = MagicMock()
        client.beta.environments.create.return_value = api_obj

        config = _make_config(name="test-env", config={"networking": {"type": "unrestricted"}})
        env = create_environment(client, config)

        assert isinstance(env, Environment)
        assert env.id == api_obj.id
        client.beta.environments.create.assert_called_once_with(
            name="test-env",
            config={"type": "cloud", "networking": {"type": "unrestricted"}},
        )

    def test_default_config_gets_type_cloud_prepended(self):
        client = MagicMock()
        client.beta.environments.create.return_value = _make_api_env("e")

        create_environment(client, _make_config(config={}))

        assert client.beta.environments.create.call_args.kwargs["config"] == {"type": "cloud"}


# ---------------------------------------------------------------------------
# create_environment — existing resource (pagination)
# ---------------------------------------------------------------------------

class TestCreateEnvironmentExisting:
    def test_finds_environment_across_pages(self):
        page1 = MagicMock()
        page1.data = [_make_api_env("other-env", "id-other")]
        page2 = MagicMock()
        target = _make_api_env("wanted-env", "id-wanted")
        page2.data = [target]

        client = _make_paginated_client([page1, page2])
        config = _make_config(name="wanted-env")

        env = create_environment(client, config, existing=True)

        assert env.id == "id-wanted"

    def test_raises_lookup_error_when_not_found(self):
        page = MagicMock()
        page.data = [_make_api_env("other-env")]
        client = _make_paginated_client([page])
        config = _make_config(name="missing-env")

        with pytest.raises(LookupError, match="missing-env"):
            create_environment(client, config, existing=True)

    def test_raises_lookup_error_when_pages_empty(self):
        client = _make_paginated_client([])
        config = _make_config(name="any-env")

        with pytest.raises(LookupError, match="any-env"):
            create_environment(client, config, existing=True)
