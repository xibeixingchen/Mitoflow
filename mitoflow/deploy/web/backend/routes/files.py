"""File upload and workspace management routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..config import ALLOWED_EXTENSIONS_UPLOAD, MAX_UPLOAD_SIZE, WORKSPACE_ROOT, safe_path

router = APIRouter()


@router.post("/api/files/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    session_id: str = Form("default"),
):
    """Upload one or more files to the workspace."""
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
                "name": p.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "type": p.suffix.lower(),
            })
    return {"files": files, "workspace": str(session_dir)}


@router.get("/api/files/download/{filename:path}")
async def download_file(filename: str, session_id: str = Query("default")):
    """Download a file from the workspace."""
    session_dir = WORKSPACE_ROOT / session_id
    target = safe_path(session_dir, filename)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(target), filename=target.name, media_type="application/octet-stream")


@router.delete("/api/files/{filename:path}")
async def delete_file(filename: str, session_id: str = Query("default")):
    """Delete a file from the workspace."""
    session_dir = WORKSPACE_ROOT / session_id
    target = safe_path(session_dir, filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    target.unlink()
    return {"deleted": filename}
