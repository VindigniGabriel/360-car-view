from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import json
from datetime import datetime
from typing import Optional

from .config import get_settings, Settings
from .schemas import (
    VideoUploadResponse,
    TaskStatusResponse,
    TaskResultResponse,
    HealthResponse,
    TaskStatus,
    ProcessingStep,
    FrameCount,
)
from .dependencies import get_minio_client, get_redis_client

app = FastAPI(
    title="Car 360 Spin Viewer API",
    description="API that converts walk-around videos into interactive 360° spin viewers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get processing metrics and statistics."""
    from .metrics import metrics
    return metrics.get_stats()


@app.get("/api/v1/metrics/history")
async def get_metrics_history(limit: int = 10):
    """Get recent processing history."""
    from .metrics import metrics
    return {"history": metrics.get_recent_history(limit)}


@app.post("/api/v1/videos", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    frames: int = Form(default=36),
    settings: Settings = Depends(get_settings),
):
    """
    Upload a walk-around video for processing.
    
    - **file**: Video file (mp4, mov, avi)
    - **frames**: Number of frames to extract (24, 36, or 72)
    """
    # Validate frames
    if frames not in [24, 36, 72]:
        raise HTTPException(
            status_code=400,
            detail="frames must be 24, 36, or 72"
        )
    
    # Validate file extension
    if file.filename:
        ext = file.filename.split(".")[-1].lower()
        if ext not in settings.allowed_extensions_list:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {settings.allowed_extensions}"
            )
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > settings.max_video_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_video_size_mb}MB"
        )
    
    # Upload to MinIO
    try:
        minio_client = get_minio_client()
        from io import BytesIO
        
        object_name = f"{task_id}/original.{ext}"
        minio_client.put_object(
            settings.minio_bucket,
            object_name,
            BytesIO(content),
            len(content),
            content_type=file.content_type or "video/mp4",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload video: {str(e)}"
        )
    
    # Store task metadata in Redis
    try:
        redis_client = get_redis_client()
        task_data = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "progress": 0,
            "step": ProcessingStep.UPLOADING.value,
            "frames": frames,
            "original_filename": file.filename,
            "object_name": object_name,
            "created_at": datetime.utcnow().isoformat(),
            "error": None,
        }
        redis_client.set(f"task:{task_id}", json.dumps(task_data))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create task: {str(e)}"
        )
    
    # Send task to Celery
    try:
        from worker.tasks import process_video
        process_video.delay(task_id, frames)
    except Exception as e:
        # Update task status to failed
        task_data["status"] = TaskStatus.FAILURE.value
        task_data["error"] = f"Failed to queue task: {str(e)}"
        redis_client.set(f"task:{task_id}", json.dumps(task_data))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue processing task: {str(e)}"
        )
    
    return VideoUploadResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Video uploaded successfully. Processing started.",
    )


@app.get("/api/v1/videos/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the processing status of a video task."""
    redis_client = get_redis_client()
    
    task_data = redis_client.get(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = json.loads(task_data)
    
    return TaskStatusResponse(
        task_id=task["task_id"],
        status=TaskStatus(task["status"]),
        progress=task.get("progress", 0),
        step=ProcessingStep(task["step"]) if task.get("step") else None,
        created_at=datetime.fromisoformat(task["created_at"]),
        error=task.get("error"),
    )


@app.get("/api/v1/videos/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(task_id: str):
    """Get the result of a completed video processing task."""
    redis_client = get_redis_client()
    settings = get_settings()
    
    task_data = redis_client.get(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = json.loads(task_data)
    
    if task["status"] != TaskStatus.SUCCESS.value:
        return TaskResultResponse(
            task_id=task_id,
            status=TaskStatus(task["status"]),
            error=task.get("error"),
        )
    
    # Build result URLs
    base_url = f"http://{settings.minio_endpoint}/{settings.minio_bucket}/{task_id}"
    
    return TaskResultResponse(
        task_id=task_id,
        status=TaskStatus.SUCCESS,
        result={
            "viewer_url": f"{base_url}/viewer.html",
            "sprite_url": f"{base_url}/sprite.jpg",
            "frames_url": f"{base_url}/frames/",
            "metadata": task.get("metadata", {}),
        },
    )


@app.delete("/api/v1/videos/{task_id}")
async def delete_task(task_id: str):
    """Delete a video task and its associated files."""
    redis_client = get_redis_client()
    minio_client = get_minio_client()
    settings = get_settings()
    
    task_data = redis_client.get(f"task:{task_id}")
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Delete from MinIO
    try:
        objects = minio_client.list_objects(
            settings.minio_bucket,
            prefix=f"{task_id}/",
            recursive=True,
        )
        for obj in objects:
            minio_client.remove_object(settings.minio_bucket, obj.object_name)
    except Exception as e:
        print(f"Failed to delete MinIO objects: {e}")
    
    # Delete from Redis
    redis_client.delete(f"task:{task_id}")
    
    return {"message": "Task deleted successfully"}
