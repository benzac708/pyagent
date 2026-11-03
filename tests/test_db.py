"""Tests for SQLite persistence layer."""

import pytest

from agent import db


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("agent.config.DB_PATH", db_path)
    monkeypatch.setattr("agent.db.DB_PATH", db_path)
    db.init_db()
    yield db_path


def test_init_creates_tables(tmp_db):
    import sqlite3

    conn = sqlite3.connect(tmp_db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert {"conversations", "messages", "runs"} <= tables


def test_conversation_lifecycle(tmp_db):
    db.create_conversation("c1")
    db.save_message("c1", "user", content="hi")
    db.save_message("c1", "assistant", content="hello")

    msgs = db.get_conversation_messages("c1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hi"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "hello"


def test_save_run_and_list(tmp_db):
    db.create_conversation("c1")
    db.save_run("r1", "c1", "primary", 2, 100, "completed")
    db.save_run("r2", "c1", "primary", 1, 50, "completed")

    runs = db.list_runs(limit=10)
    assert len(runs) == 2
    ids = {r["id"] for r in runs}
    assert ids == {"r1", "r2"}


def test_save_message_with_tool_call(tmp_db):
    db.create_conversation("c1")
    tc = [{"id": "t1", "type": "function", "function": {"name": "read_file", "arguments": '{"path":"x"}'}}]
    db.save_message("c1", "assistant", content=None, tool_calls=tc)
    db.save_message("c1", "tool", content="file contents", tool_call_id="t1")

    msgs = db.get_conversation_messages("c1")
    assert len(msgs) == 2
    assert msgs[0]["tool_calls"][0]["function"]["name"] == "read_file"
    assert msgs[1]["role"] == "tool"
    assert msgs[1]["content"] == "file contents"
    assert msgs[1]["tool_call_id"] == "t1"


def test_get_conversation_messages_empty(tmp_db):
    assert db.get_conversation_messages("nonexistent") == []
