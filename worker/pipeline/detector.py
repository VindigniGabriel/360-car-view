"""
Object detection module using YOLOv8.
Detects and tracks vehicles in video frames for automatic centering.
"""
import os
from typing import List, Tuple, Optional, Dict
import numpy as np
from PIL import Image


# YOLO class IDs for vehicles
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class VehicleDetector:
    """Detects vehicles in images using YOLOv8."""
    
    def __init__(self, model_path: str = None, confidence: float = 0.5):
        """
        Initialize the detector.
        
        Args:
            model_path: Path to YOLO model weights (default: yolov8n.pt)
            confidence: Minimum confidence threshold
        """
        self.confidence = confidence
        self.model = None
        self.model_path = model_path or "yolov8n.pt"
        
    def _load_model(self):
        """Lazy load the YOLO model."""
        if self.model is None:
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
            except Exception as e:
                print(f"Failed to load YOLO model: {e}")
                self.model = None
        return self.model
    
    def detect(self, image: np.ndarray) -> List[Dict]:
        """
        Detect vehicles in an image.
        
        Args:
            image: Image as numpy array (BGR or RGB)
        
        Returns:
            List of detections with bounding boxes and confidence
        """
        model = self._load_model()
        if model is None:
            return []
        
        results = model(image, conf=self.confidence, verbose=False)
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id in VEHICLE_CLASSES:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append({
                        "class_id": cls_id,
                        "class_name": VEHICLE_CLASSES[cls_id],
                        "confidence": float(box.conf[0]),
                        "bbox": {
                            "x1": int(x1),
                            "y1": int(y1),
                            "x2": int(x2),
                            "y2": int(y2),
                        },
                        "center": {
                            "x": int((x1 + x2) / 2),
                            "y": int((y1 + y2) / 2),
                        },
                        "area": int((x2 - x1) * (y2 - y1)),
                    })
        
        # Sort by area (largest first)
        detections.sort(key=lambda d: d["area"], reverse=True)
        return detections
    
    def detect_from_file(self, image_path: str) -> List[Dict]:
        """Detect vehicles from an image file."""
        import cv2
        image = cv2.imread(image_path)
        if image is None:
            return []
        return self.detect(image)
    
    def get_main_vehicle(self, image: np.ndarray) -> Optional[Dict]:
        """
        Get the main (largest) vehicle in the image.
        
        Returns:
            Detection dict or None if no vehicle found
        """
        detections = self.detect(image)
        return detections[0] if detections else None


def calculate_crop_box(
    detection: Dict,
    image_width: int,
    image_height: int,
    padding: float = 0.1,
    aspect_ratio: float = 4/3,
) -> Tuple[int, int, int, int]:
    """
    Calculate a crop box centered on the detected vehicle.
    
    Args:
        detection: Detection dict with bbox
        image_width: Original image width
        image_height: Original image height
        padding: Padding around vehicle (0.1 = 10%)
        aspect_ratio: Desired aspect ratio (width/height)
    
    Returns:
        Tuple of (x1, y1, x2, y2) for crop box
    """
    bbox = detection["bbox"]
    center_x = detection["center"]["x"]
    center_y = detection["center"]["y"]
    
    # Calculate vehicle dimensions with padding
    vehicle_width = bbox["x2"] - bbox["x1"]
    vehicle_height = bbox["y2"] - bbox["y1"]
    
    padded_width = vehicle_width * (1 + padding * 2)
    padded_height = vehicle_height * (1 + padding * 2)
    
    # Adjust to desired aspect ratio
    if padded_width / padded_height > aspect_ratio:
        # Too wide, increase height
        crop_width = padded_width
        crop_height = padded_width / aspect_ratio
    else:
        # Too tall, increase width
        crop_height = padded_height
        crop_width = padded_height * aspect_ratio
    
    # Calculate crop box
    x1 = int(center_x - crop_width / 2)
    y1 = int(center_y - crop_height / 2)
    x2 = int(center_x + crop_width / 2)
    y2 = int(center_y + crop_height / 2)
    
    # Clamp to image bounds
    if x1 < 0:
        x2 -= x1
        x1 = 0
    if y1 < 0:
        y2 -= y1
        y1 = 0
    if x2 > image_width:
        x1 -= (x2 - image_width)
        x2 = image_width
    if y2 > image_height:
        y1 -= (y2 - image_height)
        y2 = image_height
    
    # Final clamp
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image_width, x2)
    y2 = min(image_height, y2)
    
    return x1, y1, x2, y2


def detect_vehicles_in_frames(
    frame_paths: List[str],
    detector: VehicleDetector = None,
) -> List[Optional[Dict]]:
    """
    Detect the main vehicle in each frame.
    
    Args:
        frame_paths: List of frame image paths
        detector: VehicleDetector instance (created if None)
    
    Returns:
        List of detections (None for frames with no vehicle)
    """
    if detector is None:
        detector = VehicleDetector()
    
    detections = []
    for path in frame_paths:
        det = detector.detect_from_file(path)
        detections.append(det[0] if det else None)
    
    return detections
