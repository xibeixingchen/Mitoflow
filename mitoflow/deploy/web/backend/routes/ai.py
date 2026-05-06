"""AI chat and session management routes."""

from __future__ import annotations

import json as _json
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import PROJECT_ROOT, WORKSPACE_ROOT, safe_path
from ..state import state
from .auth import _require_auth

router = APIRouter()


def _require_session_ownership(session_id: str, user: dict) -> None:
    """Raise 404 if `user` does not own `session_id`.

    Orphan sessions (NULL owner) are not accessible to any user.
    """
    if state.ai_store is None:
        return
    if not state.ai_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    owner = state.ai_store.get_session_owner(session_id)
    # Orphan sessions (owner=None) are not accessible
    if owner is None or owner != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

# Session metadata storage
_session_meta: dict = {}
_sessions_file = Path(__import__("os").getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions")) / "_sessions.json"


class ChatRequest(BaseModel):
    """AI chat request — supports all OpenAI/Anthropic-compatible providers."""

    session_id: str
    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    tool_items: Optional[list] = None  # Multi-tool: [{key, label, prompt, description}]


class UpdateSessionRequest(BaseModel):
    """Rename or pin a session."""
    name: Optional[str] = None
    pinned: Optional[bool] = None


def _get_ai_service(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
):
    """Get AI service — prefers global instance, falls back to per-request override."""
    from mitoflow.ai.service import AIService, build_provider

    if provider is None and model is None and api_key is None and base_url is None:
        if state.ai_service is None:
            raise HTTPException(status_code=503, detail="AI service not initialized")
        return state.ai_service

    sessions_dir = Path(__import__("os").getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions"))
    workspace = WORKSPACE_ROOT
    prov, resolved_model = build_provider(provider_name=provider, model=model, api_key=api_key, base_url=base_url)
    from mitoflow.ai.service import build_default_registry
    registry = build_default_registry()
    return AIService(session_root=sessions_dir, workspace_root=workspace, registry=registry, provider=prov, model=resolved_model)


def _load_sessions():
    global _session_meta
    if _sessions_file.exists():
        try:
            data = _json.loads(_sessions_file.read_text())
            for s in data.get("sessions", []):
                state.ai_sessions[s["id"]] = s.get("created", time.time())
            _session_meta = data.get("meta", {})
        except Exception:
            pass
    from pathlib import Path as _P
    for d in [_P(PROJECT_ROOT / ".mitoflow_ai_sessions"), _P(PROJECT_ROOT / "mitoflow_workspace")]:
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir() and not sub.name.startswith(".") and not sub.name.startswith("_"):
                    sid = sub.name
                    if sid not in state.ai_sessions and len(sid) > 20:
                        state.ai_sessions[sid] = sub.stat().st_mtime

    # Migrate JSON sessions into SQLite so they appear in list_sessions()
    if state.ai_store is not None:
        from mitoflow.ai.sessions import LocalSessionStore
        local_store = LocalSessionStore(
            Path(__import__("os").getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions"))
        )
        for sid, created in state.ai_sessions.items():
            if not state.ai_store.session_exists(sid):
                meta = _session_meta.get(sid, {})
                state.ai_store._conn.execute(
                    "INSERT OR IGNORE INTO sessions (id, created_at, name, first_message, pinned) VALUES (?, ?, ?, ?, ?)",
                    (sid, created, meta.get("name"), meta.get("first_message"), int(meta.get("pinned", False))),
                )
            # Migrate messages and events from JSONL if SQLite is empty
            if state.ai_store.message_count(sid) == 0 and local_store.session_exists(sid):
                for msg in local_store.load_messages(sid):
                    state.ai_store.append_message(sid, msg)
                for ev in local_store.load_events(sid):
                    state.ai_store.append_event(sid, ev)
        state.ai_store._conn.commit()


def _save_sessions():
    try:
        _sessions_file.parent.mkdir(parents=True, exist_ok=True)
        _sessions_file.write_text(_json.dumps({
            "sessions": [{"id": s, "created": t} for s, t in state.ai_sessions.items()],
            "meta": _session_meta,
        }))
    except Exception:
        pass


def _persist_session(session_id: str):
    """Save session list to disk after changes."""
    _save_sessions()


def _local_session_store():
    from mitoflow.ai.sessions import LocalSessionStore
    return LocalSessionStore(Path(__import__("os").getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions")))


def _read_session_store(session_id: str):
    """Return the active store for reading a session, preferring SQLite."""
    if state.ai_store is not None and state.ai_store.session_exists(session_id):
        return state.ai_store
    store = _local_session_store()
    if store.session_exists(session_id):
        return store
    return None


def _serialize_ai_message(message):
    return {
        "role": message.role,
        "content": message.content,
        "name": message.name,
        "tool_call_id": message.tool_call_id,
        "tool_calls": [tc.model_dump() for tc in (message.tool_calls or [])],
    }


def _serialize_runtime_event(event):
    return event.model_dump(mode="json") if hasattr(event, "model_dump") else event


@router.post("/api/ai/sessions")
async def create_ai_session(authorization: str = Header(None)):
    """Create a new AI chat session, owned by the authenticated user."""
    user = _require_auth(authorization)
    svc = _get_ai_service()
    session_id = svc.create_session(user_id=user["id"])
    state.ai_sessions[session_id] = time.time()
    _persist_session(session_id)
    return {"session_id": session_id}


@router.get("/api/ai/sessions")
async def list_ai_sessions(authorization: str = Header(None)):
    """List AI chat sessions for the authenticated user only."""
    user = _require_auth(authorization)
    if state.ai_store is not None:
        sessions = state.ai_store.list_sessions(user_id=user["id"])
        return {"sessions": sessions}
    # Fallback (no SQLite store): in-memory has no user tagging, so return empty.
    return {"sessions": []}


@router.delete("/api/ai/sessions/{session_id}")
async def delete_ai_session(session_id: str, authorization: str = Header(None)):
    """Delete a session and its data — only if the caller owns it."""
    import shutil
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    if state.ai_store is not None:
        state.ai_store.delete_session(session_id, user_id=user["id"])
    if session_id in state.ai_sessions:
        del state.ai_sessions[session_id]
    if session_id in _session_meta:
        del _session_meta[session_id]
    _persist_session(session_id)
    for d in [PROJECT_ROOT / ".mitoflow_ai_sessions" / session_id, PROJECT_ROOT / "mitoflow_workspace" / session_id]:
        if d.exists():
            shutil.rmtree(str(d), ignore_errors=True)
    return {"ok": True}


@router.patch("/api/ai/sessions/{session_id}")
async def update_session_meta(session_id: str, req: UpdateSessionRequest,
                              authorization: str = Header(None)):
    """Update session name or pin status — only if the caller owns it."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    if state.ai_store is not None:
        ok = state.ai_store.set_session_meta(
            session_id, name=req.name, pinned=req.pinned, user_id=user["id"],
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True, "name": req.name, "pinned": req.pinned}
    if session_id not in state.ai_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id not in _session_meta:
        _session_meta[session_id] = {}
    if req.name is not None:
        _session_meta[session_id]["name"] = req.name
    if req.pinned is not None:
        _session_meta[session_id]["pinned"] = req.pinned
    _persist_session(session_id)
    return {"ok": True, **_session_meta[session_id]}


@router.get("/api/ai/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, authorization: str = Header(None)):
    """Load chat history for a session — owner only."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    try:
        store = _read_session_store(session_id)
        if store is None:
            return {"messages": [], "events": []}
        messages = store.load_messages(session_id)
        events = store.load_events(session_id)
        return {
            "messages": [_serialize_ai_message(m) for m in messages],
            "events": [_serialize_runtime_event(e) for e in events],
        }
    except Exception:
        return {"messages": [], "events": []}


@router.get("/api/ai/sessions/{session_id}/results")
async def get_session_results(session_id: str, authorization: str = Header(None)):
    """Browse result directories for a session — owner only."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    from pathlib import Path as _P
    results = []
    bases = [
        _P(PROJECT_ROOT / ".mitoflow_ai_sessions") / session_id / "artifacts",
        _P(PROJECT_ROOT / "mitoflow_workspace") / session_id,
    ]
    for base in bases:
        if base.exists():
            for d in sorted(base.rglob("*")):
                if d.is_dir():
                    rel_parts = d.relative_to(base).parts
                    if any(p.startswith(".") for p in rel_parts):
                        continue
                    if not rel_parts:
                        continue
                    rel = str(d.relative_to(base))
                    files = [{"name": f.name, "size": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file()][:20]
                    if files:
                        results.append({"path": rel, "files": files, "base": str(base)})
    return {"results": results[:30], "workspace": str(_P(PROJECT_ROOT / "mitoflow_workspace") / session_id)}


@router.get("/api/ai/sessions/{session_id}/results/download")
async def download_result_file(session_id: str, path: str = Query(...),
                               authorization: str = Header(None)):
    """Download a file from the session's results directories — owner only."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    from pathlib import Path as _P
    allowed = (_P(PROJECT_ROOT / ".mitoflow_ai_sessions") / session_id / "artifacts").resolve()
    target = safe_path(allowed, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    from fastapi.responses import FileResponse
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")


@router.get("/api/ai/sessions/{session_id}/export")
async def export_session_workflow(session_id: str, format: str = Query("json"),
                                  authorization: str = Header(None)):
    """Export session events as JSON or Markdown — owner only."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    from pathlib import Path as _P
    from datetime import datetime

    store = _read_session_store(session_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Session not found")

    events = store.load_events(session_id)
    tool_calls = [e for e in events if e.type == "tool_call"]
    tool_results = [e for e in events if e.type == "tool_result"]

    if format == "markdown":
        lines = [
            f"# MitoFlow Workflow Report",
            f"",
            f"**Session ID**: `{session_id}`",
            f"**Generated**: {datetime.now().isoformat()}",
            f"",
            f"## Tool Calls",
            f"",
        ]
        for e in tool_calls:
            name = e.data.get("name", "unknown")
            args = e.data.get("arguments", e.data)
            lines.append(f"### {name}")
            lines.append(f"```json")
            lines.append(_json.dumps(args, ensure_ascii=False, indent=2))
            lines.append(f"```")
            # Find matching result
            res = next((r for r in tool_results if r.data.get("call_id") == e.data.get("id")), None)
            if res:
                status = "✅ Success" if res.data.get("ok", True) else "❌ Failed"
                lines.append(f"**Result**: {status}")
                content = res.data.get("content", res.message)[:500]
                lines.append(f"```")
                lines.append(content)
                lines.append(f"```")
            lines.append("")
        md = "\n".join(lines)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")

    # Default JSON
    return {
        "session_id": session_id,
        "exported_at": datetime.now().isoformat(),
        "tool_calls": [{"type": e.type, "name": e.data.get("name"), "arguments": e.data.get("arguments", e.data), "time": e.data.get("timestamp")} for e in tool_calls],
        "tool_results": [{"type": e.type, "name": e.data.get("name"), "ok": e.data.get("ok"), "content": e.data.get("content", e.message)[:500]} for e in tool_results],
    }


def _ensure_session_for_chat(session_id: str, user: dict) -> None:
    """Verify the user owns this session, or auto-create/claim it.

    Behaviour:
    - Session exists, owned by user -> OK.
    - Session exists, unowned (NULL user_id) -> atomic claim for this user.
    - Session exists, owned by someone else -> 403.
    - Session does not exist -> create it for this user.
    """
    if state.ai_store is None:
        return
    if not state.ai_store.session_exists(session_id):
        state.ai_store.create_session(session_id, user_id=user["id"])
        return
    owner = state.ai_store.get_session_owner(session_id)
    if owner is None:
        # Atomic claim -- returns False if already claimed by someone else
        if not state.ai_store.claim_session(session_id, user["id"]):
            raise HTTPException(status_code=403, detail="Session belongs to another user")
        return
    if owner != user["id"]:
        raise HTTPException(status_code=403, detail="Session belongs to another user")


@router.post("/api/ai/chat")
async def ai_chat(req: ChatRequest, authorization: str = Header(None)):
    """Send a message to the AI assistant — caller must own (or claim) the session."""
    user = _require_auth(authorization)
    _ensure_session_for_chat(req.session_id, user)
    if req.session_id not in state.ai_sessions:
        state.ai_sessions[req.session_id] = time.time()
    try:
        svc = _get_ai_service(provider=req.provider, model=req.model, api_key=req.api_key, base_url=req.base_url)
        from mitoflow.ai.models import EntryPoint
        result = svc.send_message(req.session_id, req.message, EntryPoint.API)
        if req.session_id not in _session_meta:
            _session_meta[req.session_id] = {"name": req.message[:50], "first_message": req.message[:30], "pinned": False}
            _persist_session(req.session_id)
            if state.ai_store is not None:
                state.ai_store.set_session_meta(
                    req.session_id,
                    name=req.message[:50],
                    first_message=req.message[:30],
                    user_id=user["id"],
                )
        return result.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Configuration error: {e}. Provide an API key or set the environment variable.")
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).exception("AI chat error for session %s", req.session_id)
        raise HTTPException(status_code=500, detail="Internal error. Please try again.")


def _fix_orphan_tool_calls(messages: list, session_id: str, store) -> None:
    """Ensure every assistant tool_call has a matching tool result message.

    Scans the entire message history for assistant messages with tool_calls
    that lack corresponding tool results, and adds placeholder results.
    """
    from mitoflow.ai.models import AIMessage
    i = len(messages) - 1
    while i >= 0:
        msg = messages[i]
        if msg.role == "assistant" and msg.tool_calls:
            # Collect expected call_ids
            expected_ids = set()
            for tc in msg.tool_calls:
                tc_id = tc.id if hasattr(tc, "id") else tc.get("id", "")
                if tc_id:
                    expected_ids.add(tc_id)
            # Check which already have results in messages AFTER this assistant
            answered = set()
            for j in range(i + 1, len(messages)):
                m = messages[j]
                if m.role == "tool" and m.tool_call_id:
                    answered.add(m.tool_call_id)
            # Fill missing
            missing = expected_ids - answered
            for tc in msg.tool_calls:
                tc_id = tc.id if hasattr(tc, "id") else tc.get("id", "")
                tc_name = tc.name if hasattr(tc, "name") else tc.get("name", "unknown")
                if tc_id in missing:
                    placeholder = AIMessage(
                        role="tool", name=tc_name,
                        tool_call_id=tc_id,
                        content="(Previous tool call was interrupted. Please try again.)",
                    )
                    messages.append(placeholder)
                    store.append_message(session_id, placeholder)
        i -= 1


@router.post("/api/ai/chat/stream")
async def ai_chat_stream(req: ChatRequest, authorization: str = Header(None)):
    """Stream AI response via SSE — caller must own (or claim) the session."""
    user = _require_auth(authorization)
    _ensure_session_for_chat(req.session_id, user)
    if req.session_id not in state.ai_sessions:
        state.ai_sessions[req.session_id] = time.time()

    def event_stream():
        """Sync generator — Starlette runs it in a threadpool so the async
        event loop stays free to flush SSE chunks to the client immediately."""
        try:
            svc = _get_ai_service(provider=req.provider, model=req.model, api_key=req.api_key, base_url=req.base_url)
            from mitoflow.ai.models import EntryPoint, AIMessage, ProviderRequest, RuntimeEvent, ToolCall
            from mitoflow.ai.tools import ToolContext
            try:
                from mitoflow.ai.domain_prompts import MANAGER_SYSTEM_PROMPT_WITH_KNOWLEDGE as MANAGER_SYSTEM_PROMPT
            except ImportError:
                from mitoflow.ai.prompts import MANAGER_SYSTEM_PROMPT

            store = svc.store
            sid = req.session_id
            if not store.session_exists(sid):
                store.create_session(sid)

            store.append_message(sid, AIMessage(role="user", content=req.message))
            yield f"data: {_json.dumps({'type': 'thinking', 'message': 'Analyzing...'})}\n\n"

            ctx = ToolContext(
                session_id=sid,
                workspace_root=svc.workspace_root,
                output_root=store.artifact_dir(sid),
                entry_point=EntryPoint.API,
                last_user_message=req.message,
            )

            # Fix message consistency before any path (multi-tool or normal)
            _fix_orphan_tool_calls(
                [AIMessage(role="system", content=MANAGER_SYSTEM_PROMPT)] + store.load_messages(sid),
                sid, store,
            )

            # ── Multi-tool orchestration path ─────────────────────
            if req.tool_items and len(req.tool_items) > 0:
                from mitoflow.ai.runtime_deep import MultiToolOrchestrator
                orchestrator = MultiToolOrchestrator(
                    provider=svc.provider, registry=svc.registry,
                    store=store, model=svc.model,
                )
                _collected_events: list = []
                def _orch_event_cb(event_type: str, data: dict):
                    _collected_events.append((event_type, data))
                result = orchestrator.run_pipeline(sid, req.message, req.tool_items, ctx, _orch_event_cb)
                # Yield collected events
                for etype, edata in _collected_events:
                    yield f"data: {_json.dumps({'type': etype, **edata})}\n\n"
                for ev in result.events:
                    store.append_event(sid, ev)
                # Stream final text with typewriter effect
                final = result.final_text
                for i in range(0, len(final), 20):
                    yield f"data: {_json.dumps({'type': 'text', 'content': final[i:i+20]})}\n\n"
                yield f"data: {_json.dumps({'type': 'done', 'final_text': final})}\n\n"
                # Persist session metadata
                if req.session_id not in _session_meta:
                    _session_meta[req.session_id] = {"name": req.message[:50], "first_message": req.message[:30], "pinned": False}
                    _persist_session(req.session_id)
                    if state.ai_store is not None:
                        state.ai_store.set_session_meta(
                            req.session_id, name=req.message[:50],
                            first_message=req.message[:30],
                            user_id=user["id"],
                        )
                return  # end generator after multi-tool path

            # ── Normal single-tool / chat path ─────────────────────
            tools = svc.registry.definitions(EntryPoint.API)
            messages = [AIMessage(role="system", content=MANAGER_SYSTEM_PROMPT)] + store.load_messages(sid)

            # Fix message consistency: if last assistant has tool_calls without tool results,
            # add placeholder tool results so the API doesn't reject the request
            _fix_orphan_tool_calls(messages, sid, store)

            # Anti-loop: track repeated identical failures in SSE loop
            _failure_tracker: dict[str, int] = {}
            MAX_SAME_FAILURE = 3

            for _turn in range(8):
                req_p = ProviderRequest(model=svc.model, messages=messages, tools=tools)
                full_text = ""
                tool_calls: list = []

                try:
                    for chunk in svc.provider.create_stream(req_p):
                        if chunk["type"] == "text":
                            full_text += chunk["content"]
                            yield f"data: {_json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                        elif chunk["type"] == "tool_call":
                            tc = ToolCall(id=chunk.get("id", ""), name=chunk["name"], arguments=chunk.get("arguments", {}))
                            tool_calls.append(tc)
                            store.append_event(sid, RuntimeEvent(type="tool_call", message=tc.name, data={"arguments": tc.arguments}))
                            yield f"data: {_json.dumps({'type': 'tool_call', 'name': tc.name, 'arguments': tc.arguments})}\n\n"
                        elif chunk["type"] == "done":
                            pass  # stream finished normally
                except Exception:
                    import traceback
                    traceback.print_exc()
                    # Fallback to non-streaming, then simulate typewriter in chunks
                    resp = svc.provider.create(req_p)
                    full_text = resp.message.content
                    tool_calls = resp.tool_calls
                    if full_text:
                        # Send in ~20-char chunks for a smoother typewriter feel
                        for i in range(0, len(full_text), 20):
                            yield f"data: {_json.dumps({'type': 'text', 'content': full_text[i:i+20]})}\n\n"

                if not tool_calls:
                    store.append_message(sid, AIMessage(role="assistant", content=full_text))
                    yield f"data: {_json.dumps({'type': 'done', 'final_text': full_text})}\n\n"
                    break

                store.append_message(sid, AIMessage(role="assistant", content=full_text, tool_calls=tool_calls))
                for tc in tool_calls:
                    result = svc.registry.execute(tc, ctx)
                    store.append_event(sid, RuntimeEvent(type="tool_result", message=result.name, data={"content": result.content[:500], "ok": result.ok}))
                    yield f"data: {_json.dumps({'type': 'tool_result', 'name': result.name, 'content': result.content[:500], 'ok': result.ok})}\n\n"
                    store.append_message(sid, AIMessage(role="tool", name=result.name, tool_call_id=result.call_id, content=result.content))

                    # Anti-loop: track repeated identical failures
                    if not result.ok:
                        fail_key = f"{tc.name}:{_json.dumps(tc.arguments, sort_keys=True)}"
                        _failure_tracker[fail_key] = _failure_tracker.get(fail_key, 0) + 1
                        if _failure_tracker[fail_key] >= MAX_SAME_FAILURE:
                            final_text = (
                                f"Stopped: tool '{tc.name}' failed {MAX_SAME_FAILURE} times "
                                f"with the same arguments. Please check your input and try again."
                            )
                            store.append_message(sid, AIMessage(role="assistant", content=final_text))
                            yield f"data: {_json.dumps({'type': 'done', 'final_text': final_text})}\n\n"
                            break
                    else:
                        _failure_tracker.clear()
                else:
                    messages = [AIMessage(role="system", content=MANAGER_SYSTEM_PROMPT)] + store.load_messages(sid)
                    continue
                break

            if req.session_id not in _session_meta:
                _session_meta[req.session_id] = {"name": req.message[:50], "first_message": req.message[:30], "pinned": False}
                _persist_session(req.session_id)
                # Also persist to SQLite store so list_sessions returns the title
                if state.ai_store is not None:
                    state.ai_store.set_session_meta(
                        req.session_id,
                        name=req.message[:50],
                        first_message=req.message[:30],
                        user_id=user["id"],
                    )

        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).exception("AI stream error for session %s", req.session_id)
            yield f"data: {_json.dumps({'type': 'error', 'message': 'Internal error. Please try again.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/api/ai/tools")
async def list_ai_tools(authorization: str = Header(None)):
    """List available AI tools."""
    _require_auth(authorization)
    svc = _get_ai_service()
    from mitoflow.ai.models import EntryPoint
    return {"tools": svc.list_tools(EntryPoint.API)}


@router.get("/api/ai/wiki/graph")
async def get_wiki_graph(
    session_id: str = Query(default=""),
    query: str = Query(default=""),
    authorization: str = Header(None),
):
    """Build knowledge graph from wiki pages, return nodes/edges for frontend visualization."""
    user = _require_auth(authorization)
    if session_id:
        _require_session_ownership(session_id, user)
    from mitoflow.ai.wiki.organelle_graph import OrganelleGraph, auto_detect_organelle

    # Resolve wiki directory: session-specific or global
    wiki_dir = None
    if session_id:
        candidates = [
            PROJECT_ROOT / ".mitoflow_ai_sessions" / session_id / "artifacts",
            PROJECT_ROOT / "mitoflow_workspace" / session_id / "wiki",
        ]
        for c in candidates:
            if c.exists():
                wiki_dir = c
                break
    if wiki_dir is None:
        wiki_dir = PROJECT_ROOT / "mitoflow_workspace" / "wiki"
    if not wiki_dir.exists():
        from mitoflow.ai.wiki import wiki_index
        wiki_dir = Path(wiki_index.__file__).resolve().parent / "pages"

    # Build organelle-aware graph
    og = OrganelleGraph()
    result = og.build_organelle_graph(wiki_dir)

    # If no wiki pages found, return empty graph
    if not result.base_graph.nodes:
        return {"nodes": [], "edges": [], "organelle": "unknown", "total_nodes": 0}

    # Type mapping: backend GraphNode.type → frontend KGNode.type
    _TYPE_MAP = {
        "entity": "gene",
        "concept": "concept",
        "source": "reference",
        "synthesis": "wiki_page",
        "page": "wiki_page",
    }

    # Edge type mapping: OrganelleEdge.edge_type → frontend KGEdge.type
    _EDGE_MAP = {
        "gene_complex": "member_of",
        "gene_paper": "mentioned_in",
        "gene_species": "encoded_in",
        "gene_editing": "editing_target",
        "paper_method": "analyzed_by",
        "paper_organelle": "encoded_in",
    }

    nodes = []
    for n in result.base_graph.nodes:
        nodes.append({
            "id": n.id,
            "label": n.label,
            "type": _TYPE_MAP.get(n.type, n.type),
            "description": f"Type: {n.type}, links: {n.link_count}" if n.path else n.label,
            "path": n.path,
        })

    edges = []
    for e in result.base_graph.edges:
        etype = _EDGE_MAP.get(e.edge_type, "wiki_links" if e.edge_type == "wikilink" else e.edge_type)
        edges.append({"source": e.source, "target": e.target, "type": etype, "weight": e.weight})

    for oe in result.organelle_edges:
        etype = _EDGE_MAP.get(oe.edge_type, oe.edge_type)
        edges.append({"source": oe.source, "target": oe.target, "type": etype, "label": oe.label})

    # Filter by query if provided
    if query:
        q_lower = query.lower()
        matching = {n["id"] for n in nodes if q_lower in n["label"].lower() or q_lower in n.get("description", "").lower()}
        # Expand to direct neighbors
        neighbor_ids = set(matching)
        for e in edges:
            if e["source"] in matching:
                neighbor_ids.add(e["target"])
            if e["target"] in matching:
                neighbor_ids.add(e["source"])
        nodes = [n for n in nodes if n["id"] in neighbor_ids]
        edge_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["source"] in edge_ids and e["target"] in edge_ids]

    return {
        "nodes": nodes,
        "edges": edges,
        "organelle": result.detected_organelle,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


@router.get("/api/ai/wiki/entities")
async def get_wiki_entities(
    session_id: str = Query(default=""),
    authorization: str = Header(None),
):
    """Return entity definitions for chat entity linking, built from wiki pages + domain knowledge."""
    user = _require_auth(authorization)
    if session_id:
        _require_session_ownership(session_id, user)
    from mitoflow.ai.wiki.organelle_graph import _GENE_COMPLEXES, _EDITING_GENES, _MITO_KEYWORDS, _CHLORO_KEYWORDS

    entities = []

    # Gene entities from domain knowledge
    for gene in sorted(set(list(_GENE_COMPLEXES.keys()) + list(_EDITING_GENES.keys()))):
        complex_name = _GENE_COMPLEXES.get(gene, "")
        edit_type = _EDITING_GENES.get(gene, "")
        desc_parts = []
        if complex_name:
            desc_parts.append(complex_name)
        if edit_type:
            desc_parts.append(f"{edit_type} RNA editing")
        entities.append({
            "id": f"gene:{gene}",
            "match": gene,
            "type": "gene",
            "label": gene,
            "description": ", ".join(desc_parts) if desc_parts else f"Gene {gene}",
        })

    # Complex entities
    seen_complexes = set()
    for gene, cx in _GENE_COMPLEXES.items():
        if cx not in seen_complexes:
            seen_complexes.add(cx)
            cid = cx.lower().replace(" ", "_")
            entities.append({
                "id": f"complex:{cid}",
                "match": cx,
                "type": "complex",
                "label": cx,
            })

    return {"entities": entities, "total": len(entities)}
