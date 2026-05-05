"""AI chat and session management routes."""

from __future__ import annotations

import json as _json
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import PROJECT_ROOT, safe_path
from ..state import state

router = APIRouter()

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
    workspace = Path(__import__("os").getenv("MITOFLOW_WORKSPACE", "."))
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


@router.post("/api/ai/sessions")
async def create_ai_session():
    """Create a new AI chat session."""
    svc = _get_ai_service()
    session_id = svc.create_session()
    state.ai_sessions[session_id] = time.time()
    _persist_session(session_id)
    return {"session_id": session_id}


@router.get("/api/ai/sessions")
async def list_ai_sessions():
    """List all AI chat sessions with metadata."""
    if state.ai_store is not None:
        sessions = state.ai_store.list_sessions()
        return {"sessions": sessions}
    result = []
    for sid in state.ai_sessions:
        meta = _session_meta.get(sid, {})
        result.append({
            "id": sid,
            "name": meta.get("name", sid[:8] + "..."),
            "first_message": meta.get("first_message", ""),
            "pinned": meta.get("pinned", False),
            "created": state.ai_sessions[sid],
        })
    result.sort(key=lambda s: (not s["pinned"], -s["created"]))
    return {"sessions": result}


@router.delete("/api/ai/sessions/{session_id}")
async def delete_ai_session(session_id: str):
    """Delete a session and its data."""
    import shutil
    if state.ai_store is not None:
        state.ai_store.delete_session(session_id)
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
async def update_session_meta(
    session_id: str,
    name: Optional[str] = None,
    pinned: Optional[bool] = None,
):
    """Update session name or pin status."""
    if state.ai_store is not None:
        ok = state.ai_store.set_session_meta(session_id, name=name, pinned=pinned)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True, "name": name, "pinned": pinned}
    if session_id not in state.ai_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id not in _session_meta:
        _session_meta[session_id] = {}
    if name is not None:
        _session_meta[session_id]["name"] = name
    if pinned is not None:
        _session_meta[session_id]["pinned"] = pinned
    _persist_session(session_id)
    return {"ok": True, **_session_meta[session_id]}


@router.get("/api/ai/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Load chat history for a session."""
    try:
        from mitoflow.ai.sessions import LocalSessionStore
        store = LocalSessionStore(Path(__import__("os").getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions")))
        if not store.session_exists(session_id):
            return {"messages": [], "events": []}
        messages = store.load_messages(session_id)
        events = store.load_events(session_id)
        return {
            "messages": [{"role": m.role, "content": m.content, "name": m.name, "tool_calls": [tc.model_dump() for tc in (m.tool_calls or [])]} for m in messages],
            "events": events,
        }
    except Exception:
        return {"messages": [], "events": []}


@router.get("/api/ai/sessions/{session_id}/results")
async def get_session_results(session_id: str):
    """Browse result directories for a session."""
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
async def download_result_file(session_id: str, path: str = Query(...)):
    """Download a file from the session's results directories."""
    from pathlib import Path as _P
    allowed = (_P(PROJECT_ROOT / ".mitoflow_ai_sessions") / session_id / "artifacts").resolve()
    target = safe_path(allowed, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    from fastapi.responses import FileResponse
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")


@router.post("/api/ai/chat")
async def ai_chat(req: ChatRequest):
    """Send a message to the AI assistant."""
    if req.session_id not in state.ai_sessions:
        state.ai_sessions[req.session_id] = time.time()
    try:
        svc = _get_ai_service(provider=req.provider, model=req.model, api_key=req.api_key, base_url=req.base_url)
        from mitoflow.ai.models import EntryPoint
        result = svc.send_message(req.session_id, req.message, EntryPoint.API)
        if req.session_id not in _session_meta:
            _session_meta[req.session_id] = {"name": req.message[:50], "first_message": req.message[:30], "pinned": False}
            _persist_session(req.session_id)
        return result.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Configuration error: {e}. Provide an API key or set the environment variable.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)[:300]}")


@router.post("/api/ai/chat/stream")
async def ai_chat_stream(req: ChatRequest):
    """Stream AI response via SSE."""
    if req.session_id not in state.ai_sessions:
        state.ai_sessions[req.session_id] = time.time()

    async def event_stream():
        try:
            svc = _get_ai_service(provider=req.provider, model=req.model, api_key=req.api_key, base_url=req.base_url)
            from mitoflow.ai.models import EntryPoint, AIMessage, ProviderRequest, ToolCall
            from mitoflow.ai.tools import ToolContext
            from mitoflow.ai.prompts import MANAGER_SYSTEM_PROMPT

            store = svc.store
            sid = req.session_id
            if not store.session_exists(sid):
                store.create_session()

            store.append_message(sid, AIMessage(role="user", content=req.message))
            yield f"data: {_json.dumps({'type': 'thinking', 'message': 'Analyzing...'})}\n\n"

            ctx = ToolContext(
                session_id=sid,
                workspace_root=svc.workspace_root,
                output_root=store.artifact_dir(sid),
                entry_point=EntryPoint.API,
            )
            tools = svc.registry.definitions(EntryPoint.API)
            messages = [AIMessage(role="system", content=MANAGER_SYSTEM_PROMPT)] + store.load_messages(sid)

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
                            yield f"data: {_json.dumps({'type': 'tool_call', 'name': tc.name, 'arguments': tc.arguments})}\n\n"
                except Exception:
                    resp = svc.provider.create(req_p)
                    full_text = resp.message.content
                    tool_calls = resp.tool_calls
                    if full_text:
                        yield f"data: {_json.dumps({'type': 'text', 'content': full_text})}\n\n"

                if not tool_calls:
                    store.append_message(sid, AIMessage(role="assistant", content=full_text))
                    yield f"data: {_json.dumps({'type': 'done', 'final_text': full_text})}\n\n"
                    break

                store.append_message(sid, AIMessage(role="assistant", content=full_text, tool_calls=tool_calls))
                for tc in tool_calls:
                    result = svc.registry.execute(tc, ctx)
                    yield f"data: {_json.dumps({'type': 'tool_result', 'name': result.name, 'content': result.content[:500], 'ok': result.ok})}\n\n"
                    store.append_message(sid, AIMessage(role="tool", name=result.name, tool_call_id=result.call_id, content=result.content))

                messages = [AIMessage(role="system", content=MANAGER_SYSTEM_PROMPT)] + store.load_messages(sid)

            if req.session_id not in _session_meta:
                _session_meta[req.session_id] = {"name": req.message[:50], "first_message": req.message[:30], "pinned": False}
                _persist_session(req.session_id)

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)[:300]})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/api/ai/tools")
async def list_ai_tools():
    """List available AI tools."""
    svc = _get_ai_service()
    from mitoflow.ai.models import EntryPoint
    return {"tools": svc.list_tools(EntryPoint.API)}
