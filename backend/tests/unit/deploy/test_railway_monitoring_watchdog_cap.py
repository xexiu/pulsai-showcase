"""The prod monitoring worker carries its OWN solo-pool RSS watchdog cap (MON-LEAK, 2026-10-02).

IMPORTERS/CALLERS: pytest only. AFFECTED API: none -- reads .railway/railway.ts and the settings
default. DATA SCHEMAS: none.

WHY: one constant (CELERY_SOLO_RSS_WATCHDOG_MAX_KIB, default 2,900,000 KiB) arms every solo worker,
and it is sized for the 2.4 GB local TRAINING solo worker. On prod the monitoring worker starts at
~0.68 GB and its main process kept growing under that cap: measured 2026-10-01 17:11 -> 2026-10-02
08:06 UTC, the floor between FinBERT-child spikes rose 0.68 -> 2.76 GB (+0.06 GB/h of drift, plus a
step after each in-process lab paper-forward tick), and the watchdog never tripped. Railway bills
that floor by the GB-minute. The ~30-minute container spikes are the SPAWNED FinBERT child, which the
watchdog does not count (ru_maxrss of the main process), so a cap on the main process sees the floor.

Two bounds, both from the 08-21 incident written up in settings_ops_workers.py: a cap at or under
the process floor restarts the worker forever (six warm shutdowns in three minutes), and a cap above
the default protects nothing.

REUSE-AUDIT: considered tests/unit/deploy/test_dockerfile_*.py -- they read the Dockerfile, not
railway.ts; considered tests/unit/workers/test_celery_solo_rss_watchdog.py -- it tests the watchdog's
behaviour, not which cap a deployed service gets. Nothing else reads railway.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.infrastructure.config.settings_sections.settings_ops_workers import (
    CELERY_SOLO_GROWTH_HEADROOM_KIB,
    CELERY_SOLO_POST_MODEL_BASELINE_KIB,
)

_RAILWAY_TS = Path(__file__).resolve().parents[5] / ".railway" / "railway.ts"
_SERVICE = "celery-worker-monitoring"
_KEY = "CELERY_SOLO_RSS_WATCHDOG_MAX_KIB"

#: MEASURED 2026-10-01: the prod monitoring container right after a restart (17:11 UTC, 0.68 GB).
_MONITORING_FRESH_FLOOR_KIB = 680 * 1024
#: The cap must clear the fresh floor by at least this factor, or ordinary drift restarts it hourly.
_MIN_HEADROOM_FACTOR = 2.0


def _service_block(source: str, service: str) -> str:
    start = source.index(f"service('{service}'")
    following = source.find("service('", start + 1)
    return source[start : following if following != -1 else len(source)]


def _declared_cap_kib() -> int:
    block = _service_block(_RAILWAY_TS.read_text(encoding="utf-8"), _SERVICE)
    match = re.search(rf"{_KEY}:\s*'(\d+)'", block)
    assert match, f"{_SERVICE} declares no literal {_KEY} in railway.ts -- it inherits the 2.9 GB default"
    return int(match.group(1))


def test_the_monitoring_service_declares_its_own_cap() -> None:
    assert _declared_cap_kib() > 0


def test_the_cap_clears_the_fresh_monitoring_floor() -> None:
    assert _declared_cap_kib() >= _MONITORING_FRESH_FLOOR_KIB * _MIN_HEADROOM_FACTOR


def test_the_cap_is_tighter_than_the_default_that_never_tripped() -> None:
    assert _declared_cap_kib() < CELERY_SOLO_POST_MODEL_BASELINE_KIB + CELERY_SOLO_GROWTH_HEADROOM_KIB


def test_the_block_reader_finds_the_service_it_is_asked_for() -> None:
    """Canary: if the service is renamed the test must fail loudly, not pass on another block."""
    block = _service_block(_RAILWAY_TS.read_text(encoding="utf-8"), _SERVICE)
    assert "--queues=monitoring" in block
