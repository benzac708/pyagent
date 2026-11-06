"""Integration tests: real tools, provider failover through the loop, CLI."""

import json
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

    def fake_chat(messages, tools=None, response_format=None):
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

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    loop.main("hello from cli")

    captured = capsys.readouterr()
    assert "cli reply" in captured.out
    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"


def test_loop_with_real_check_disk_tool(tmp_db, monkeypatch):
    """Agent loop invokes real check_disk tool and persists result."""
    tc = make_tool_call("tc1", "check_disk", '{"path": "/"}')
    responses = [
        make_response(content=None, tool_calls=[tc], total_tokens=5),
        make_response(content="disk ok", total_tokens=3),
    ]
    it = iter(responses)

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    result = loop.run("check disk")

    conn = sqlite3.connect(tmp_db)
    conv_id = conn.execute("SELECT conv_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    tool_msgs = [
        r[0]
        for r in conn.execute("SELECT content FROM messages WHERE conv_id=? AND role='tool'", (conv_id,)).fetchall()
    ]
    conn.close()

    assert any("path=/" in (m or "") for m in tool_msgs)
    assert result["status"] == "completed"


def test_loop_working_memory_persisted(tmp_db, monkeypatch):
    """Notes (working memory) are saved to runs table."""
    tc = make_tool_call("tc1", "check_disk", '{"path": "/"}')
    responses = [
        make_response(content=None, tool_calls=[tc], total_tokens=5),
        make_response(content="done", total_tokens=3),
    ]
    it = iter(responses)

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    result = loop.run("check disk")

    assert "check_disk" in result.get("notes", {})
    # Verify persisted in DB
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT notes FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    conn.close()
    assert row is not None
    notes = json.loads(row[0]) if row[0] else {}
    assert "check_disk" in notes


def test_loop_event_log_persisted(tmp_db, monkeypatch):
    """Event log is saved to runs table."""
    responses = [make_response(content="hello", total_tokens=5)]
    it = iter(responses)

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    result = loop.run("hi")

    assert any(e["type"] == "agent_completed" for e in result.get("events", []))
    conn = sqlite3.connect(tmp_db)
    row = conn.execute("SELECT events FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    conn.close()
    assert row is not None
    events = json.loads(row[0]) if row[0] else []
    assert any(e["type"] == "agent_completed" for e in events)


def test_destructive_tool_requires_confirmation(tmp_db, monkeypatch):
    """Destructive tool without confirmed=true returns confirmation required."""
    tc = make_tool_call("tc1", "bash", '{"command": "echo hi"}')
    responses = [
        make_response(content=None, tool_calls=[tc], total_tokens=5),
        make_response(content="done", total_tokens=3),
    ]
    it = iter(responses)

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    loop.run("run bash")

    conn = sqlite3.connect(tmp_db)
    conv_id = conn.execute("SELECT conv_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    tool_msgs = [
        r[0]
        for r in conn.execute("SELECT content FROM messages WHERE conv_id=? AND role='tool'", (conv_id,)).fetchall()
    ]
    conn.close()

    assert any("Confirmation required" in (m or "") for m in tool_msgs)


def test_parallel_tool_execution(tmp_db, monkeypatch):
    """Multiple tools in one turn execute and persist results."""
    tc1 = make_tool_call("tc1", "check_disk", '{"path": "/"}')
    tc2 = make_tool_call("tc2", "check_services", '{"services": ["nginx"]}')
    responses = [
        make_response(content=None, tool_calls=[tc1, tc2], total_tokens=5),
        make_response(content="done", total_tokens=3),
    ]
    it = iter(responses)

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    mock_chain = MagicMock()
    mock_chain.chat.side_effect = fake_chat
    monkeypatch.setattr("agent.loop.chain", mock_chain)

    loop.run("check everything")

    conn = sqlite3.connect(tmp_db)
    conv_id = conn.execute("SELECT conv_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    tool_msgs = [
        r[0]
        for r in conn.execute("SELECT content FROM messages WHERE conv_id=? AND role='tool'", (conv_id,)).fetchall()
    ]
    conn.close()

    assert len(tool_msgs) == 2
    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"
    assert runs[0]["iterations"] == 2
