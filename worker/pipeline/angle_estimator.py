"""
Angle estimation module.
Estimates rotation angle between frames for intelligent frame selection.
"""
import os
from typing import List, Tuple, Optional
import numpy as np
import cv2


def estimate_rotation_angle(
    frame1: np.ndarray,
    frame2: np.ndarray,
    method: str = "orb",
) -> float:
    """
    Estimate the rotation angle between two frames.
    
    Uses feature matching to estimate camera movement around the object.
    
    Args:
        frame1: First frame (numpy array)
        frame2: Second frame (numpy array)
        method: Feature detection method ('orb', 'sift', 'akaze')
    
    Returns:
        Estimated rotation angle in degrees
    """
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY) if len(frame1.shape) == 3 else frame1
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY) if len(frame2.shape) == 3 else frame2
    
    # Create feature detector
    if method == "orb":
        detector = cv2.ORB_create(nfeatures=1000)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    elif method == "sift":
        detector = cv2.SIFT_create()
        matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
    elif method == "akaze":
        detector = cv2.AKAZE_create()
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    else:
        detector = cv2.ORB_create(nfeatures=1000)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    
    # Detect keypoints and compute descriptors
    kp1, desc1 = detector.detectAndCompute(gray1, None)
    kp2, desc2 = detector.detectAndCompute(gray2, None)
    
    if desc1 is None or desc2 is None or len(kp1) < 10 or len(kp2) < 10:
        return 0.0
    
    # Match features
    matches = matcher.match(desc1, desc2)
    
    if len(matches) < 10:
        return 0.0
    
    # Sort by distance
    matches = sorted(matches, key=lambda x: x.distance)
    
    # Use top matches
    good_matches = matches[:min(50, len(matches))]
    
    # Get matched points
    pts1 = np.float32([kp1[m.queryIdx].pt for m in good_matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in good_matches])
    
    # Calculate horizontal displacement (approximates rotation)
    dx = np.mean(pts2[:, 0] - pts1[:, 0])
    
    # Convert pixel displacement to approximate angle
    # Assuming 360° corresponds to full image width traversal
    image_width = gray1.shape[1]
    angle = (dx / image_width) * 360
    
    return angle


def calculate_cumulative_angles(
    frame_paths: List[str],
    sample_rate: int = 1,
) -> List[float]:
    """
    Calculate cumulative rotation angles for all frames.
    
    Args:
        frame_paths: List of frame image paths
        sample_rate: Process every Nth frame for speed
    
    Returns:
        List of cumulative angles (one per frame)
    """
    if len(frame_paths) < 2:
        return [0.0] * len(frame_paths)
    
    cumulative_angles = [0.0]
    
    prev_frame = cv2.imread(frame_paths[0])
    
    for i in range(1, len(frame_paths)):
        curr_frame = cv2.imread(frame_paths[i])
        
        if curr_frame is None:
            cumulative_angles.append(cumulative_angles[-1])
            continue
        
        if i % sample_rate == 0:
            angle = estimate_rotation_angle(prev_frame, curr_frame)
            cumulative_angles.append(cumulative_angles[-1] + angle)
            prev_frame = curr_frame
        else:
            # Interpolate
            cumulative_angles.append(cumulative_angles[-1])
    
    return cumulative_angles


def select_frames_by_angle(
    frame_paths: List[str],
    num_frames: int = 36,
    total_rotation: float = 360.0,
) -> List[str]:
    """
    Select frames at equidistant angular intervals.
    
    This ensures smooth rotation regardless of walking speed.
    
    Args:
        frame_paths: All available frame paths
        num_frames: Number of frames to select
        total_rotation: Expected total rotation in degrees
    
    Returns:
        List of selected frame paths
    """
    if len(frame_paths) <= num_frames:
        return frame_paths
    
    # Calculate cumulative angles
    angles = calculate_cumulative_angles(frame_paths)
    
    # Normalize to expected total rotation
    if angles[-1] != 0:
        scale = total_rotation / abs(angles[-1])
        angles = [a * scale for a in angles]
    else:
        # Fallback: assume uniform distribution
        angles = [i * total_rotation / len(frame_paths) for i in range(len(frame_paths))]
    
    # Select frames at target angles
    target_angles = [i * total_rotation / num_frames for i in range(num_frames)]
    
    selected = []
    for target in target_angles:
        # Find frame closest to target angle
        best_idx = min(range(len(angles)), key=lambda i: abs(angles[i] - target))
        selected.append(frame_paths[best_idx])
    
    return selected


def detect_rotation_direction(
    frame_paths: List[str],
    sample_count: int = 5,
) -> str:
    """
    Detect if the camera is moving clockwise or counter-clockwise.
    
    Args:
        frame_paths: Frame paths
        sample_count: Number of frame pairs to sample
    
    Returns:
        'cw' for clockwise, 'ccw' for counter-clockwise
    """
    if len(frame_paths) < 2:
        return "cw"
    
    total_angle = 0
    step = max(1, len(frame_paths) // sample_count)
    
    for i in range(0, len(frame_paths) - step, step):
        frame1 = cv2.imread(frame_paths[i])
        frame2 = cv2.imread(frame_paths[i + step])
        
        if frame1 is not None and frame2 is not None:
            angle = estimate_rotation_angle(frame1, frame2)
            total_angle += angle
    
    return "cw" if total_angle > 0 else "ccw"


def estimate_coverage(
    frame_paths: List[str],
) -> float:
    """
    Estimate how much of a full 360° rotation the video covers.
    
    Returns:
        Estimated coverage in degrees (0-360+)
    """
    angles = calculate_cumulative_angles(frame_paths)
    return abs(angles[-1]) if angles else 0.0
