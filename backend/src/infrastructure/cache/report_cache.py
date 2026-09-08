from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_DEFAULT_TTL_SECONDS = 900


class ReportReadCache:
    """In-memory TTL cache for per-report read-heavy repository queries."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._entries[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + self._ttl_seconds, value)

    def invalidate_report(self, report_date: str) -> None:
        prefix = f"{report_date}:"
        with self._lock:
            keys = [key for key in self._entries if key.startswith(prefix) or key == report_date]
            for key in keys:
                self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_report_read_cache = ReportReadCache()


def get_report_read_cache() -> ReportReadCache:
    return _report_read_cache


def cached_report_read(namespace: str, report_date: str, loader: Callable[[], T]) -> T:
    key = f"{report_date}:{namespace}"
    cached = _report_read_cache.get(key)
    if cached is not None:
        return cached
    value = loader()
    _report_read_cache.set(key, value)
    return value
