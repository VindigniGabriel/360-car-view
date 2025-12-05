"""
Image optimization module.
Compresses and optimizes images for web delivery.
"""
import os
from typing import List, Tuple, Optional
from PIL import Image
import subprocess


def optimize_image(
    input_path: str,
    output_path: str,
    format: str = "webp",
    quality: int = 85,
    max_width: int = None,
    max_height: int = None,
) -> str:
    """
    Optimize an image for web delivery.
    
    Args:
        input_path: Path to input image
        output_path: Path for output image
        format: Output format ('webp', 'jpeg', 'png')
        quality: Compression quality (1-100)
        max_width: Maximum width (resize if larger)
        max_height: Maximum height (resize if larger)
    
    Returns:
        Path to optimized image
    """
    image = Image.open(input_path)
    
    # Resize if needed
    if max_width or max_height:
        orig_width, orig_height = image.size
        
        if max_width and orig_width > max_width:
            ratio = max_width / orig_width
            new_height = int(orig_height * ratio)
            image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        if max_height and image.size[1] > max_height:
            ratio = max_height / image.size[1]
            new_width = int(image.size[0] * ratio)
            image = image.resize((new_width, max_height), Image.Resampling.LANCZOS)
    
    # Convert to RGB if necessary (for JPEG/WebP)
    if image.mode in ('RGBA', 'P') and format.lower() in ('jpeg', 'jpg', 'webp'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'RGBA':
            background.paste(image, mask=image.split()[3])
        else:
            background.paste(image)
        image = background
    
    # Save with optimization
    save_kwargs = {
        'quality': quality,
        'optimize': True,
    }
    
    if format.lower() == 'webp':
        save_kwargs['method'] = 6  # Best compression
    elif format.lower() in ('jpeg', 'jpg'):
        save_kwargs['progressive'] = True
    
    image.save(output_path, format=format.upper(), **save_kwargs)
    image.close()
    
    return output_path


def batch_optimize(
    input_paths: List[str],
    output_dir: str,
    format: str = "webp",
    quality: int = 85,
) -> List[str]:
    """
    Optimize multiple images.
    
    Args:
        input_paths: List of input image paths
        output_dir: Directory for output images
        format: Output format
        quality: Compression quality
    
    Returns:
        List of optimized image paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    output_paths = []
    for input_path in input_paths:
        filename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{filename}.{format}")
        
        try:
            optimize_image(input_path, output_path, format, quality)
            output_paths.append(output_path)
        except Exception as e:
            print(f"Failed to optimize {input_path}: {e}")
            # Fallback: copy original
            output_paths.append(input_path)
    
    return output_paths


def create_webp_sprite(
    frame_paths: List[str],
    output_path: str,
    quality: int = 80,
    columns: int = None,
) -> Tuple[str, dict]:
    """
    Create an optimized WebP sprite sheet.
    
    Args:
        frame_paths: List of frame image paths
        output_path: Path for output sprite
        quality: WebP quality
        columns: Number of columns (auto if None)
    
    Returns:
        Tuple of (sprite path, metadata dict)
    """
    import math
    
    if not frame_paths:
        raise ValueError("No frames provided")
    
    # Load first frame to get dimensions
    first_frame = Image.open(frame_paths[0])
    frame_width, frame_height = first_frame.size
    first_frame.close()
    
    # Calculate grid
    num_frames = len(frame_paths)
    if columns is None:
        columns = int(math.ceil(math.sqrt(num_frames)))
    rows = int(math.ceil(num_frames / columns))
    
    # Create sprite
    sprite_width = columns * frame_width
    sprite_height = rows * frame_height
    sprite = Image.new("RGB", (sprite_width, sprite_height), (255, 255, 255))
    
    for i, frame_path in enumerate(frame_paths):
        row = i // columns
        col = i % columns
        x = col * frame_width
        y = row * frame_height
        
        frame = Image.open(frame_path)
        sprite.paste(frame, (x, y))
        frame.close()
    
    # Save as WebP
    sprite.save(output_path, "WEBP", quality=quality, method=6)
    sprite.close()
    
    metadata = {
        "format": "webp",
        "frames": num_frames,
        "columns": columns,
        "rows": rows,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "sprite_width": sprite_width,
        "sprite_height": sprite_height,
    }
    
    return output_path, metadata


def get_image_size(path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(path)


def calculate_savings(original_paths: List[str], optimized_paths: List[str]) -> dict:
    """
    Calculate space savings from optimization.
    
    Returns:
        Dict with original_size, optimized_size, savings_bytes, savings_percent
    """
    original_size = sum(get_image_size(p) for p in original_paths if os.path.exists(p))
    optimized_size = sum(get_image_size(p) for p in optimized_paths if os.path.exists(p))
    
    savings_bytes = original_size - optimized_size
    savings_percent = (savings_bytes / original_size * 100) if original_size > 0 else 0
    
    return {
        "original_size_bytes": original_size,
        "optimized_size_bytes": optimized_size,
        "savings_bytes": savings_bytes,
        "savings_percent": round(savings_percent, 2),
    }
