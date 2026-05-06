"""File upload and workspace management routes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..config import ALLOWED_EXTENSIONS_UPLOAD, MAX_UPLOAD_SIZE, WORKSPACE_ROOT, safe_path
from ..state import state
from .auth import _require_auth

router = APIRouter()


def _require_session_ownership(session_id: str, user: dict) -> None:
    """Raise 404 if user does not own session_id (mirrors ai.py policy).

    Orphan sessions (owner=None) are not accessible to any user.
    """
    if state.ai_store is None:
        return
    if not state.ai_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    owner = state.ai_store.get_session_owner(session_id)
    if owner is None or owner != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")


def _claim_or_check_session(session_id: str, user: dict) -> None:
    """Attach orphan or unknown session to user; reject if owned by someone else.

    Used by upload, where a brand-new session_id may not yet exist in ai_store.
    """
    if state.ai_store is None:
        return
    owner = state.ai_store.get_session_owner(session_id)
    if owner is None:
        if state.ai_store.session_exists(session_id):
            state.ai_store.claim_session(session_id, user["id"])
        else:
            state.ai_store.create_session(session_id=session_id, user_id=user["id"])
        return
    if owner != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/api/files/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    session_id: str = Form("default"),
    authorization: str = Header(None),
):
    """Upload one or more files to the workspace."""
    user = _require_auth(authorization)
    _claim_or_check_session(session_id, user)
    session_dir = WORKSPACE_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    uploaded = []
    errors = []
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS_UPLOAD and not any(
            f.filename.endswith(x) for x in [".tar.gz", ".tar.bz2", ".fq.gz", ".fastq.gz"]
        ):
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


@router.get("/api/files/list")
async def list_files(
    session_id: str = Query("default"),
    authorization: str = Header(None),
):
    """List user-uploaded files in the workspace (top-level only, excludes subdirs like viz/)."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    session_dir = WORKSPACE_ROOT / session_id
    if not session_dir.exists():
        return {"files": [], "workspace": str(session_dir)}
    files = []
    for p in sorted(session_dir.iterdir()):
        if p.is_file():
            stat = p.stat()
            files.append({
                "name": p.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "type": p.suffix.lower(),
            })
    return {"files": files, "workspace": str(session_dir)}


@router.get("/api/files/all")
async def list_all_files(authorization: str = Header(None)):
    """List files across all session workspaces owned by the current user."""
    user = _require_auth(authorization)
    sessions: list[dict] = []
    if not WORKSPACE_ROOT.exists():
        return {"sessions": sessions}
    for session_dir in sorted(WORKSPACE_ROOT.iterdir()):
        if not session_dir.is_dir():
            continue
        sid = session_dir.name
        # Skip sessions not owned by this user (and skip orphans).
        if state.ai_store is not None:
            owner = state.ai_store.get_session_owner(sid)
            if owner is None or owner != user["id"]:
                continue
        files = []
        for p in sorted(session_dir.iterdir()):
            if p.is_file():
                stat = p.stat()
                files.append({
                    "name": p.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": p.suffix.lower(),
                })
        if files:
            sessions.append({
                "session_id": sid,
                "files": files,
            })
    return {"sessions": sessions}


@router.get("/api/files/download/{filename:path}")
async def download_file(
    filename: str,
    session_id: str = Query("default"),
    authorization: str = Header(None),
):
    """Download a file from the workspace."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    session_dir = WORKSPACE_ROOT / session_id
    target = safe_path(session_dir, filename)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")


@router.delete("/api/files/{filename:path}")
async def delete_file(
    filename: str,
    session_id: str = Query("default"),
    authorization: str = Header(None),
):
    """Delete a file from the workspace."""
    user = _require_auth(authorization)
    _require_session_ownership(session_id, user)
    session_dir = WORKSPACE_ROOT / session_id
    target = safe_path(session_dir, filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    target.unlink()
    return {"deleted": filename}


@router.post("/api/files/copy")
async def copy_files(
    source_session_id: str = Form(...),
    target_session_id: str = Form(...),
    filenames: str = Form("[]"),
    authorization: str = Header(None),
):
    """Copy files from one session workspace to another. Caller must own both."""
    user = _require_auth(authorization)
    _require_session_ownership(source_session_id, user)
    _claim_or_check_session(target_session_id, user)
    names = json.loads(filenames)
    if not names:
        return {"copied": [], "errors": ["No filenames provided"]}
    src_dir = WORKSPACE_ROOT / source_session_id
    dst_dir = WORKSPACE_ROOT / target_session_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict] = []
    errors: list[str] = []
    for name in names:
        src = safe_path(src_dir, name)
        if not src.exists() or not src.is_file():
            errors.append(f"{name}: not found in source session")
            continue
        dst = dst_dir / name
        shutil.copy2(str(src), str(dst))
        copied.append({"name": name, "size": dst.stat().st_size})
    return {"copied": copied, "errors": errors}
