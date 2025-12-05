"""
Frame normalization module.
Crops, resizes, and centers frames based on vehicle detection.
"""
import os
from typing import List, Tuple, Optional, Dict
from PIL import Image
import numpy as np


def normalize_frame(
    image: Image.Image,
    detection: Optional[Dict],
    output_size: Tuple[int, int] = (800, 600),
    padding: float = 0.15,
) -> Image.Image:
    """
    Normalize a frame by centering on the detected vehicle.
    
    Args:
        image: PIL Image
        detection: Detection dict with bbox and center (or None)
        output_size: Target (width, height)
        padding: Padding around vehicle
    
    Returns:
        Normalized PIL Image
    """
    width, height = image.size
    target_width, target_height = output_size
    target_aspect = target_width / target_height
    
    if detection is None:
        # No detection: center crop
        current_aspect = width / height
        
        if current_aspect > target_aspect:
            # Image is wider: crop width
            new_width = int(height * target_aspect)
            x1 = (width - new_width) // 2
            crop_box = (x1, 0, x1 + new_width, height)
        else:
            # Image is taller: crop height
            new_height = int(width / target_aspect)
            y1 = (height - new_height) // 2
            crop_box = (0, y1, width, y1 + new_height)
        
        cropped = image.crop(crop_box)
        return cropped.resize(output_size, Image.Resampling.LANCZOS)
    
    # With detection: center on vehicle
    bbox = detection["bbox"]
    center_x = detection["center"]["x"]
    center_y = detection["center"]["y"]
    
    # Calculate vehicle dimensions with padding
    vehicle_width = bbox["x2"] - bbox["x1"]
    vehicle_height = bbox["y2"] - bbox["y1"]
    
    padded_width = vehicle_width * (1 + padding * 2)
    padded_height = vehicle_height * (1 + padding * 2)
    
    # Adjust to target aspect ratio
    if padded_width / padded_height > target_aspect:
        crop_width = padded_width
        crop_height = padded_width / target_aspect
    else:
        crop_height = padded_height
        crop_width = padded_height * target_aspect
    
    # Ensure minimum crop size
    min_crop = min(width, height) * 0.5
    crop_width = max(crop_width, min_crop)
    crop_height = max(crop_height, min_crop / target_aspect)
    
    # Calculate crop box centered on vehicle
    x1 = int(center_x - crop_width / 2)
    y1 = int(center_y - crop_height / 2)
    x2 = int(center_x + crop_width / 2)
    y2 = int(center_y + crop_height / 2)
    
    # Adjust if out of bounds
    if x1 < 0:
        x2 -= x1
        x1 = 0
    if y1 < 0:
        y2 -= y1
        y1 = 0
    if x2 > width:
        x1 -= (x2 - width)
        x2 = width
    if y2 > height:
        y1 -= (y2 - height)
        y2 = height
    
    # Final clamp
    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = min(width, int(x2))
    y2 = min(height, int(y2))
    
    cropped = image.crop((x1, y1, x2, y2))
    return cropped.resize(output_size, Image.Resampling.LANCZOS)


def normalize_frames(
    frame_paths: List[str],
    detections: List[Optional[Dict]],
    output_dir: str,
    output_size: Tuple[int, int] = (800, 600),
    quality: int = 90,
) -> List[str]:
    """
    Normalize all frames with consistent centering.
    
    Args:
        frame_paths: List of input frame paths
        detections: List of detections for each frame
        output_dir: Directory for normalized frames
        output_size: Target (width, height)
        quality: JPEG quality
    
    Returns:
        List of normalized frame paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Use smoothed detections for consistent centering
    smoothed = smooth_detections(detections)
    
    normalized_paths = []
    for i, (path, detection) in enumerate(zip(frame_paths, smoothed)):
        image = Image.open(path)
        normalized = normalize_frame(image, detection, output_size)
        
        output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        normalized.save(output_path, "JPEG", quality=quality)
        normalized_paths.append(output_path)
        
        image.close()
    
    return normalized_paths


def smooth_detections(
    detections: List[Optional[Dict]],
    window_size: int = 5,
) -> List[Optional[Dict]]:
    """
    Smooth detection centers across frames to reduce jitter.
    
    Args:
        detections: List of detections
        window_size: Smoothing window size
    
    Returns:
        Smoothed detections
    """
    if not detections:
        return detections
    
    # Find valid detections
    valid_indices = [i for i, d in enumerate(detections) if d is not None]
    
    if not valid_indices:
        return detections
    
    # Interpolate missing detections
    smoothed = list(detections)
    
    for i, det in enumerate(detections):
        if det is None:
            # Find nearest valid detection
            nearest = min(valid_indices, key=lambda x: abs(x - i))
            smoothed[i] = detections[nearest]
    
    # Apply moving average to centers
    centers_x = [d["center"]["x"] if d else 0 for d in smoothed]
    centers_y = [d["center"]["y"] if d else 0 for d in smoothed]
    
    smoothed_x = moving_average(centers_x, window_size)
    smoothed_y = moving_average(centers_y, window_size)
    
    # Update detections with smoothed centers
    result = []
    for i, det in enumerate(smoothed):
        if det is None:
            result.append(None)
        else:
            new_det = det.copy()
            new_det["center"] = {
                "x": int(smoothed_x[i]),
                "y": int(smoothed_y[i]),
            }
            result.append(new_det)
    
    return result


def moving_average(values: List[float], window: int) -> List[float]:
    """Apply moving average smoothing."""
    if len(values) < window:
        return values
    
    result = []
    half_window = window // 2
    
    for i in range(len(values)):
        start = max(0, i - half_window)
        end = min(len(values), i + half_window + 1)
        avg = sum(values[start:end]) / (end - start)
        result.append(avg)
    
    return result


def equalize_histogram(image: Image.Image) -> Image.Image:
    """
    Apply histogram equalization for consistent lighting.
    
    Args:
        image: PIL Image
    
    Returns:
        Equalized PIL Image
    """
    import cv2
    
    # Convert to numpy
    img_array = np.array(image)
    
    # Convert to LAB color space
    lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    
    # Apply CLAHE to L channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    
    # Convert back to RGB
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    
    return Image.fromarray(result)
