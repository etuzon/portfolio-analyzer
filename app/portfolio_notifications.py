"""Wake connected dashboards when the analytics worker changes state."""

import asyncio
from contextlib import asynccontextmanager
from threading import Lock


class PortfolioNotifications:
    def __init__(self):
        self._lock = Lock()
        self._listeners = set()
        self._revision = 0

    @property
    def revision(self):
        with self._lock:
            return self._revision

    def notify(self):
        # Workers run on threads; events belong to their subscriber's loop.
        with self._lock:
            self._revision += 1
            listeners = tuple(self._listeners)
        for loop, event in listeners:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                pass  # A disconnected subscriber's loop may already be closed.

    @asynccontextmanager
    async def subscribe(self):
        listener = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            self._listeners.add(listener)
        try:
            yield listener[1]
        finally:
            with self._lock:
                self._listeners.discard(listener)
