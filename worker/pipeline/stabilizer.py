"""
Video stabilization module using FFmpeg vidstab.
Stabilizes shaky walk-around footage for smoother 360° viewing.
"""
import os
import subprocess
import tempfile
from typing import Optional


def stabilize_video(
    input_path: str,
    output_path: str,
    shakiness: int = 5,
    accuracy: int = 15,
    smoothing: int = 30,
    crop: str = "black",
) -> str:
    """
    Stabilize a video using FFmpeg's vidstab filter.
    
    This is a two-pass process:
    1. Analyze video and detect motion (vidstabdetect)
    2. Apply stabilization transforms (vidstabtransform)
    
    Args:
        input_path: Path to input video
        output_path: Path for stabilized output video
        shakiness: How shaky the video is (1-10, default 5)
        accuracy: Accuracy of detection (1-15, default 15)
        smoothing: Number of frames for smoothing (default 30)
        crop: How to handle borders: 'black' or 'keep'
    
    Returns:
        Path to stabilized video
    """
    # Create temp file for transforms
    transforms_file = tempfile.NamedTemporaryFile(
        suffix=".trf", delete=False
    ).name
    
    try:
        # Pass 1: Detect motion and generate transforms
        detect_cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", f"vidstabdetect=shakiness={shakiness}:accuracy={accuracy}:result={transforms_file}",
            "-f", "null",
            "-",
        ]
        
        result = subprocess.run(
            detect_cmd,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            # vidstab might not be available, return original
            print(f"vidstabdetect failed (vidstab may not be installed): {result.stderr}")
            # Copy original to output
            subprocess.run(["cp", input_path, output_path], check=True)
            return output_path
        
        # Pass 2: Apply stabilization transforms
        transform_cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vf", f"vidstabtransform=input={transforms_file}:smoothing={smoothing}:crop={crop}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "copy",
            output_path,
        ]
        
        result = subprocess.run(
            transform_cmd,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"vidstabtransform failed: {result.stderr}")
            # Copy original to output
            subprocess.run(["cp", input_path, output_path], check=True)
            return output_path
        
        return output_path
        
    finally:
        # Cleanup transforms file
        if os.path.exists(transforms_file):
            os.remove(transforms_file)


def quick_stabilize(
    input_path: str,
    output_path: str,
) -> str:
    """
    Quick stabilization using deshake filter (faster but less accurate).
    
    Use this as fallback when vidstab is not available.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", "deshake=x=-1:y=-1:w=-1:h=-1:rx=16:ry=16",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        output_path,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"deshake failed: {result.stderr}")
        # Copy original
        subprocess.run(["cp", input_path, output_path], check=True)
    
    return output_path


def check_vidstab_available() -> bool:
    """Check if vidstab filter is available in FFmpeg."""
    cmd = ["ffmpeg", "-filters"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return "vidstab" in result.stdout
