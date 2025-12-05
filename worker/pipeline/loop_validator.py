"""
Loop validation module.
Ensures the 360° sequence loops seamlessly by validating first/last frame similarity.
"""
import os
from typing import List, Tuple
import numpy as np
import cv2


def compute_frame_similarity(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    Compute similarity between two frames using SSIM.
    
    Args:
        frame1: First frame
        frame2: Second frame
    
    Returns:
        Similarity score (0-1, higher is more similar)
    """
    from skimage.metrics import structural_similarity as ssim
    
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY) if len(frame1.shape) == 3 else frame1
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY) if len(frame2.shape) == 3 else frame2
    
    # Resize to same size if needed
    if gray1.shape != gray2.shape:
        gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))
    
    # Compute SSIM
    score, _ = ssim(gray1, gray2, full=True)
    
    return score


def validate_loop(frame_paths: List[str], threshold: float = 0.7) -> Tuple[bool, float]:
    """
    Validate if the sequence forms a good loop.
    
    Args:
        frame_paths: List of frame paths
        threshold: Minimum similarity required (0-1)
    
    Returns:
        Tuple of (is_valid, similarity_score)
    """
    if len(frame_paths) < 2:
        return False, 0.0
    
    # Load first and last frames
    first = cv2.imread(frame_paths[0])
    last = cv2.imread(frame_paths[-1])
    
    if first is None or last is None:
        return False, 0.0
    
    # Compute similarity
    similarity = compute_frame_similarity(first, last)
    
    is_valid = similarity >= threshold
    
    return is_valid, similarity


def find_best_loop_point(
    frame_paths: List[str],
    target_frames: int = 36,
) -> Tuple[List[str], int]:
    """
    Find the best subset of frames that creates a perfect loop.
    
    Tries to find N frames where the last is most similar to the first.
    
    Args:
        frame_paths: All available frame paths
        target_frames: Desired number of frames
    
    Returns:
        Tuple of (selected frame paths, end index)
    """
    if len(frame_paths) <= target_frames:
        return frame_paths, len(frame_paths) - 1
    
    first_frame = cv2.imread(frame_paths[0])
    if first_frame is None:
        return frame_paths[:target_frames], target_frames - 1
    
    # Try different end points around target
    best_similarity = 0.0
    best_end_idx = target_frames - 1
    
    # Search window: ±10% of target
    search_range = max(3, target_frames // 10)
    start_idx = max(target_frames - search_range, 1)
    end_idx = min(target_frames + search_range, len(frame_paths))
    
    for i in range(start_idx, end_idx):
        candidate = cv2.imread(frame_paths[i])
        if candidate is None:
            continue
        
        similarity = compute_frame_similarity(first_frame, candidate)
        
        if similarity > best_similarity:
            best_similarity = similarity
            best_end_idx = i
    
    # Select frames with best loop point
    selected = frame_paths[:best_end_idx + 1]
    
    # If we have more frames than target, subsample evenly
    if len(selected) > target_frames:
        indices = np.linspace(0, len(selected) - 1, target_frames, dtype=int)
        selected = [selected[i] for i in indices]
    
    return selected, best_end_idx


def create_transition_frame(
    frame1: np.ndarray,
    frame2: np.ndarray,
    alpha: float = 0.5,
) -> np.ndarray:
    """
    Create a blended transition frame between two frames.
    
    Args:
        frame1: First frame
        frame2: Second frame
        alpha: Blend factor (0=frame1, 1=frame2)
    
    Returns:
        Blended frame
    """
    return cv2.addWeighted(frame1, 1 - alpha, frame2, alpha, 0)


def smooth_loop_transition(
    frame_paths: List[str],
    output_dir: str,
    blend_count: int = 2,
) -> List[str]:
    """
    Add blended transition frames at the loop point for smoother rotation.
    
    Args:
        frame_paths: List of frame paths
        output_dir: Output directory
        blend_count: Number of blend frames to insert
    
    Returns:
        List of frame paths with transitions
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if len(frame_paths) < 2:
        return frame_paths
    
    # Copy all original frames
    output_paths = []
    for i, path in enumerate(frame_paths):
        frame = cv2.imread(path)
        if frame is None:
            continue
        
        output_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
        cv2.imwrite(output_path, frame)
        output_paths.append(output_path)
    
    # Add transition frames between last and first
    last_frame = cv2.imread(frame_paths[-1])
    first_frame = cv2.imread(frame_paths[0])
    
    if last_frame is not None and first_frame is not None:
        for i in range(1, blend_count + 1):
            alpha = i / (blend_count + 1)
            blended = create_transition_frame(last_frame, first_frame, alpha)
            
            output_path = os.path.join(
                output_dir, 
                f"frame_{len(frame_paths) + i - 1:03d}.jpg"
            )
            cv2.imwrite(output_path, blended)
            output_paths.append(output_path)
    
    return output_paths
