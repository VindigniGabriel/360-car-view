"""
Caching module for models and intermediate results.
Reduces redundant processing and model loading.
"""
import os
import hashlib
import json
import time
from typing import Any, Optional, Callable
from functools import wraps


class ModelCache:
    """Singleton cache for ML models."""
    
    _instance = None
    _models = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get(self, model_name: str) -> Optional[Any]:
        """Get a cached model."""
        return self._models.get(model_name)
    
    def set(self, model_name: str, model: Any) -> None:
        """Cache a model."""
        self._models[model_name] = model
    
    def has(self, model_name: str) -> bool:
        """Check if model is cached."""
        return model_name in self._models
    
    def clear(self) -> None:
        """Clear all cached models."""
        self._models.clear()


class FileCache:
    """File-based cache for intermediate results."""
    
    def __init__(self, cache_dir: str = "/app/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()
    
    def _get_path(self, key: str) -> str:
        """Get cache file path for key."""
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, key: str) -> Optional[dict]:
        """Get cached value."""
        path = self._get_path(key)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    # Check expiry
                    if data.get("expires_at", float("inf")) > time.time():
                        return data.get("value")
            except Exception:
                pass
        return None
    
    def set(self, key: str, value: dict, ttl: int = 3600) -> None:
        """Cache a value with TTL in seconds."""
        path = self._get_path(key)
        data = {
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
        }
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def delete(self, key: str) -> None:
        """Delete cached value."""
        path = self._get_path(key)
        if os.path.exists(path):
            os.remove(path)
    
    def clear_expired(self) -> int:
        """Clear expired cache entries. Returns count of deleted entries."""
        deleted = 0
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.cache_dir, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if data.get("expires_at", float("inf")) < time.time():
                        os.remove(path)
                        deleted += 1
                except Exception:
                    pass
        return deleted


def cached(cache: FileCache, ttl: int = 3600):
    """Decorator for caching function results."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = {
                "func": func.__name__,
                "args": [str(a) for a in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()},
            }
            key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            
            # Check cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


def get_video_hash(video_path: str) -> str:
    """
    Generate a hash for a video file.
    Uses file size and first/last bytes for speed.
    """
    stat = os.stat(video_path)
    size = stat.st_size
    
    with open(video_path, 'rb') as f:
        # Read first 1KB
        first_bytes = f.read(1024)
        
        # Read last 1KB
        f.seek(max(0, size - 1024))
        last_bytes = f.read(1024)
    
    data = f"{size}:{first_bytes.hex()}:{last_bytes.hex()}"
    return hashlib.md5(data.encode()).hexdigest()


# Global instances
model_cache = ModelCache()
file_cache = FileCache()
