"""
Metrics and monitoring module.
Tracks processing times, success rates, and system health.
"""
import time
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from functools import wraps
import redis
import os


class MetricsCollector:
    """Collects and stores application metrics."""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
        self.prefix = "metrics:"
    
    def _get_redis(self) -> redis.Redis:
        if self.redis is None:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            self.redis = redis.from_url(redis_url, decode_responses=True)
        return self.redis
    
    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a counter metric."""
        try:
            self._get_redis().incr(f"{self.prefix}counter:{metric}", value)
        except Exception:
            pass
    
    def gauge(self, metric: str, value: float) -> None:
        """Set a gauge metric."""
        try:
            self._get_redis().set(f"{self.prefix}gauge:{metric}", value)
        except Exception:
            pass
    
    def timing(self, metric: str, duration_ms: float) -> None:
        """Record a timing metric."""
        try:
            r = self._get_redis()
            key = f"{self.prefix}timing:{metric}"
            
            # Store in a sorted set with timestamp as score
            timestamp = time.time()
            r.zadd(key, {f"{timestamp}:{duration_ms}": timestamp})
            
            # Keep only last hour of data
            cutoff = timestamp - 3600
            r.zremrangebyscore(key, 0, cutoff)
        except Exception:
            pass
    
    def record_processing(
        self,
        task_id: str,
        duration_seconds: float,
        num_frames: int,
        success: bool,
    ) -> None:
        """Record video processing metrics."""
        try:
            r = self._get_redis()
            
            # Increment counters
            self.increment("videos_processed")
            if success:
                self.increment("videos_success")
            else:
                self.increment("videos_failed")
            
            # Record timing
            self.timing("processing_time", duration_seconds * 1000)
            
            # Store processing record
            record = {
                "task_id": task_id,
                "duration_seconds": duration_seconds,
                "num_frames": num_frames,
                "success": success,
                "timestamp": datetime.utcnow().isoformat(),
            }
            r.lpush(f"{self.prefix}history", json.dumps(record))
            r.ltrim(f"{self.prefix}history", 0, 999)  # Keep last 1000
        except Exception:
            pass
    
    def get_stats(self) -> Dict:
        """Get current metrics summary."""
        try:
            r = self._get_redis()
            
            # Get counters
            total = int(r.get(f"{self.prefix}counter:videos_processed") or 0)
            success = int(r.get(f"{self.prefix}counter:videos_success") or 0)
            failed = int(r.get(f"{self.prefix}counter:videos_failed") or 0)
            
            # Calculate average processing time
            timing_key = f"{self.prefix}timing:processing_time"
            timings = r.zrange(timing_key, 0, -1)
            
            avg_time = 0
            if timings:
                times = [float(t.split(":")[1]) for t in timings]
                avg_time = sum(times) / len(times) / 1000  # Convert to seconds
            
            return {
                "total_processed": total,
                "successful": success,
                "failed": failed,
                "success_rate": round(success / total * 100, 2) if total > 0 else 0,
                "avg_processing_time_seconds": round(avg_time, 2),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_recent_history(self, limit: int = 10) -> List[Dict]:
        """Get recent processing history."""
        try:
            r = self._get_redis()
            records = r.lrange(f"{self.prefix}history", 0, limit - 1)
            return [json.loads(r) for r in records]
        except Exception:
            return []


def timed(metric_name: str):
    """Decorator to time function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (time.time() - start) * 1000
                metrics.timing(metric_name, duration)
        return wrapper
    return decorator


# Global metrics instance
metrics = MetricsCollector()
