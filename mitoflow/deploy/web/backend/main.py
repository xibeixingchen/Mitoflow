"""MitoFlow Web API - FastAPI Backend."""

from __future__ import annotations
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(
    title="MitoFlow Web",
    description="Plant Mitochondrial Genome Annotation Web Service",
    version="0.1.0",
)

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = Path("/app/uploads")
RESULTS_DIR = Path("/app/results")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".fasta",".fa",".fas",".fna"}

UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

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


def run_annotation_task(task_id: str, input_path: Path, output_dir: Path, params: dict):
    """Background task to run MitoFlow annotation."""
    try:
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "Starting annotation pipeline..."
        
        # Import and run MitoFlow pipeline
        import sys
        sys.path.insert(0, "/app/src")
        
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
