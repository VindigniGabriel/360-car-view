"""
Background removal module using rembg.
Removes background from vehicle images for transparent 360° viewer.
"""
import os
from typing import List, Tuple
from PIL import Image, ImageFilter
import numpy as np
import cv2
import io


def refine_mask(mask: np.ndarray) -> np.ndarray:
    """
    Advanced mask refinement to remove halos and create clean edges.
    
    Args:
        mask: Alpha channel as numpy array
    
    Returns:
        Refined mask with clean edges
    """
    # Step 1: Threshold to remove semi-transparent pixels
    hard_fg = (mask > 220).astype(np.uint8) * 255
    
    # Step 2: Morphological operations
    kernel_small = np.ones((2, 2), np.uint8)
    kernel_med = np.ones((3, 3), np.uint8)
    
    # Erode to remove halo
    eroded = cv2.erode(hard_fg, kernel_small, iterations=1)
    
    # Close small holes
    closed = cv2.morphologyEx(eroded, cv2.MORPH_CLOSE, kernel_med)
    
    # Step 3: Feathering - smooth edge transition
    dilated = cv2.dilate(closed, kernel_small, iterations=1)
    edge = cv2.subtract(dilated, cv2.erode(closed, kernel_small, iterations=1))
    edge_blurred = cv2.GaussianBlur(edge, (5, 5), 0)
    
    result = closed.copy()
    edge_mask = edge > 0
    result[edge_mask] = np.clip(
        closed[edge_mask] * 0.7 + edge_blurred[edge_mask] * 0.3, 0, 255
    ).astype(np.uint8)
    
    # Step 4: Final smoothing
    result = cv2.GaussianBlur(result, (3, 3), 0)
    result = np.clip(result.astype(np.float32) * 1.15 - 10, 0, 255).astype(np.uint8)
    
    return result


def remove_background(
    input_path: str,
    output_path: str,
    model: str = "isnet-general-use",
    refine: bool = True,
) -> str:
    """
    Remove background from an image using rembg with refinement.
    
    Args:
        input_path: Path to input image
        output_path: Path for output image (PNG with transparency)
        model: rembg model ('isnet-general-use' recommended for objects)
        refine: Apply post-processing to clean edges
    
    Returns:
        Path to output image
    """
    from rembg import remove, new_session
    
    # Create session for the model (cached)
    session = new_session(model)
    
    # Read input image
    with open(input_path, 'rb') as f:
        input_data = f.read()
    
    # Remove background with alpha matting for better edges
    output_data = remove(
        input_data,
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=270,
        alpha_matting_background_threshold=20,
        alpha_matting_erode_size=15,
    )
    
    # Load result
    output_image = Image.open(io.BytesIO(output_data)).convert("RGBA")
    
    if refine:
        # Extract alpha channel and refine it
        r, g, b, a = output_image.split()
        alpha_np = np.array(a)
        
        # Refine the mask
        refined_alpha = refine_mask(alpha_np)
        
        # Apply refined alpha
        a = Image.fromarray(refined_alpha)
        output_image = Image.merge("RGBA", (r, g, b, a))
    
    # Save output
    output_image.save(output_path, "PNG", optimize=True)
    
    return output_path


def remove_background_batch(
    input_paths: List[str],
    output_dir: str,
    model: str = "isnet-general-use",
) -> List[str]:
    """
    Remove background from multiple images with refinement.
    
    Args:
        input_paths: List of input image paths
        output_dir: Directory for output images
        model: rembg model to use ('isnet-general-use' for best quality)
    
    Returns:
        List of output image paths
    """
    from rembg import remove, new_session
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Create session once for all images
    session = new_session(model)
    
    output_paths = []
    for input_path in input_paths:
        filename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{filename}.png")
        
        try:
            with open(input_path, 'rb') as f:
                input_data = f.read()
            
            # Remove background with alpha matting
            output_data = remove(
                input_data,
                session=session,
                alpha_matting=True,
                alpha_matting_foreground_threshold=270,
                alpha_matting_background_threshold=20,
                alpha_matting_erode_size=15,
            )
            
            # Load and refine
            output_image = Image.open(io.BytesIO(output_data)).convert("RGBA")
            
            # Refine alpha channel
            r, g, b, a = output_image.split()
            alpha_np = np.array(a)
            refined_alpha = refine_mask(alpha_np)
            a = Image.fromarray(refined_alpha)
            output_image = Image.merge("RGBA", (r, g, b, a))
            
            output_image.save(output_path, "PNG", optimize=True)
            output_paths.append(output_path)
            
        except Exception as e:
            print(f"Failed to remove background from {input_path}: {e}")
            # Fallback: copy original
            output_paths.append(input_path)
    
    return output_paths


def create_transparent_sprite(
    frame_paths: List[str],
    output_path: str,
    columns: int = None,
) -> Tuple[str, dict]:
    """
    Create a sprite sheet with transparency (PNG format).
    
    Args:
        frame_paths: List of frame image paths (with transparency)
        output_path: Path for output sprite
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
    
    # Create sprite with transparency
    sprite_width = columns * frame_width
    sprite_height = rows * frame_height
    sprite = Image.new("RGBA", (sprite_width, sprite_height), (0, 0, 0, 0))
    
    for i, frame_path in enumerate(frame_paths):
        row = i // columns
        col = i % columns
        x = col * frame_width
        y = row * frame_height
        
        frame = Image.open(frame_path)
        # Convert to RGBA if needed
        if frame.mode != 'RGBA':
            frame = frame.convert('RGBA')
        sprite.paste(frame, (x, y), frame)
        frame.close()
    
    # Save as PNG (preserves transparency)
    sprite.save(output_path, "PNG", optimize=True)
    sprite.close()
    
    metadata = {
        "format": "png",
        "transparent": True,
        "frames": num_frames,
        "columns": columns,
        "rows": rows,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "sprite_width": sprite_width,
        "sprite_height": sprite_height,
    }
    
    return output_path, metadata
