"""Bound ordinary provider work inside the application-owned inventory route.

The AI worker still uses its one authenticated inventory REST request. Slow
provider calls may finish caching evidence, but cannot hide the inventory or
create unbounded background work when the user retries.
"""
from concurrent.futures import ThreadPoolExecutor, wait
from copy import deepcopy
from threading import RLock


class ApiPreflight:
    def __init__(self, max_workers=3):
        self._capacity = max_workers
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="enrichment-api")
        self._inflight = {}
        self._lock = RLock()

    def _submit(self, candidate, fetch):
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

            future.add_done_callback(release)
            return future

    def run(self, candidates, fetch, *, timeout_seconds=25):
        selected = list(candidates)[:3]
        jobs = [(candidate, self._submit(candidate, fetch)) for candidate in selected]
        futures = {future for _, future in jobs if future is not None}
        if futures:
            wait(futures, timeout=max(0, timeout_seconds))
        outcomes = []
        for candidate, future in jobs:
            error_type, code = "TimeoutError", "provider_timeout"
            if future is None:
                error_type = "ProviderWorkInProgress"
            elif future.done():
                try:
                    value = future.result()
                    if not isinstance(value, dict) or value.get("security_key") != candidate["security_key"]:
                        raise ValueError("Invalid provider result")
                    outcomes.append(value)
                    continue
                except Exception as exc:
                    error_type, code = type(exc).__name__, "job_failed"
            outcomes.append({**deepcopy(candidate), "status": "unavailable", "code": code,
                             "available_fields": [], "missing_fields": candidate.get("missing_fields", []),
                             "diagnostic": {"stage": "checking_apis", "code": code,
                                            "error_type": error_type, "http_status": None}})
        return outcomes
