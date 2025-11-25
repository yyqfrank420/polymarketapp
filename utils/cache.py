"""Simple in-memory cache for chatbot queries"""
import time
import threading
from typing import Optional, Any

class SimpleCache:
    """Thread-safe in-memory cache with TTL"""
    
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
    
    def get(self, key: str, ttl: int = 60) -> Optional[Any]:
        """Get cached value if not expired"""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < ttl:
                    return value
                else:
                    # Expired, remove it
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any):
        """Set cached value with current timestamp"""
        with self._lock:
            self._cache[key] = (value, time.time())
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self._cache.clear()

# Global cache instance
_cache = SimpleCache()

def get_cache() -> SimpleCache:
    """Get global cache instance"""
    return _cache

