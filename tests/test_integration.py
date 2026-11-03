"""Integration tests: real tools, provider failover through the loop, CLI."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from agent import db, loop
from agent.providers import ProviderChain
from tests.helpers import make_response, make_tool_call


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "t.db")
    monkeypatch.setattr("agent.config.DB_PATH", db_path)
    monkeypatch.setattr("agent.db.DB_PATH", db_path)
    db.init_db()
    yield db_path


def test_loop_with_real_read_file_tool(tmp_db, monkeypatch):
    """Agent loop invokes the real read_file tool and persists its result."""
    tc = make_tool_call("tc1", "read_file", '{"path": "fizzbuzz.js"}')
    responses = [
        make_response(content=None, tool_calls=[tc], total_tokens=5),
        make_response(content="summarized", total_tokens=3),
    ]
    it = iter(responses)

    def fake_chat(messages, tools=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    loop.run("read fizzbuzz.js")

    conn = sqlite3.connect(tmp_db)
    conv_id = conn.execute("SELECT conv_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    tool_msgs = [
        r[0]
        for r in conn.execute("SELECT content FROM messages WHERE conv_id=? AND role='tool'", (conv_id,)).fetchall()
    ]
    conn.close()

    assert any("fizzbuzz" in (m or "") for m in tool_msgs)
    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"


def test_loop_failover_integration(tmp_db, monkeypatch):
    """Loop completes via fallback provider when primary raises."""

    ok_client = MagicMock()
    ok_client.chat.completions.create.return_value = make_response(content="from fallback", total_tokens=4)

    failing_client = MagicMock()
    failing_client.chat.completions.create.side_effect = RuntimeError("primary down")

    with patch("agent.providers.create_client") as mock_create:
        mock_create.side_effect = [failing_client, ok_client]
        chain = ProviderChain(
            [
                {"base_url": "u1", "api_key": "k1", "model": "m1", "name": "primary"},
                {"base_url": "u2", "api_key": "k2", "model": "m2", "name": "fallback"},
            ]
        )
        monkeypatch.setattr("agent.loop.chain", chain)
        loop.run("hi")

    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"
    assert runs[0]["provider"] == "fallback"


def test_cli_main_invocation(tmp_db, monkeypatch, capsys):
    """agent.loop.main runs end-to-end and prints the assistant reply."""
    responses = [make_response(content="cli reply", total_tokens=2)]
    it = iter(responses)

    def fake_chat(messages, tools=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    loop.main("hello from cli")

    captured = capsys.readouterr()
    assert "cli reply" in captured.out
    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"
