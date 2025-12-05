import json
import os
import time
from datetime import datetime

import redis

from .celery_app import celery_app
from .pipeline.extractor import extract_frames
from .pipeline.stabilizer import stabilize_video, check_vidstab_available
from .pipeline.detector import VehicleDetector, detect_vehicles_in_frames
from .pipeline.normalizer import normalize_frames
from .pipeline.frame_aligner import align_to_center_mass
from .pipeline.loop_validator import find_best_loop_point, validate_loop
from .pipeline.sprite_builder import build_sprite_sheet
from .pipeline.viewer_generator import generate_viewer
from .pipeline.image_optimizer import batch_optimize, create_webp_sprite
from .pipeline.background_remover import remove_background_batch, create_transparent_sprite
from .pipeline.cache import model_cache


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
def process_video(self, task_id: str, num_frames: int = 36, remove_bg: bool = False):
    """
    Main task to process a walk-around video into a 360° spin viewer.
    
    Full Pipeline:
    1. Download video from MinIO
    2. Stabilize video (vidstab)
    3. Extract frames at regular intervals
    4. Detect vehicles (YOLOv8)
    5. Normalize frames (crop, center, resize)
    6. Optimize to WebP
    7. Remove background (optional)
    8. Build sprite sheet
    9. Generate viewer HTML
    10. Upload results to MinIO
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
        
        # Step 3: Extract more frames than needed for loop optimization
        frames_dir = os.path.join(task_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Extract 20% more frames to find best loop point
        extract_count = int(num_frames * 1.2)
        frame_paths, orig_width, orig_height = extract_frames(
            stabilized_path, frames_dir, extract_count, output_width=800
        )
        update_task_status(task_id, "PROCESSING", 45, "optimizing_loop")
        
        # Find best loop point (frames where last is similar to first)
        frame_paths, _ = find_best_loop_point(frame_paths, num_frames)
        
        # Validate loop quality
        is_valid_loop, similarity = validate_loop(frame_paths)
        print(f"Loop validation: valid={is_valid_loop}, similarity={similarity:.3f}")
        
        update_task_status(task_id, "PROCESSING", 50, "detecting")
        
        # Step 4: Detect vehicles in frames for centering
        detector = VehicleDetector()
        detections = detect_vehicles_in_frames(frame_paths, detector)
        
        update_task_status(task_id, "PROCESSING", 60, "normalizing")
        
        # Use extracted frames directly
        selected_paths = frame_paths
        selected_detections = detections
        
        # Step 6: Align frames to keep car centered
        aligned_dir = os.path.join(task_dir, "aligned")
        aligned_paths = align_to_center_mass(selected_paths, aligned_dir, selected_detections)
        update_task_status(task_id, "PROCESSING", 65, "normalizing")
        
        # Step 7: Normalize frames
        normalized_dir = os.path.join(task_dir, "normalized")
        frame_width, frame_height = 800, 600
        normalized_paths = normalize_frames(
            aligned_paths,
            selected_detections,
            normalized_dir,
            output_size=(frame_width, frame_height),
        )
        update_task_status(task_id, "PROCESSING", 70, "optimizing")
        
        # Step 7: Remove background if requested
        if remove_bg:
            update_task_status(task_id, "PROCESSING", 72, "removing_background")
            nobg_dir = os.path.join(task_dir, "nobg")
            final_paths = remove_background_batch(normalized_paths, nobg_dir)
            sprite_format = "png"
            content_type = "image/png"
        else:
            # Optimize frames to WebP
            optimized_dir = os.path.join(task_dir, "optimized")
            final_paths = batch_optimize(
                normalized_paths,
                optimized_dir,
                format="webp",
                quality=85,
            )
            sprite_format = "webp"
            content_type = "image/webp"
        
        update_task_status(task_id, "PROCESSING", 80, "building")
        
        # Step 8: Build sprite sheet
        if remove_bg:
            sprite_path = os.path.join(task_dir, "sprite.png")
            sprite_path, sprite_meta = create_transparent_sprite(final_paths, sprite_path)
        else:
            sprite_path = os.path.join(task_dir, "sprite.webp")
            sprite_path, sprite_meta = create_webp_sprite(final_paths, sprite_path, quality=80)
        
        update_task_status(task_id, "PROCESSING", 88, "building")
        
        # Step 9: Generate viewer HTML
        viewer_path = os.path.join(task_dir, "viewer.html")
        generate_viewer(
            viewer_path, 
            num_frames, 
            frame_width, 
            frame_height, 
            use_webp=(not remove_bg),
            transparent=remove_bg,
        )
        update_task_status(task_id, "PROCESSING", 92, "uploading")
        
        # Step 10: Upload results to MinIO
        # Upload frames
        for i, frame_path in enumerate(final_paths):
            frame_name = os.path.basename(frame_path)
            minio_client.fput_object(
                bucket,
                f"{task_id}/frames/{frame_name}",
                frame_path,
                content_type=content_type,
            )
        
        # Upload sprite
        sprite_filename = f"sprite.{sprite_format}"
        minio_client.fput_object(
            bucket,
            f"{task_id}/{sprite_filename}",
            sprite_path,
            content_type=content_type,
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
            "total_frames": len(frame_paths),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "processing_time_seconds": round(processing_time, 2),
            "format": sprite_format,
            "transparent": remove_bg,
            "sprite_columns": sprite_meta.get("columns", 6),
            "sprite_rows": sprite_meta.get("rows", 6),
            "loop_valid": is_valid_loop,
            "loop_similarity": round(similarity, 3),
        }
        update_task_status(task_id, "SUCCESS", 100, "completed", metadata=metadata)
        
        # Record metrics
        try:
            from api.metrics import metrics
            metrics.record_processing(task_id, processing_time, num_frames, success=True)
        except Exception:
            pass
        
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
