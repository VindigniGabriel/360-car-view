import json
import os
import time
from datetime import datetime

import redis

from .celery_app import celery_app
from .pipeline.extractor import extract_frames, extract_all_frames
from .pipeline.stabilizer import stabilize_video, check_vidstab_available
from .pipeline.detector import VehicleDetector, detect_vehicles_in_frames
from .pipeline.normalizer import normalize_frames
from .pipeline.angle_estimator import select_frames_by_angle
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
    
    Full Pipeline:
    1. Download video from MinIO
    2. Stabilize video (vidstab)
    3. Extract all frames
    4. Detect vehicles (YOLOv8)
    5. Select frames by angle
    6. Normalize frames (crop, center, resize)
    7. Build sprite sheet
    8. Generate viewer HTML
    9. Upload results to MinIO
    """
    start_time = time.time()
    temp_dir = os.getenv("TEMP_DIR", "/app/temp")
    task_dir = os.path.join(temp_dir, task_id)
    bucket = os.getenv("MINIO_BUCKET", "car360")
    
    try:
        os.makedirs(task_dir, exist_ok=True)
        
        # Update status: PROCESSING
        update_task_status(task_id, "PROCESSING", 5, "stabilizing")
        
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
        update_task_status(task_id, "PROCESSING", 10, "stabilizing")
        
        # Step 2: Stabilize video
        stabilized_path = os.path.join(task_dir, f"stabilized.{video_ext}")
        if check_vidstab_available():
            stabilize_video(video_path, stabilized_path)
        else:
            # Skip stabilization if vidstab not available
            stabilized_path = video_path
        update_task_status(task_id, "PROCESSING", 25, "extracting")
        
        # Step 3: Extract ALL frames for analysis
        all_frames_dir = os.path.join(task_dir, "all_frames")
        os.makedirs(all_frames_dir, exist_ok=True)
        
        all_frame_paths, orig_width, orig_height = extract_all_frames(
            stabilized_path, all_frames_dir
        )
        update_task_status(task_id, "PROCESSING", 35, "detecting")
        
        # Step 4: Detect vehicles in frames (sample for speed)
        detector = VehicleDetector()
        sample_rate = max(1, len(all_frame_paths) // 50)  # Sample ~50 frames
        sampled_paths = all_frame_paths[::sample_rate]
        detections = detect_vehicles_in_frames(sampled_paths, detector)
        
        # Expand detections to all frames
        full_detections = []
        for i, path in enumerate(all_frame_paths):
            sample_idx = i // sample_rate
            if sample_idx < len(detections):
                full_detections.append(detections[sample_idx])
            else:
                full_detections.append(detections[-1] if detections else None)
        
        update_task_status(task_id, "PROCESSING", 50, "extracting")
        
        # Step 5: Select frames by angle
        selected_paths = select_frames_by_angle(all_frame_paths, num_frames)
        
        # Get detections for selected frames
        selected_detections = []
        for path in selected_paths:
            idx = all_frame_paths.index(path) if path in all_frame_paths else 0
            selected_detections.append(full_detections[idx] if idx < len(full_detections) else None)
        
        update_task_status(task_id, "PROCESSING", 60, "normalizing")
        
        # Step 6: Normalize frames
        normalized_dir = os.path.join(task_dir, "normalized")
        frame_width, frame_height = 800, 600
        normalized_paths = normalize_frames(
            selected_paths,
            selected_detections,
            normalized_dir,
            output_size=(frame_width, frame_height),
        )
        update_task_status(task_id, "PROCESSING", 75, "building")
        
        # Step 7: Build sprite sheet
        sprite_path = os.path.join(task_dir, "sprite.jpg")
        build_sprite_sheet(normalized_paths, sprite_path, num_frames)
        update_task_status(task_id, "PROCESSING", 85, "building")
        
        # Step 8: Generate viewer HTML
        viewer_path = os.path.join(task_dir, "viewer.html")
        generate_viewer(viewer_path, num_frames, frame_width, frame_height)
        update_task_status(task_id, "PROCESSING", 90, "uploading")
        
        # Step 9: Upload results to MinIO
        # Upload normalized frames
        for i, frame_path in enumerate(normalized_paths):
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
