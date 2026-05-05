"""MitoFlow Web API - FastAPI Backend."""

from __future__ import annotations
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Project root for absolute paths (works regardless of cwd)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

app = FastAPI(
    title="MitoFlow Web",
    description="Plant Mitochondrial Genome Annotation Web Service + AI Assistant",
    version="0.2.0",
)

# CORS for frontend access
_CORS_ORIGINS_STR = os.getenv("MITOFLOW_CORS_ORIGINS", "")
if _CORS_ORIGINS_STR.strip():
    _CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_STR.split(",") if o.strip()]
else:
    _CORS_ORIGINS = ["http://localhost:5173", "http://localhost:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting Middleware ────────────────────────────────────────

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limit incoming requests by IP and path category."""
    from mitoflow.ai.rate_limiter import get_rate_limiter
    limiter = get_rate_limiter()

    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # Determine rate limit category
    if path.startswith("/api/ai/chat"):
        if not limiter.check_chat(user_id=0, ip=client_ip):
            raise HTTPException(status_code=429, detail="Too many chat requests. Please wait.")
        try:
            response = await call_next(request)
            return response
        finally:
            limiter.release_chat(0)
    elif path.startswith("/api/files/upload"):
        if not limiter.check_upload(user_id=0):
            raise HTTPException(status_code=429, detail="Too many upload requests. Please wait.")

    return await call_next(request)

# Configuration
UPLOAD_DIR = Path(os.getenv("MITOFLOW_UPLOAD_DIR", PROJECT_ROOT / "mitoflow_uploads"))
RESULTS_DIR = Path(os.getenv("MITOFLOW_RESULTS_DIR", PROJECT_ROOT / "mitoflow_results"))
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {".fasta",".fa",".fas",".fna"}

UPLOAD_DIR = UPLOAD_DIR.resolve()
RESULTS_DIR = RESULTS_DIR.resolve()
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# Task storage (use Redis in production)
tasks = {}


class AnnotationRequest(BaseModel):
    """Annotation request parameters."""
    name: str = "MitoFlow"
    threads: int = 4
    skip_trna: bool = False
    skip_rrna: bool = False
    skip_qc: bool = False


class TaskStatus(BaseModel):
    """Task status response."""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: int = 0
    message: str = ""
    result_url: Optional[str] = None


def validate_fasta_file(file_path: Path) -> bool:
    """Validate uploaded FASTA file."""
    if not file_path.exists():
        return False
    if file_path.stat().st_size > MAX_FILE_SIZE:
        return False
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return False
    return True


def _safe_path(base: Path, rel: str) -> Path:
    """Resolve a relative path under base, rejecting path traversal."""
    target = (base / rel).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return target


def run_annotation_task(task_id: str, input_path: Path, output_dir: Path, params: dict):
    """Background task to run MitoFlow annotation."""
    try:
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "Starting annotation pipeline..."
        
        # Import and run MitoFlow pipeline
        import sys
        src_path = os.getenv("MITOFLOW_SRC_PATH", os.getcwd())
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        from mitoflow.core.pipeline import AnnotationPipeline
        from mitoflow.core.input import load_fasta
        
        tasks[task_id]["progress"] = 20
        tasks[task_id]["message"] = "Loading genome and running HMM search..."
        
        pipeline = AnnotationPipeline(threads=params["threads"])
        result = pipeline.run(
            fasta_path=input_path,
            output_dir=output_dir,
            name=params["name"],
            skip_trna=params["skip_trna"],
            skip_rrna=params["skip_rrna"],
            skip_qc=params["skip_qc"],
            skip_mtpt=True,  # Web version doesn't support MTPT (requires cp genome)
        )
        
        # Create result archive
        tasks[task_id]["progress"] = 90
        tasks[task_id]["message"] = "Packaging results..."
        
        archive_path = output_dir / "mitoflow_results.zip"
        shutil.make_archive(
            base_name=str(output_dir / "mitoflow_results"),
            format="zip",
            root_dir=output_dir,
        )
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "Annotation completed successfully!"
        tasks[task_id]["result_url"] = f"/api/results/{task_id}/download"
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = f"Error: {str(e)}"
        raise


@app.post("/api/annotate", response_model=TaskStatus)
async def create_annotation_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form("MitoFlow"),
    threads: int = Form(4),
    skip_trna: bool = Form(False),
    skip_rrna: bool = Form(False),
    skip_qc: bool = Form(False),
):
    """Submit a new annotation task."""
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(exist_ok=True)
    
    # Save uploaded file
    input_path = task_dir / f"input{file_ext}"
    with open(input_path, "wb") as f:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 100MB)")
        f.write(content)
    
    # Validate FASTA
    if not validate_fasta_file(input_path):
        raise HTTPException(status_code=400, detail="Invalid FASTA file")
    
    # Create output directory
    output_dir = RESULTS_DIR / task_id
    output_dir.mkdir(exist_ok=True)
    
    # Initialize task
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task queued...",
        "result_url": None,
        "output_dir": str(output_dir),
    }
    
    # Start background task
    params = {
        "name": name,
        "threads": min(threads, 8),  # Limit max threads
        "skip_trna": skip_trna,
        "skip_rrna": skip_rrna,
        "skip_qc": skip_qc,
    }
    
    background_tasks.add_task(
        run_annotation_task, task_id, input_path, output_dir, params
    )
    
    return TaskStatus(**tasks[task_id])


@app.get("/api/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get task status and progress."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(**tasks[task_id])


@app.get("/api/results/{task_id}/download")
async def download_results(task_id: str):
    """Download annotation results."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")
    
    archive_path = RESULTS_DIR / task_id / "mitoflow_results.zip"
    if not archive_path.exists():
        raise HTTPException(status_code=404, detail="Results not found")
    
    return FileResponse(
        path=archive_path,
        filename=f"mitoflow_results_{task_id[:8]}.zip",
        media_type="application/zip",
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its data."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Cleanup files
    upload_dir = UPLOAD_DIR / task_id
    result_dir = RESULTS_DIR / task_id
    
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    if result_dir.exists():
        shutil.rmtree(result_dir)
    
    del tasks[task_id]

    return {"message": "Task deleted successfully"}


# ── Authentication ──────────────────────────────────────────────────
from pydantic import BaseModel as AuthBaseModel

class RegisterRequest(AuthBaseModel):
    email: str
    username: str
    password: str

class LoginRequest(AuthBaseModel):
    email: str
    password: str

class ApiKeyUpdate(AuthBaseModel):
    api_key: str

class ProfileUpdate(AuthBaseModel):
    username: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    degree: Optional[str] = None

class ChangePasswordRequest(AuthBaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/register")
async def auth_register(req: RegisterRequest):
    """Register a new user account (email verification required)."""
    from mitoflow.ai.auth import register_user
    from mitoflow.ai.email_verification import verify_code as check_verification

    # Require verification code for registration
    code = getattr(req, 'verification_code', None)
    if code:
        result = check_verification(req.email, code, "register")
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

    result = register_user(req.email, req.username, req.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """Login and get a session token."""
    from mitoflow.ai.auth import login_user
    result = login_user(req.email, req.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.post("/api/auth/me")
async def auth_me(authorization: str = Header(None)):
    """Get current user info from token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    from mitoflow.ai.auth import get_user_by_token
    user = get_user_by_token(authorization[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@app.post("/api/auth/api-key")
async def auth_update_api_key(req: ApiKeyUpdate, authorization: str = Header(None)):
    """Update user's default API key."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    from mitoflow.ai.auth import get_user_by_token, update_api_key
    user = get_user_by_token(authorization[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    update_api_key(user["id"], req.api_key)
    return {"ok": True}


class TestConnectionRequest(AuthBaseModel):
    provider: str  # "openai" or "anthropic"
    base_url: str = ""
    api_key: str
    model: str = ""


@app.post("/api/auth/test-connection")
async def auth_test_connection(req: TestConnectionRequest):
    """Test a model connection with a minimal request."""
    import time as _time
    result = {"ok": False, "latency_ms": 0, "model": "", "error": ""}

    if not req.api_key:
        result["error"] = "API key is required"
        return result

    try:
        if req.provider == "anthropic":
            from mitoflow.ai.providers import AnthropicAdapter
            from mitoflow.ai.models import AIMessage, ProviderRequest
            adapter = AnthropicAdapter(
                api_key=req.api_key,
                model=req.model or "claude-haiku-4-5-20251001",
                base_url=req.base_url or None,
            )
            start = _time.monotonic()
            resp = adapter.create(ProviderRequest(
                model=req.model or "claude-haiku-4-5-20251001",
                messages=[AIMessage(role="user", content="Hi")],
                max_tokens=5,
            ))
            result["latency_ms"] = round((_time.monotonic() - start) * 1000)
            result["model"] = req.model
            result["ok"] = True
        else:
            from mitoflow.ai.providers import OpenAIChatAdapter
            from mitoflow.ai.models import AIMessage, ProviderRequest
            adapter = OpenAIChatAdapter(
                api_key=req.api_key,
                model=req.model or "gpt-4o-mini",
                base_url=req.base_url or None,
            )
            start = _time.monotonic()
            resp = adapter.create(ProviderRequest(
                model=req.model or "gpt-4o-mini",
                messages=[AIMessage(role="user", content="Hi")],
                max_tokens=5,
            ))
            result["latency_ms"] = round((_time.monotonic() - start) * 1000)
            result["model"] = req.model
            result["ok"] = True
    except Exception as e:
        result["error"] = str(e)[:200]

    return result


# ── Email Verification & Password Reset ─────────────────────────────

class SendCodeRequest(AuthBaseModel):
    email: str
    purpose: str = "register"  # "register" or "reset_password"

class VerifyCodeRequest(AuthBaseModel):
    email: str
    code: str
    purpose: str = "register"

class ResetPasswordRequest(AuthBaseModel):
    token: str
    new_password: str


@app.post("/api/auth/send-code")
async def auth_send_code(req: SendCodeRequest):
    """Send a verification code to email."""
    from mitoflow.ai.email_verification import (
        store_verification_code,
        send_verification_email,
    )
    if req.purpose not in ("register", "reset_password"):
        raise HTTPException(status_code=400, detail="Invalid purpose")
    # For reset_password, verify email exists
    if req.purpose == "reset_password":
        from mitoflow.ai.auth import _get_db as get_auth_db
        db = get_auth_db()
        row = db.execute(
            "SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),)
        ).fetchone()
        db.close()
        if not row:
            # Don't reveal whether email exists — just say code sent
            return {"ok": True, "message": "If the email is registered, a code has been sent."}

    code = store_verification_code(req.email, req.purpose)
    result = send_verification_email(req.email, code, req.purpose)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {
        "ok": True,
        "message": "Verification code sent. Valid for 5 minutes.",
        "dev_code": code if result.get("dev_mode") else None,
    }


@app.post("/api/auth/verify-code")
async def auth_verify_code(req: VerifyCodeRequest):
    """Verify a code (used for email confirmation during registration)."""
    from mitoflow.ai.email_verification import verify_code as check_code
    result = check_code(req.email, req.code, req.purpose)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}


@app.post("/api/auth/forgot-password")
async def auth_forgot_password(req: SendCodeRequest):
    """Send a password reset code to email."""
    req.purpose = "reset_password"
    return await auth_send_code(req)


@app.post("/api/auth/reset-password")
async def auth_reset_password(req: ResetPasswordRequest):
    """Reset password using a reset token or verification code."""
    from mitoflow.ai.email_verification import verify_reset_token, reset_password
    from mitoflow.ai.email_verification import verify_code as check_code
    from mitoflow.ai.auth import get_user_by_token

    # Try reset token first, then verification code
    user_id = verify_reset_token(req.token)
    if not user_id:
        # Could be verification code — need email too
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = reset_password(user_id, req.new_password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}


@app.get("/api/auth/profile")
async def auth_get_profile(authorization: str = Header(None)):
    """Get current user profile."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    from mitoflow.ai.auth import get_user_by_token
    user = get_user_by_token(authorization[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@app.post("/api/auth/profile")
async def auth_update_profile(req: ProfileUpdate, authorization: str = Header(None)):
    """Update user profile (username, institution, role, degree)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    from mitoflow.ai.auth import get_user_by_token, update_profile
    user = get_user_by_token(authorization[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = update_profile(user["id"], data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/auth/change-password")
async def auth_change_password(req: ChangePasswordRequest, authorization: str = Header(None)):
    """Change password after verifying current password."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    from mitoflow.ai.auth import get_user_by_token, change_password
    user = get_user_by_token(authorization[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = change_password(user["id"], req.old_password, req.new_password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── AI Chat Endpoints (/api/ai/*) ────────────────────────────────────

# AI service — initialized on startup; per-request overrides support provider switching
_ai_service = None
_ai_sessions: dict = {}  # session_id -> created timestamp (fast lookup cache)
_ai_store = None  # SQLiteSessionStore — source of truth for list/search/metadata


class ChatRequest(BaseModel):
    """AI chat request — supports all OpenAI/Anthropic-compatible providers."""
    session_id: str
    message: str
    provider: Optional[str] = None  # "openai" | "anthropic" | "fake"
    model: Optional[str] = None
    api_key: Optional[str] = None  # per-request API key override
    base_url: Optional[str] = None  # per-request base URL override


@app.on_event("startup")
def init_ai_service():
    """Initialize default AIService and SQLite session store on server startup."""
    global _ai_service, _ai_store
    sessions_dir = Path(os.getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions"))
    workspace = Path(os.getenv("MITOFLOW_WORKSPACE", "."))
    try:
        from mitoflow.ai.sessions_sqlite import SQLiteSessionStore
        _ai_store = SQLiteSessionStore(sessions_dir)
        from mitoflow.ai.service import AIService
        _ai_service = AIService(session_root=sessions_dir, workspace_root=workspace, store=_ai_store)
    except Exception:
        try:
            from mitoflow.ai.service import AIService
            _ai_service = AIService(session_root=sessions_dir, workspace_root=workspace)
        except Exception as e:
            print(f"Warning: AI service not available: {e}")


def _get_ai_service(provider: Optional[str] = None, model: Optional[str] = None,
                    api_key: Optional[str] = None, base_url: Optional[str] = None) -> "AIService":
    """Get AI service — prefers DeepAgents runtime, falls back to legacy."""
    from mitoflow.ai.service import AIService, build_provider
    if provider is None and model is None and api_key is None and base_url is None:
        if _ai_service is None:
            raise HTTPException(status_code=503, detail="AI service not initialized")
        return _ai_service
    # Per-request provider override
    sessions_dir = Path(os.getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions"))
    workspace = Path(os.getenv("MITOFLOW_WORKSPACE", "."))
    prov, resolved_model = build_provider(provider_name=provider, model=model, api_key=api_key, base_url=base_url)
    from mitoflow.ai.service import build_default_registry
    registry = build_default_registry()
    return AIService(session_root=sessions_dir, workspace_root=workspace, registry=registry, provider=prov, model=resolved_model)


@app.post("/api/ai/sessions")
async def create_ai_session():
    """Create a new AI chat session."""
    import time
    svc = _get_ai_service()
    session_id = svc.create_session()
    _ai_sessions[session_id] = time.time()
    _persist_session(session_id)
    return {"session_id": session_id}


# Session metadata storage: session_id -> {name, pinned, first_message}
import json as _json
_session_meta: dict = {}
_sessions_file = Path(os.getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions")) / "_sessions.json"


def _load_sessions():
    global _ai_sessions, _session_meta
    # Load saved sessions
    if _sessions_file.exists():
        try:
            data = _json.loads(_sessions_file.read_text())
            for s in data.get("sessions", []):
                _ai_sessions[s["id"]] = s.get("created", time.time())
            _session_meta = data.get("meta", {})
        except Exception:
            pass
    # Also scan filesystem for session dirs not in the saved file
    from pathlib import Path as _P
    for d in [_P(PROJECT_ROOT / ".mitoflow_ai_sessions"), _P(PROJECT_ROOT / "mitoflow_workspace")]:
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir() and not sub.name.startswith('.') and not sub.name.startswith('_'):
                    sid = sub.name
                    if sid not in _ai_sessions and len(sid) > 20:  # looks like a UUID
                        _ai_sessions[sid] = sub.stat().st_mtime


def _save_sessions():
    try:
        _sessions_file.parent.mkdir(parents=True, exist_ok=True)
        _sessions_file.write_text(_json.dumps({"sessions": [{"id": s, "created": t} for s, t in _ai_sessions.items()], "meta": _session_meta}))
    except Exception:
        pass


_load_sessions()


def _persist_session(session_id: str):
    """Save session list to disk after changes."""
    _save_sessions()


@app.get("/api/ai/sessions")
async def list_ai_sessions():
    """List all AI chat sessions with metadata (from SQLite store)."""
    if _ai_store is not None:
        sessions = _ai_store.list_sessions()
        return {"sessions": sessions}
    # Fallback to in-memory dict
    result = []
    for sid in _ai_sessions:
        meta = _session_meta.get(sid, {})
        result.append({
            "id": sid,
            "name": meta.get("name", sid[:8] + "..."),
            "first_message": meta.get("first_message", ""),
            "pinned": meta.get("pinned", False),
            "created": _ai_sessions[sid],
        })
    result.sort(key=lambda s: (not s["pinned"], -s["created"]))
    return {"sessions": result}


@app.delete("/api/ai/sessions/{session_id}")
async def delete_ai_session(session_id: str):
    """Delete a session and its data."""
    import shutil
    # SQLite store (source of truth)
    if _ai_store is not None:
        _ai_store.delete_session(session_id)
    # In-memory cache cleanup
    if session_id in _ai_sessions:
        del _ai_sessions[session_id]
    if session_id in _session_meta:
        del _session_meta[session_id]
    _persist_session(session_id)
    # Clean up files
    for d in [PROJECT_ROOT / ".mitoflow_ai_sessions" / session_id, PROJECT_ROOT / "mitoflow_workspace" / session_id]:
        if d.exists():
            shutil.rmtree(str(d), ignore_errors=True)
    return {"ok": True}


@app.patch("/api/ai/sessions/{session_id}")
async def update_session_meta(session_id: str, name: Optional[str] = None, pinned: Optional[bool] = None):
    """Update session name or pin status."""
    if _ai_store is not None:
        ok = _ai_store.set_session_meta(session_id, name=name, pinned=pinned)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True, "name": name, "pinned": pinned}
    # Fallback to in-memory
    if session_id not in _ai_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if session_id not in _session_meta:
        _session_meta[session_id] = {}
    if name is not None:
        _session_meta[session_id]["name"] = name
    if pinned is not None:
        _session_meta[session_id]["pinned"] = pinned
    _persist_session(session_id)
    return {"ok": True, **_session_meta[session_id]}


@app.get("/api/ai/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Load chat history for a session."""
    try:
        from mitoflow.ai.sessions import LocalSessionStore
        store = LocalSessionStore(Path(os.getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions")))
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


@app.get("/api/ai/sessions/{session_id}/results")
async def get_session_results(session_id: str):
    """Browse result directories for a session."""
    from pathlib import Path as _P
    results = []
    # Only check session-specific output directories
    bases = [
        _P(PROJECT_ROOT / ".mitoflow_ai_sessions") / session_id / "artifacts",
        _P(PROJECT_ROOT / "mitoflow_workspace") / session_id,
    ]
    for base in bases:
        if base.exists():
            for d in sorted(base.rglob("*")):
                if d.is_dir():
                    rel_parts = d.relative_to(base).parts
                    if any(p.startswith('.') for p in rel_parts):
                        continue
                    if not rel_parts:
                        continue
                    rel = str(d.relative_to(base))
                    files = [{"name": f.name, "size": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file()][:20]
                    if files:
                        results.append({"path": rel, "files": files, "base": str(base)})
    return {"results": results[:30], "workspace": str(_P(PROJECT_ROOT / "mitoflow_workspace") / session_id)}


@app.get("/api/ai/sessions/{session_id}/results/download")
async def download_result_file(session_id: str, path: str = Query(...)):
    """Download a file from the session's results directories."""
    from pathlib import Path as _P
    allowed = (_P(PROJECT_ROOT / ".mitoflow_ai_sessions") / session_id / "artifacts").resolve()
    target = _safe_path(allowed, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")


@app.post("/api/ai/chat")
async def ai_chat(req: ChatRequest):
    """Send a message to the AI assistant. Supports all OpenAI/Anthropic-compatible APIs."""
    if req.session_id not in _ai_sessions:
        _ai_sessions[req.session_id] = time.time()
    try:
        svc = _get_ai_service(provider=req.provider, model=req.model, api_key=req.api_key, base_url=req.base_url)
        from mitoflow.ai.models import EntryPoint
        result = svc.send_message(req.session_id, req.message, EntryPoint.API)
        # Save first message as session name and persist
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


@app.post("/api/ai/chat/stream")
async def ai_chat_stream(req: ChatRequest):
    """Stream AI response via SSE — typewriter effect + real-time tool calls."""
    import json as _json
    from fastapi.responses import StreamingResponse

    if req.session_id not in _ai_sessions:
        _ai_sessions[req.session_id] = time.time()

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

            ctx = ToolContext(session_id=sid, workspace_root=svc.workspace_root,
                              output_root=store.artifact_dir(sid), entry_point=EntryPoint.API)
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
                            tc = ToolCall(id=chunk.get("id",""), name=chunk["name"], arguments=chunk.get("arguments",{}))
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
            import traceback; traceback.print_exc()
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)[:300]})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@app.get("/api/ai/tools")
async def list_ai_tools():
    """List available AI tools."""
    svc = _get_ai_service()
    from mitoflow.ai.models import EntryPoint
    return {"tools": svc.list_tools(EntryPoint.API)}


# ── File Upload & Workspace ──────────────────────────────────────────
WORKSPACE_ROOT = Path(os.getenv("MITOFLOW_WORKSPACE", PROJECT_ROOT / "mitoflow_workspace")).resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS_UPLOAD = {
    ".fasta", ".fa", ".fas", ".fna", ".fq", ".fastq", ".fq.gz", ".fastq.gz",
    ".gb", ".gbk", ".gbff", ".gff", ".gff3", ".gtf",
    ".vcf", ".bam", ".bai", ".sam",
    ".csv", ".tsv", ".txt",
    ".nwk", ".treefile", ".tre", ".phylip", ".phy",
    ".zip", ".tar.gz", ".tar.bz2",
    ".png", ".jpg", ".svg", ".pdf",
}


@app.post("/api/files/upload")
async def upload_files(files: list[UploadFile] = File(...), session_id: str = Form("default")):
    """Upload one or more files to the workspace."""
    session_dir = WORKSPACE_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    uploaded = []
    errors = []
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS_UPLOAD and not any(f.filename.endswith(x) for x in ['.tar.gz','.tar.bz2','.fq.gz','.fastq.gz']):
            errors.append(f"{f.filename}: unsupported type")
            continue
        dest = session_dir / f.filename
        content = await f.read()
        if len(content) > MAX_UPLOAD_SIZE:
            errors.append(f"{f.filename}: file too large (max {MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
            continue
        dest.write_bytes(content)
        uploaded.append({"name": f.filename, "size": len(content), "type": ext})
    return {"uploaded": uploaded, "errors": errors, "session_id": session_id, "workspace": str(session_dir)}


@app.get("/api/files/list")
async def list_files(session_id: str = Query("default")):
    """List files in the workspace."""
    session_dir = WORKSPACE_ROOT / session_id
    if not session_dir.exists():
        return {"files": [], "workspace": str(session_dir)}
    files = []
    for p in sorted(session_dir.iterdir()):
        if p.is_file():
            stat = p.stat()
            files.append({
                "name": p.name, "size": stat.st_size,
                "modified": stat.st_mtime,
                "type": p.suffix.lower(),
            })
    return {"files": files, "workspace": str(session_dir)}


@app.get("/api/files/download/{filename:path}")
async def download_file(filename: str, session_id: str = Query("default")):
    """Download a file from the workspace."""
    session_dir = WORKSPACE_ROOT / session_id
    target = _safe_path(session_dir, filename)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")


@app.delete("/api/files/{filename:path}")
async def delete_file(filename: str, session_id: str = Query("default")):
    """Delete a file from the workspace."""
    session_dir = WORKSPACE_ROOT / session_id
    target = _safe_path(session_dir, filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    target.unlink()
    return {"deleted": filename}


# ── Static files ────────────────────────────────────────────────────
import mimetypes

@app.get("/logo.png")
async def serve_logo():
    """Serve the MitoFlow logo."""
    logo_path = Path(__file__).parent.parent.parent.parent / "LOGO.png"
    if not logo_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path=str(logo_path), media_type="image/png")


# ── Vite SPA Static Files ────────────────────────────────────────────
DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve the Vue SPA (falls back to index.html for all non-API routes)."""
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    # Fallback to legacy HTML if dist not built yet
    from .chat_ui import CHAT_HTML
    return HTMLResponse(CHAT_HTML)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
