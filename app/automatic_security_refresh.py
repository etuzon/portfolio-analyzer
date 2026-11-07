"""Application-owned bounded API work; only its coordinator may apply prices.

Workers fetch/cache market facts. Deadline or cancellation never schedules a
late application callback. A subsequent run can reuse an ongoing fetch while
passing its current candidate to apply, rather than the worker's older metadata.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from threading import Event, RLock
import time
from typing import Any, Callable


class AutomaticSecurityRefresh:
    def __init__(self, max_workers: int = 3):
        self._capacity = min(max(int(max_workers), 1), 3)
        self._pool = ThreadPoolExecutor(max_workers=self._capacity, thread_name_prefix="automatic-security-api")
        self._inflight: dict[str, Any] = {}
        self._lock = RLock()
        self._changed = Event()

    def _submit(self, candidate: dict[str, Any], fetch: Callable):
        key = candidate["security_key"]
        with self._lock:
            if key in self._inflight:
                return self._inflight[key]
            if len(self._inflight) >= self._capacity:
                return None
            future = self._pool.submit(fetch, deepcopy(candidate))
            self._inflight[key] = future

            def release(completed):
                with self._lock:
                    if self._inflight.get(key) is completed:
                        del self._inflight[key]
                self._changed.set()

            future.add_done_callback(release)
            return future

    def run(self, candidates, fetch: Callable, apply: Callable, *, cancelled: Callable[[], bool] = lambda: False,
            timeout_seconds: float = 25) -> dict[str, Any]:
        """Visit all candidates through a sliding window, until deadline/cancel.

        ``checked`` counts completed callback outcomes, including failures;
        ``updated`` counts securities with a positive accepted count. Remaining
        includes both unstarted and unfinished work. Failed callbacks expose only
        their exception class, never messages, URLs or source credentials.
        """
        unique = {candidate["security_key"]: deepcopy(candidate) for candidate in candidates}
        queue = deque(unique.values())
        jobs: dict[str, tuple[dict[str, Any], Any]] = {}
        deadline = time.monotonic() + max(0, float(timeout_seconds))
        stats: dict[str, Any] = {"total": len(unique), "checked": 0, "updated": 0, "accepted": 0,
                                 "failed": 0, "timed_out": 0, "remaining": len(unique),
                                 "cancelled": False, "diagnostics": []}
        while queue or jobs:
            if cancelled():
                stats["cancelled"] = True
                break
            if time.monotonic() >= deadline:
                stats["timed_out"] = len(jobs)
                break
            # One scan can attach an already-running key even when other runs
            # occupy every provider slot; no new executor backlog is created.
            for _ in range(len(queue)):
                if len(jobs) >= self._capacity or cancelled() or time.monotonic() >= deadline:
                    break
                candidate = queue.popleft()
                future = self._submit(candidate, fetch)
                if future is None:
                    queue.append(candidate)
                else:
                    jobs[candidate["security_key"]] = (candidate, future)
            if not jobs:
                self._changed.wait(timeout=min(.02, max(0, deadline - time.monotonic())))
                self._changed.clear()
                continue
            completed, _pending = wait({job[1] for job in jobs.values()},
                                       timeout=min(.05, max(0, deadline - time.monotonic())),
                                       return_when=FIRST_COMPLETED)
            for key, (candidate, future) in list(jobs.items()):
                if future not in completed:
                    continue
                if cancelled() or time.monotonic() >= deadline:
                    # Leave the job unprocessed: neither this run nor the
                    # future's completion callback can perform the write later.
                    break
                try:
                    snapshot = future.result()
                    if cancelled() or time.monotonic() >= deadline:
                        break
                    accepted = apply(candidate, snapshot)
                    if accepted is None:
                        accepted = 0
                    if not isinstance(accepted, (bool, int)) or accepted < 0:
                        raise ValueError("Apply must return a nonnegative accepted count")
                    stats["accepted"] += int(accepted)
                    stats["updated"] += int(accepted > 0)
                except Exception as exc:
                    stats["failed"] += 1
                    stats["diagnostics"].append({"error_type": type(exc).__name__})
                stats["checked"] += 1
                del jobs[key]
        stats["remaining"] = stats["total"] - stats["checked"]
        return stats
