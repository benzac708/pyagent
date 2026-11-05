"""Tests for the agent loop."""

from unittest.mock import patch

from tests.helpers import make_response, make_tool_call


def _patch_chain(responses):
    """Make agent.loop.chain.chat return canned responses in order."""
    it = iter(responses)

    def fake_chat(messages, tools=None, response_format=None):
        return next(it), "primary"

    return patch("agent.loop.chain", **{"chat.side_effect": fake_chat})


def test_no_tool_call_completes(tmp_path, monkeypatch):
    import agent.loop as loop

    monkeypatch.setattr("agent.config.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("agent.db.DB_PATH", str(tmp_path / "t.db"))
    import agent.db as db

    db.init_db()

    responses = [make_response(content="hello back", total_tokens=5)]
    with _patch_chain(responses):
        loop.run("hi")

    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"
    assert runs[0]["iterations"] == 1


def test_tool_call_round_trip(tmp_path, monkeypatch):
    import agent.db as db
    import agent.loop as loop

    monkeypatch.setattr("agent.config.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("agent.db.DB_PATH", str(tmp_path / "t.db"))
    db.init_db()

    tc = make_tool_call("tc1", "read_file", '{"path": "fizzbuzz.js"}')
    responses = [
        make_response(content=None, tool_calls=[tc], total_tokens=5),
        make_response(content="done", total_tokens=3),
    ]
    with _patch_chain(responses), patch("agent.loop.execute_tool", return_value="file contents") as mock_exec:
        loop.run("read fizzbuzz")

    mock_exec.assert_called_once_with("read_file", {"path": "fizzbuzz.js"})
    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "completed"
    assert runs[0]["iterations"] == 2

    # tool result was persisted
    msgs = db.get_conversation_messages(runs[0]["conv_id"]) if False else None
    # conversation id not in run row; find via runs table directly
    import sqlite3

    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conv_id = conn.execute("SELECT conv_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    msgs = db.get_conversation_messages(conv_id)
    roles = [m["role"] for m in msgs]
    assert "tool" in roles


def test_max_iterations_cap(tmp_path, monkeypatch):
    import agent.db as db
    import agent.loop as loop

    monkeypatch.setattr("agent.config.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("agent.db.DB_PATH", str(tmp_path / "t.db"))
    db.init_db()

    tc = make_tool_call("tc1", "read_file", '{"path": "x"}')
    # Always return a tool call -> never finishes naturally
    responses = [make_response(content=None, tool_calls=[tc], total_tokens=1) for _ in range(20)]
    with _patch_chain(responses), patch("agent.loop.execute_tool", return_value="r"):
        loop.run("loop forever")

    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "max_iterations"
    assert runs[0]["iterations"] == 10


def test_exception_marks_error(tmp_path, monkeypatch):
    import agent.db as db
    import agent.loop as loop

    monkeypatch.setattr("agent.config.DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr("agent.db.DB_PATH", str(tmp_path / "t.db"))
    db.init_db()

    with patch("agent.loop.chain") as mock_chain:
        mock_chain.chat.side_effect = RuntimeError("provider down")
        loop.run("hi")

    runs = db.list_runs(limit=1)
    assert runs[0]["status"] == "error"
