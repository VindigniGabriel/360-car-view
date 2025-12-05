"""
Frame alignment module.
Aligns frames using homography to ensure consistent positioning.
"""
import os
from typing import List, Tuple
import numpy as np
import cv2
from PIL import Image


def compute_homography(
    img1: np.ndarray,
    img2: np.ndarray,
    max_features: int = 500,
) -> Tuple[np.ndarray, bool]:
    """
    Compute homography matrix between two images.
    
    Args:
        img1: Reference image
        img2: Image to align
        max_features: Maximum number of features to detect
    
    Returns:
        Tuple of (homography matrix, success flag)
    """
    # Convert to grayscale
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if len(img1.shape) == 3 else img1
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if len(img2.shape) == 3 else img2
    
    # Detect ORB features
    orb = cv2.ORB_create(max_features)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)
    
    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        return None, False
    
    # Match features
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    
    if len(matches) < 10:
        return None, False
    
    # Sort by distance
    matches = sorted(matches, key=lambda x: x.distance)
    
    # Extract matched keypoints
    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches[:50]])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches[:50]])
    
    # Compute homography
    H, mask = cv2.findHomography(pts2, pts1, cv2.RANSAC, 5.0)
    
    if H is None:
        return None, False
    
    return H, True


def align_frame(
    frame: np.ndarray,
    reference: np.ndarray,
    H: np.ndarray = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Align a frame to a reference using homography.
    
    Args:
        frame: Frame to align
        reference: Reference frame
        H: Pre-computed homography (optional)
    
    Returns:
        Tuple of (aligned frame, homography matrix)
    """
    if H is None:
        H, success = compute_homography(reference, frame)
        if not success:
            return frame, None
    
    # Warp frame to align with reference
    h, w = reference.shape[:2]
    aligned = cv2.warpPerspective(frame, H, (w, h))
    
    return aligned, H


def align_frames_sequence(
    frame_paths: List[str],
    output_dir: str,
    reference_idx: int = 0,
) -> List[str]:
    """
    Align a sequence of frames to a reference frame.
    
    Args:
        frame_paths: List of frame paths
        output_dir: Output directory for aligned frames
        reference_idx: Index of reference frame (default: first frame)
    
    Returns:
        List of aligned frame paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if not frame_paths:
        return []
    
    # Load reference frame
    reference = cv2.imread(frame_paths[reference_idx])
    if reference is None:
        print(f"Failed to load reference frame: {frame_paths[reference_idx]}")
        return frame_paths
    
    aligned_paths = []
    
    for i, frame_path in enumerate(frame_paths):
        output_path = os.path.join(output_dir, os.path.basename(frame_path))
        
        if i == reference_idx:
            # Copy reference as-is
            frame = cv2.imread(frame_path)
            cv2.imwrite(output_path, frame)
            aligned_paths.append(output_path)
            continue
        
        # Load and align frame
        frame = cv2.imread(frame_path)
        if frame is None:
            print(f"Failed to load frame: {frame_path}")
            aligned_paths.append(frame_path)
            continue
        
        try:
            aligned, H = align_frame(frame, reference)
            
            if H is not None:
                cv2.imwrite(output_path, aligned)
                aligned_paths.append(output_path)
            else:
                # Alignment failed, use original
                cv2.imwrite(output_path, frame)
                aligned_paths.append(output_path)
        except Exception as e:
            print(f"Failed to align frame {i}: {e}")
            cv2.imwrite(output_path, frame)
            aligned_paths.append(output_path)
    
    return aligned_paths


def align_to_center_mass(
    frame_paths: List[str],
    output_dir: str,
    detections: List[dict] = None,
) -> List[str]:
    """
    Align frames so the detected object stays centered.
    
    Args:
        frame_paths: List of frame paths
        output_dir: Output directory
        detections: List of detection dicts with 'bbox' key
    
    Returns:
        List of aligned frame paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if not detections or len(detections) != len(frame_paths):
        return frame_paths
    
    # Calculate average center position
    centers = []
    for det in detections:
        if det and 'bbox' in det:
            x1, y1, x2, y2 = det['bbox']
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            centers.append((cx, cy))
        else:
            centers.append(None)
    
    # Filter valid centers
    valid_centers = [c for c in centers if c is not None]
    if not valid_centers:
        return frame_paths
    
    # Calculate target center (average)
    target_cx = np.mean([c[0] for c in valid_centers])
    target_cy = np.mean([c[1] for c in valid_centers])
    
    aligned_paths = []
    
    for i, (frame_path, center) in enumerate(zip(frame_paths, centers)):
        output_path = os.path.join(output_dir, os.path.basename(frame_path))
        
        frame = cv2.imread(frame_path)
        if frame is None:
            aligned_paths.append(frame_path)
            continue
        
        if center is None:
            # No detection, use as-is
            cv2.imwrite(output_path, frame)
            aligned_paths.append(output_path)
            continue
        
        # Calculate translation
        dx = target_cx - center[0]
        dy = target_cy - center[1]
        
        # Apply translation
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        h, w = frame.shape[:2]
        aligned = cv2.warpAffine(frame, M, (w, h))
        
        cv2.imwrite(output_path, aligned)
        aligned_paths.append(output_path)
    
    return aligned_paths
