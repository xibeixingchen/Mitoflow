"""Tests for web AI route session-store behavior."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path so `from deploy.web.backend...` works
# (must be the parent of deploy/, not deploy/ itself)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mitoflow.ai.models import AIMessage, RuntimeEvent


def test_get_session_messages_uses_active_ai_store(monkeypatch):
    from deploy.web.backend.routes import ai as ai_routes

    class FakeStore:
        def session_exists(self, session_id):
            return session_id == "sid-1"

        def get_session_owner(self, session_id):
            return 7

        def load_messages(self, session_id):
            return [AIMessage(role="user", content="hello from sqlite")]

        def load_events(self, session_id):
            return [RuntimeEvent(type="tool_result", message="ok", data={"ok": True})]

    monkeypatch.setattr(ai_routes, "_require_auth", lambda authorization: {"id": 7})
    monkeypatch.setattr(ai_routes.state, "ai_store", FakeStore())

    payload = asyncio.run(
        ai_routes.get_session_messages("sid-1", authorization="Bearer token")
    )

    assert payload["messages"][0]["content"] == "hello from sqlite"
    assert payload["events"][0]["message"] == "ok"


def test_stream_chat_uses_domain_system_prompt(monkeypatch, tmp_path):
    from deploy.web.backend.routes import ai as ai_routes
    from mitoflow.ai.domain_prompts import MANAGER_SYSTEM_PROMPT_WITH_KNOWLEDGE
    from mitoflow.ai.models import EntryPoint
    from mitoflow.ai.tools import ToolRegistry

    class FakeStore:
        def __init__(self):
            self.messages = []

        def session_exists(self, session_id):
            return session_id == "sid-stream"

        def create_session(self, session_id, user_id=None):
            return session_id

        def get_session_owner(self, session_id):
            return 7

        def claim_session(self, session_id, user_id):
            return True

        def artifact_dir(self, session_id):
            path = tmp_path / session_id / "artifacts"
            path.mkdir(parents=True, exist_ok=True)
            return path

        def append_message(self, session_id, message):
            self.messages.append(message)

        def load_messages(self, session_id):
            return list(self.messages)

        def append_event(self, session_id, event):
            pass

        def load_events(self, session_id):
            return []

        def set_session_meta(self, *args, **kwargs):
            return True

    class FakeProvider:
        def __init__(self):
            self.requests = []

        def create_stream(self, request):
            self.requests.append(request)
            yield {"type": "text", "content": "ok"}
            yield {"type": "done"}

    class FakeService:
        def __init__(self, store, provider):
            self.store = store
            self.provider = provider
            self.registry = ToolRegistry()
            self.workspace_root = tmp_path
            self.model = "fake"

    class CapturedStreamingResponse:
        def __init__(self, body_iterator, **kwargs):
            self.body_iterator = body_iterator
            self.kwargs = kwargs

    store = FakeStore()
    provider = FakeProvider()
    service = FakeService(store, provider)
    req = ai_routes.ChatRequest(session_id="sid-stream", message="分析 cox1")

    monkeypatch.setattr(ai_routes, "_require_auth", lambda authorization: {"id": 7})
    monkeypatch.setattr(ai_routes.state, "ai_store", store)
    monkeypatch.setattr(ai_routes, "_get_ai_service", lambda **kwargs: service)
    monkeypatch.setattr(ai_routes, "_session_meta", {"sid-stream": {"name": "existing"}})
    monkeypatch.setattr(ai_routes, "StreamingResponse", CapturedStreamingResponse)

    response = asyncio.run(ai_routes.ai_chat_stream(req, authorization="Bearer token"))
    body = "".join(response.body_iterator)

    assert "ok" in body
    assert provider.requests[0].messages[0].role == "system"
    assert provider.requests[0].messages[0].content == MANAGER_SYSTEM_PROMPT_WITH_KNOWLEDGE
    assert provider.requests[0].tools == service.registry.definitions(EntryPoint.API)


def test_stream_multitool_metadata_uses_authenticated_user(monkeypatch, tmp_path):
    from deploy.web.backend.routes import ai as ai_routes
    import mitoflow.ai.runtime_deep as runtime_deep
    from mitoflow.ai.models import RuntimeResult
    from mitoflow.ai.tools import ToolRegistry

    class FakeStore:
        def __init__(self):
            self.meta_calls = []

        def session_exists(self, session_id):
            return session_id == "sid-multi"

        def create_session(self, session_id, user_id=None):
            return session_id

        def get_session_owner(self, session_id):
            return 7

        def claim_session(self, session_id, user_id):
            return True

        def artifact_dir(self, session_id):
            path = tmp_path / session_id / "artifacts"
            path.mkdir(parents=True, exist_ok=True)
            return path

        def append_message(self, session_id, message):
            pass

        def load_messages(self, session_id):
            return []

        def append_event(self, session_id, event):
            pass

        def set_session_meta(self, *args, **kwargs):
            self.meta_calls.append((args, kwargs))
            return True

    class FakeService:
        def __init__(self, store):
            self.store = store
            self.provider = object()
            self.registry = ToolRegistry()
            self.workspace_root = tmp_path
            self.model = "fake"

    class FakeOrchestrator:
        def __init__(self, **kwargs):
            pass

        def run_pipeline(self, session_id, user_text, tool_items, context, event_callback):
            return RuntimeResult(
                session_id=session_id,
                final_text="multi done",
                messages=[],
                events=[],
                tool_results=[],
            )

    class CapturedStreamingResponse:
        def __init__(self, body_iterator, **kwargs):
            self.body_iterator = body_iterator
            self.kwargs = kwargs

    store = FakeStore()
    service = FakeService(store)
    req = ai_routes.ChatRequest(
        session_id="sid-multi",
        message="run tools",
        tool_items=[{"key": "mito_gene", "label": "Annotation", "prompt": "annotate"}],
    )

    monkeypatch.setattr(ai_routes, "_require_auth", lambda authorization: {"id": 7})
    monkeypatch.setattr(ai_routes.state, "ai_store", store)
    monkeypatch.setattr(ai_routes, "_get_ai_service", lambda **kwargs: service)
    monkeypatch.setattr(ai_routes, "_session_meta", {})
    monkeypatch.setattr(ai_routes, "StreamingResponse", CapturedStreamingResponse)
    monkeypatch.setattr(runtime_deep, "MultiToolOrchestrator", FakeOrchestrator)

    response = asyncio.run(ai_routes.ai_chat_stream(req, authorization="Bearer token"))
    body = "".join(response.body_iterator)

    assert "multi done" in body
    assert store.meta_calls
    assert store.meta_calls[0][1]["user_id"] == 7


def test_wiki_graph_falls_back_to_packaged_wiki_pages(monkeypatch, tmp_path):
    from deploy.web.backend.routes import ai as ai_routes

    monkeypatch.setattr(ai_routes, "_require_auth", lambda authorization: {"id": 7})
    monkeypatch.setattr(ai_routes, "PROJECT_ROOT", tmp_path)

    payload = asyncio.run(
        ai_routes.get_wiki_graph(session_id="", query="", authorization="Bearer token")
    )

    assert payload["total_nodes"] > 0
    assert any("RNA" in node["label"] or "Genome" in node["label"] for node in payload["nodes"])
