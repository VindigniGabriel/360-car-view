"""
Frame extraction module.
Extracts N equidistant frames from a video file.
"""
import os
import subprocess
import json
from typing import Tuple, List


def get_video_info(video_path: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"ffprobe failed: {result.stderr}")
    
    return json.loads(result.stdout)


def get_frame_count(video_path: str) -> int:
    """Get total number of frames in video."""
    info = get_video_info(video_path)
    
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            # Try nb_frames first
            if "nb_frames" in stream:
                return int(stream["nb_frames"])
            
            # Calculate from duration and fps
            duration = float(info.get("format", {}).get("duration", 0))
            fps_parts = stream.get("r_frame_rate", "30/1").split("/")
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30
            return int(duration * fps)
    
    raise Exception("Could not determine frame count")


def get_video_dimensions(video_path: str) -> Tuple[int, int]:
    """Get video width and height."""
    info = get_video_info(video_path)
    
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream.get("width", 1920), stream.get("height", 1080)
    
    return 1920, 1080


def extract_frames(
    video_path: str,
    output_dir: str,
    num_frames: int = 36,
    output_width: int = 800,
) -> Tuple[List[str], int, int]:
    """
    Extract N equidistant frames from a video.
    
    Args:
        video_path: Path to input video
        output_dir: Directory to save frames
        num_frames: Number of frames to extract (24, 36, or 72)
        output_width: Width of output frames (height auto-calculated)
    
    Returns:
        Tuple of (list of frame paths, frame width, frame height)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video info
    total_frames = get_frame_count(video_path)
    orig_width, orig_height = get_video_dimensions(video_path)
    
    # Calculate output dimensions maintaining aspect ratio
    aspect_ratio = orig_height / orig_width
    output_height = int(output_width * aspect_ratio)
    # Ensure even dimensions for video codecs
    output_height = output_height + (output_height % 2)
    
    # Calculate frame interval
    frame_interval = total_frames / num_frames
    
    frame_paths = []
    
    for i in range(num_frames):
        frame_number = int(i * frame_interval)
        output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        
        # Use ffmpeg to extract specific frame
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vf", f"select=eq(n\\,{frame_number}),scale={output_width}:{output_height}",
            "-vframes", "1",
            "-q:v", "2",
            output_path,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: Failed to extract frame {i}: {result.stderr}")
            continue
        
        if os.path.exists(output_path):
            frame_paths.append(output_path)
    
    if not frame_paths:
        raise Exception("No frames were extracted from the video")
    
    return frame_paths, output_width, output_height


def extract_all_frames(
    video_path: str,
    output_dir: str,
    fps: int = None,
) -> Tuple[List[str], int, int]:
    """
    Extract all frames from a video (or at specified FPS).
    
    Args:
        video_path: Path to input video
        output_dir: Directory to save frames
        fps: Frames per second to extract (None = all frames)
    
    Returns:
        Tuple of (list of frame paths, frame width, frame height)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    orig_width, orig_height = get_video_dimensions(video_path)
    
    # Build ffmpeg command
    if fps:
        vf_filter = f"fps={fps}"
    else:
        vf_filter = None
    
    output_pattern = os.path.join(output_dir, "frame_%05d.jpg")
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
    ]
    
    if vf_filter:
        cmd.extend(["-vf", vf_filter])
    
    cmd.extend([
        "-q:v", "2",
        output_pattern,
    ])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: FFmpeg extraction issue: {result.stderr}")
    
    # Collect extracted frames
    frame_paths = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.endswith(".jpg")
    ])
    
    if not frame_paths:
        raise Exception("No frames were extracted from the video")
    
    return frame_paths, orig_width, orig_height
