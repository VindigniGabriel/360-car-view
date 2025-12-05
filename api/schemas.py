from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class FrameCount(int, Enum):
    FRAMES_24 = 24
    FRAMES_36 = 36
    FRAMES_72 = 72


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class ProcessingStep(str, Enum):
    UPLOADING = "uploading"
    STABILIZING = "stabilizing"
    DETECTING = "detecting"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    BUILDING = "building"
    COMPLETED = "completed"


class VideoUploadResponse(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = "Video uploaded successfully. Processing started."


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = Field(ge=0, le=100)
    step: Optional[ProcessingStep] = None
    created_at: datetime
    error: Optional[str] = None


class ResultMetadata(BaseModel):
    total_frames: int
    frame_width: int
    frame_height: int
    processing_time_seconds: float


class TaskResultResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[dict] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
