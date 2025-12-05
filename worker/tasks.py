import json
import os
import time
from datetime import datetime

import redis

from .celery_app import celery_app
from .pipeline.extractor import extract_frames
from .pipeline.sprite_builder import build_sprite_sheet
from .pipeline.viewer_generator import generate_viewer


def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


def update_task_status(task_id: str, status: str, progress: int, step: str, error: str = None, metadata: dict = None):
    """Update task status in Redis."""
    client = get_redis_client()
    task_data = client.get(f"task:{task_id}")
    
    if task_data:
        task = json.loads(task_data)
        task["status"] = status
        task["progress"] = progress
        task["step"] = step
        if error:
            task["error"] = error
        if metadata:
            task["metadata"] = metadata
        client.set(f"task:{task_id}", json.dumps(task))


def get_minio_client():
    from minio import Minio
    
    return Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
        secure=False,
    )


@celery_app.task(bind=True, name="process_video")
def process_video(self, task_id: str, num_frames: int = 36):
    """
    Main task to process a walk-around video into a 360° spin viewer.
    
    Pipeline:
    1. Download video from MinIO
    2. Extract frames
    3. Build sprite sheet
    4. Generate viewer HTML
    5. Upload results to MinIO
    """
    start_time = time.time()
    temp_dir = os.getenv("TEMP_DIR", "/app/temp")
    task_dir = os.path.join(temp_dir, task_id)
    bucket = os.getenv("MINIO_BUCKET", "car360")
    
    try:
        os.makedirs(task_dir, exist_ok=True)
        
        # Update status: PROCESSING
        update_task_status(task_id, "PROCESSING", 5, "extracting")
        
        # Step 1: Download video from MinIO
        minio_client = get_minio_client()
        
        # Find the original video
        objects = list(minio_client.list_objects(bucket, prefix=f"{task_id}/original"))
        if not objects:
            raise Exception("Original video not found in storage")
        
        video_object = objects[0].object_name
        video_ext = video_object.split(".")[-1]
        video_path = os.path.join(task_dir, f"original.{video_ext}")
        
        minio_client.fget_object(bucket, video_object, video_path)
        update_task_status(task_id, "PROCESSING", 15, "extracting")
        
        # Step 2: Extract frames
        frames_dir = os.path.join(task_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        frame_paths, frame_width, frame_height = extract_frames(
            video_path, frames_dir, num_frames
        )
        update_task_status(task_id, "PROCESSING", 50, "building")
        
        # Step 3: Build sprite sheet
        sprite_path = os.path.join(task_dir, "sprite.jpg")
        build_sprite_sheet(frame_paths, sprite_path, num_frames)
        update_task_status(task_id, "PROCESSING", 75, "building")
        
        # Step 4: Generate viewer HTML
        viewer_path = os.path.join(task_dir, "viewer.html")
        generate_viewer(viewer_path, num_frames, frame_width, frame_height)
        update_task_status(task_id, "PROCESSING", 85, "uploading")
        
        # Step 5: Upload results to MinIO
        # Upload frames
        for i, frame_path in enumerate(frame_paths):
            frame_name = os.path.basename(frame_path)
            minio_client.fput_object(
                bucket,
                f"{task_id}/frames/{frame_name}",
                frame_path,
                content_type="image/jpeg",
            )
        
        # Upload sprite
        minio_client.fput_object(
            bucket,
            f"{task_id}/sprite.jpg",
            sprite_path,
            content_type="image/jpeg",
        )
        
        # Upload viewer
        minio_client.fput_object(
            bucket,
            f"{task_id}/viewer.html",
            viewer_path,
            content_type="text/html",
        )
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Update status: SUCCESS
        metadata = {
            "total_frames": num_frames,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "processing_time_seconds": round(processing_time, 2),
        }
        update_task_status(task_id, "SUCCESS", 100, "completed", metadata=metadata)
        
        # Cleanup temp files
        import shutil
        shutil.rmtree(task_dir, ignore_errors=True)
        
        return {"task_id": task_id, "status": "SUCCESS", "metadata": metadata}
        
    except Exception as e:
        update_task_status(task_id, "FAILURE", 0, "error", error=str(e))
        
        # Cleanup on failure
        import shutil
        shutil.rmtree(task_dir, ignore_errors=True)
        
        raise
