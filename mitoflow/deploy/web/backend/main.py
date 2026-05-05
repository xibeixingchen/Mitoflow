"""MitoFlow Web API - FastAPI Backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .config import PROJECT_ROOT
from .state import state
from .routes import core, auth, ai, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize AI service and session store on startup."""
    sessions_dir = Path(os.getenv("MITOFLOW_SESSIONS_DIR", ".mitoflow_ai_sessions"))
    workspace = Path(os.getenv("MITOFLOW_WORKSPACE", "."))
    try:
        from mitoflow.ai.sessions_sqlite import SQLiteSessionStore
        state.ai_store = SQLiteSessionStore(sessions_dir)
        from mitoflow.ai.service import AIService
        state.ai_service = AIService(session_root=sessions_dir, workspace_root=workspace, store=state.ai_store)
    except Exception:
        try:
            from mitoflow.ai.service import AIService
            state.ai_service = AIService(session_root=sessions_dir, workspace_root=workspace)
        except Exception as e:
            print(f"Warning: AI service not available: {e}")
    ai._load_sessions()
    yield


app = FastAPI(
    title="MitoFlow Web",
    description="Plant Mitochondrial Genome Annotation Web Service + AI Assistant",
    version="0.2.0",
    lifespan=lifespan,
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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limit incoming requests by IP and path category."""
    from mitoflow.ai.rate_limiter import get_rate_limiter
    limiter = get_rate_limiter()

    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

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


# Register route modules
app.include_router(core.router)
app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(files.router)


# ── Static files ────────────────────────────────────────────────────
DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


@app.get("/logo.png")
async def serve_logo():
    """Serve the MitoFlow logo."""
    logo_path = PROJECT_ROOT / "LOGO.png"
    if not logo_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path=str(logo_path), media_type="image/png")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve the Vue SPA (falls back to index.html for all non-API routes)."""
    index_file = DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>MitoFlow Web</h1><p>Frontend not built. Run <code>npm run build</code> in deploy/web/frontend/</p>")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
