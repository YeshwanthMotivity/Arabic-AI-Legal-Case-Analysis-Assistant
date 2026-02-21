"""
Response Cache Module
Provides a simple in-memory caching layer for backend responses to prevent duplicate LLM/pipeline executions.
"""
import time
from typing import Any, Optional

class ResponseCache:
    def __init__(self, ttl_seconds: int = 300):
        # Store items as { key: {"value": value, "timestamp": timestamp} }
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            item = self.cache[key]
            if time.time() - item["timestamp"] <= self.ttl:
                return item["value"]
            else:
                # Expired
                del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        self.cache[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def clear(self):
        self.cache = {}

# Global instance
response_cache = ResponseCache()
