#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startup progress

The engine prepares itself before it can inject anything: it fetches the LTK
patcher, refreshes the skin hashes and syncs skin data. That work used to run
behind a separate "Rose Loader" window. D-Changer hides it inside the UI
instead, so the launcher reports progress here and the UI polls it over the
local API.

This module is deliberately tiny and dependency-free: it is imported by both
the launcher (before the engine is up) and the API server, and must not pull in
anything heavy.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class StartupProgress:
    """Thread-safe snapshot of the startup sequence."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _message: str = "Starting…"
    _detail: str = ""
    _progress: int = 0
    _marquee: bool = True
    _ready: bool = False
    _error: str = ""

    def update(self, message: str | None = None, detail: str | None = None,
               progress: int | None = None, marquee: bool | None = None) -> None:
        with self._lock:
            if message is not None:
                self._message = message
            if detail is not None:
                self._detail = detail
            if progress is not None:
                self._progress = max(0, min(100, progress))
            if marquee is not None:
                self._marquee = marquee

    def finish(self) -> None:
        with self._lock:
            self._ready = True
            self._message = "Ready"
            self._progress = 100
            self._marquee = False

    def fail(self, error: str) -> None:
        with self._lock:
            self._error = error
            self._message = "Startup failed"
            self._marquee = False

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "message": self._message,
                "detail": self._detail,
                "progress": self._progress,
                "marquee": self._marquee,
                "ready": self._ready,
                "error": self._error,
            }


# The process-wide instance the API reads and the launcher writes.
PROGRESS = StartupProgress()
