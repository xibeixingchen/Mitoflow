"""Tests for local AI session persistence."""

from mitoflow.ai.models import AIMessage, RuntimeEvent
from mitoflow.ai.sessions import LocalSessionStore


def test_session_store_creates_and_loads_messages(tmp_path):
    store = LocalSessionStore(tmp_path)
    session_id = store.create_session()
    store.append_message(session_id, AIMessage(role="user", content="hello"))
    store.append_message(session_id, AIMessage(role="assistant", content="hi"))

    messages = store.load_messages(session_id)

    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "hello"


def test_session_store_records_events(tmp_path):
    store = LocalSessionStore(tmp_path)
    session_id = store.create_session()
    store.append_event(
        session_id,
        RuntimeEvent(type="tool_result", message="Tool completed", data={"ok": True}),
    )

    events = store.load_events(session_id)

    assert events[0].type == "tool_result"
    assert events[0].data == {"ok": True}


def test_session_store_returns_empty_for_missing(tmp_path):
    store = LocalSessionStore(tmp_path)

    assert store.load_messages("nonexistent") == []
    assert store.load_events("nonexistent") == []


def test_session_store_checks_existence(tmp_path):
    store = LocalSessionStore(tmp_path)
    session_id = store.create_session()

    assert store.session_exists(session_id) is True
    assert store.session_exists("nonexistent") is False


def test_session_store_provides_artifact_dir(tmp_path):
    store = LocalSessionStore(tmp_path)
    session_id = store.create_session()

    artifact_dir = store.artifact_dir(session_id)

    assert artifact_dir.exists()
    assert artifact_dir.name == "artifacts"
