from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "car360"
    minio_secure: bool = False

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # App
    max_video_size_mb: int = 100
    allowed_extensions: str = "mp4,mov,avi"
    default_frames: int = 36
    temp_dir: str = "/app/temp"

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
