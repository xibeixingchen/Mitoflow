"""Core annotation and task management routes."""

from __future__ import annotations

import os
import shutil
import sys
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, PROJECT_ROOT, RESULTS_DIR, UPLOAD_DIR
from ..state import state

router = APIRouter()


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


def run_annotation_task(task_id: str, input_path: Path, output_dir: Path, params: dict):
    """Background task to run MitoFlow annotation."""
    try:
        state.tasks[task_id]["status"] = "running"
        state.tasks[task_id]["progress"] = 10
        state.tasks[task_id]["message"] = "Starting annotation pipeline..."

        src_path = os.getenv("MITOFLOW_SRC_PATH", os.getcwd())
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        from mitoflow.core.pipeline import AnnotationPipeline
        from mitoflow.core.input import load_fasta

        state.tasks[task_id]["progress"] = 20
        state.tasks[task_id]["message"] = "Loading genome..."

        genome = load_fasta(str(input_path))
        state.tasks[task_id]["progress"] = 30
        state.tasks[task_id]["message"] = "Running annotation..."

        pipeline = AnnotationPipeline(
            genome=genome,
            output_dir=str(output_dir),
            name=params["name"],
            threads=params["threads"],
            skip_trna=params["skip_trna"],
            skip_rrna=params["skip_rrna"],
            skip_qc=params["skip_qc"],
        )
        result = pipeline.run()

        state.tasks[task_id]["progress"] = 90
        state.tasks[task_id]["message"] = "Generating outputs..."

        state.tasks[task_id]["progress"] = 100
        state.tasks[task_id]["status"] = "completed"
        state.tasks[task_id]["message"] = "Annotation completed successfully"
        state.tasks[task_id]["result_url"] = f"/api/results/{task_id}/download"

    except Exception as e:
        state.tasks[task_id]["status"] = "failed"
        state.tasks[task_id]["message"] = f"Error: {str(e)}"
        raise


@router.post("/api/annotate", response_model=TaskStatus)
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
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    task_id = str(uuid.uuid4())
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    input_path = task_dir / f"input{file_ext}"
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")
    with open(input_path, "wb") as f:
        f.write(content)

    if not validate_fasta_file(input_path):
        raise HTTPException(status_code=400, detail="Invalid FASTA file")

    output_dir = RESULTS_DIR / task_id
    output_dir.mkdir(exist_ok=True)

    state.tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task queued...",
        "result_url": None,
        "output_dir": str(output_dir),
    }

    params = {
        "name": name,
        "threads": min(threads, 8),
        "skip_trna": skip_trna,
        "skip_rrna": skip_rrna,
        "skip_qc": skip_qc,
    }
    background_tasks.add_task(run_annotation_task, task_id, input_path, output_dir, params)
    return TaskStatus(**state.tasks[task_id])


@router.get("/api/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get task status and progress."""
    if task_id not in state.tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(**state.tasks[task_id])


@router.get("/api/results/{task_id}/download")
async def download_task_result(task_id: str):
    """Download annotation results as a zip file."""
    if task_id not in state.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = state.tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    output_dir = Path(task["output_dir"])
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Results not found")

    import tempfile
    zip_path = Path(tempfile.gettempdir()) / f"mitoflow_{task_id}.zip"
    shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", output_dir)

    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(zip_path),
        filename=f"mitoflow_results_{task_id}.zip",
        media_type="application/zip",
    )


@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.2.0"}


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its data."""
    if task_id not in state.tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    upload_dir = UPLOAD_DIR / task_id
    result_dir = RESULTS_DIR / task_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    if result_dir.exists():
        shutil.rmtree(result_dir)

    del state.tasks[task_id]
    return {"message": "Task deleted successfully"}
