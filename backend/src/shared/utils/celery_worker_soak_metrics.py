"""Process metrics for Celery worker soak harness."""

from __future__ import annotations

import resource
import sys
import threading
from dataclasses import dataclass

__all__ = [
    "SoakSnapshot",
    "capture_soak_snapshot",
    "rss_mb",
    "soak_delta_exceeds_threshold",
]


@dataclass(frozen=True, slots=True)
class SoakSnapshot:
    threads: int
    rss_mb: float


def rss_mb() -> float:
    """Resident set size in MiB (platform-specific ``ru_maxrss`` units)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = float(usage.ru_maxrss)
    platform = sys.platform
    if platform == "darwin":
        return rss / (1024.0 * 1024.0)
    return rss / 1024.0


def capture_soak_snapshot() -> SoakSnapshot:
    return SoakSnapshot(threads=threading.active_count(), rss_mb=rss_mb())


def soak_delta_exceeds_threshold(
    before: SoakSnapshot,
    after: SoakSnapshot,
    *,
    max_thread_delta: int,
    max_rss_mb_delta: float,
) -> tuple[bool, str]:
    thread_delta = after.threads - before.threads
    if thread_delta > max_thread_delta:
        return (
            True,
            f"thread delta {thread_delta:+d} exceeds cap {max_thread_delta}",
        )

    rss_delta = after.rss_mb - before.rss_mb
    if rss_delta > max_rss_mb_delta:
        return (
            True,
            f"RSS delta {rss_delta:+.1f} MiB exceeds cap {max_rss_mb_delta:.1f} MiB",
        )

    return False, ""
