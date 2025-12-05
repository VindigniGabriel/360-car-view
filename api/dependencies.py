from minio import Minio
from minio.error import S3Error
from functools import lru_cache
import redis
from .config import get_settings


@lru_cache
def get_minio_client() -> Minio:
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    
    # Ensure bucket exists
    try:
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
    except S3Error as e:
        print(f"MinIO bucket check failed: {e}")
    
    return client


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def ensure_bucket_exists(client: Minio, bucket_name: str) -> bool:
    """Ensure the bucket exists, create if not."""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        return True
    except S3Error as e:
        print(f"Failed to ensure bucket exists: {e}")
        return False
