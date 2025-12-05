"""
Sprite sheet builder module.
Creates a single sprite sheet image from multiple frames.
"""
import os
import math
from typing import List
from PIL import Image


def build_sprite_sheet(
    frame_paths: List[str],
    output_path: str,
    num_frames: int,
    columns: int = None,
    quality: int = 85,
) -> str:
    """
    Build a sprite sheet from individual frames.
    
    Args:
        frame_paths: List of paths to frame images
        output_path: Path for output sprite sheet
        num_frames: Expected number of frames
        columns: Number of columns in sprite sheet (auto-calculated if None)
        quality: JPEG quality (1-100)
    
    Returns:
        Path to the created sprite sheet
    """
    if not frame_paths:
        raise ValueError("No frames provided")
    
    # Load first frame to get dimensions
    first_frame = Image.open(frame_paths[0])
    frame_width, frame_height = first_frame.size
    first_frame.close()
    
    # Calculate grid dimensions
    if columns is None:
        # Aim for roughly square sprite sheet
        columns = int(math.ceil(math.sqrt(len(frame_paths))))
    
    rows = int(math.ceil(len(frame_paths) / columns))
    
    # Create sprite sheet
    sprite_width = columns * frame_width
    sprite_height = rows * frame_height
    
    sprite = Image.new("RGB", (sprite_width, sprite_height), (255, 255, 255))
    
    # Place frames in grid
    for i, frame_path in enumerate(frame_paths):
        if not os.path.exists(frame_path):
            continue
        
        row = i // columns
        col = i % columns
        
        x = col * frame_width
        y = row * frame_height
        
        frame = Image.open(frame_path)
        sprite.paste(frame, (x, y))
        frame.close()
    
    # Save sprite sheet
    sprite.save(output_path, "JPEG", quality=quality, optimize=True)
    sprite.close()
    
    return output_path


def get_sprite_metadata(
    num_frames: int,
    frame_width: int,
    frame_height: int,
    columns: int = None,
) -> dict:
    """
    Get metadata for sprite sheet configuration.
    
    Returns dict with columns, rows, and frame dimensions.
    """
    if columns is None:
        columns = int(math.ceil(math.sqrt(num_frames)))
    
    rows = int(math.ceil(num_frames / columns))
    
    return {
        "frames": num_frames,
        "columns": columns,
        "rows": rows,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "sprite_width": columns * frame_width,
        "sprite_height": rows * frame_height,
    }
