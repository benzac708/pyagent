"""Tests for provider failover chain."""

from unittest.mock import MagicMock, patch

from agent.providers import ProviderChain
from tests.helpers import make_response


def test_single_provider_success():
    with patch("agent.providers.create_client") as mock_create:
        client = MagicMock()
        mock_create.return_value = client
        client.chat.completions.create.return_value = make_response(content="hi", total_tokens=5)

        chain = ProviderChain([{"base_url": "u", "api_key": "k", "model": "m", "name": "primary"}])
        resp, name = chain.chat([{"role": "user", "content": "hi"}])

        assert name == "primary"
        assert resp.choices[0].message.content == "hi"
        assert chain.last_provider == "primary"


def test_fallback_on_primary_failure():
    with patch("agent.providers.create_client") as mock_create:
        failing = MagicMock()
        failing.chat.completions.create.side_effect = RuntimeError("boom")
        ok = MagicMock()
        ok.chat.completions.create.return_value = make_response(content="ok", total_tokens=3)
        mock_create.side_effect = [failing, ok]

        chain = ProviderChain([
            {"base_url": "u1", "api_key": "k1", "model": "m1", "name": "primary"},
            {"base_url": "u2", "api_key": "k2", "model": "m2", "name": "fallback"},
        ])
        resp, name = chain.chat([{"role": "user", "content": "hi"}])

        assert name == "fallback"
        assert resp.choices[0].message.content == "ok"


def test_all_providers_fail_raises():
    with patch("agent.providers.create_client") as mock_create:
        c1 = MagicMock()
        c1.chat.completions.create.side_effect = RuntimeError("e1")
        c2 = MagicMock()
        c2.chat.completions.create.side_effect = RuntimeError("e2")
        mock_create.side_effect = [c1, c2]

        chain = ProviderChain([
            {"base_url": "u1", "api_key": "k1", "model": "m1", "name": "p1"},
            {"base_url": "u2", "api_key": "k2", "model": "m2", "name": "p2"},
        ])
        try:
            chain.chat([{"role": "user", "content": "hi"}])
            raised = False
        except RuntimeError as e:
            raised = True
            assert str(e) == "e2"
        assert raised


def test_tools_passed_to_client():
    with patch("agent.providers.create_client") as mock_create:
        client = MagicMock()
        mock_create.return_value = client
        client.chat.completions.create.return_value = make_response(content="hi")

        chain = ProviderChain([{"base_url": "u", "api_key": "k", "model": "m", "name": "p"}])
        tools = [{"type": "function", "function": {"name": "t", "parameters": {}}}]
        chain.chat([{"role": "user", "content": "hi"}], tools=tools)

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"] == tools
