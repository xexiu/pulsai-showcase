"""Celery and paper-trading worker limits (settings §23-24)."""

from pydantic import AliasChoices, Field

# MEASURED post-prewarm floor of a Celery prefork child (KiB). `worker_process_init` prewarms
# Numba JIT + polars + the ccxt market cache + joblib production models before any task runs.
#   2026-08-06, darwin/py3.11: five live children sat at 872-878 MB, 6-9 s old (3,680 markets).
#   2026-10-01, darwin/py3.11: 538 MB, replaying the child's own prewarm step by step after
#     176985f71 scoped the binance market template to its 756 USDT-quoted markets (865 -> 538 MB).
# The old 900_000 left the derived cap ~1 GB above a child instead of the designed 700 MB.
# Prod pins its own cap (CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB=1600000 on celery-worker), and
# there children are replaced by CELERY_WORKER_MAX_TASKS_PER_CHILD (150) first: measured
# 2026-10-01, ForkPoolWorker-19 and -20 each ran exactly 150 tasks in ~1.5 h and were replaced.
CELERY_CHILD_POST_PREWARM_BASELINE_KIB = 560_000

# Growth a child may add on top of that baseline before it is recycled as leaking.
CELERY_CHILD_GROWTH_HEADROOM_KIB = 700_000

# MEASURED resident floor of the SOLO workers doing their job (KiB), 2026-08-21, darwin/py3.11.
# The cap must clear the HIGHEST of them, because one constant arms every solo worker:
#
#   monitoring   1_552_400 peak  — six consecutive watchdog trips at 924_688 / 945_792 / 948_528 /
#                                  1_497_000 / 1_527_824 / 1_552_400, with FinBERT (~1.3 GB)
#                                  loaded 14 times in a single log
#   training     2_406_400 flat  — six samples, 10 s apart, IDENTICAL every time: not a leak, just
#                                  what polars + xgboost + the joblib prod models + the ccxt market
#                                  cache weigh once prewarmed
#
# A first pass at this fix used 1_600_000, sized on the monitoring floor alone. The training worker
# then measured ABOVE it — the same "cap under the process floor" defect one worker over. Measuring
# BOTH before picking the number is the whole point; the prefork cap above learned this first.
CELERY_SOLO_POST_MODEL_BASELINE_KIB = 2_500_000

# Growth a solo worker may add on top of that baseline before it is recycled as leaking.
#
# 400_000 rather than the prefork child's 700_000, and the difference is forced, not stylistic.
# The window here is genuinely narrow: the heaviest legitimate floor is 2_406_400 (training) and
# the pathology this watchdog exists for is 2_936_012 (Railway monitoring, 261 MB import ->
# 2.8 GB resident). Only ~520 MB separates "working" from "leaking", so 700_000 of headroom would
# put the cap at 3_200_000 -- ABOVE the leak, and the guard would stop catching the one case it
# was written for. 400_000 puts it at 2_900_000: clears both measured floors, still trips the leak.
#
# That narrowness is the argument for a PER-QUEUE baseline (argv already carries `--queues=`, so
# the worker can identify itself at arm time). One constant serving a 1.5 GB worker and a 2.4 GB
# worker is a compromise, not a design.
CELERY_SOLO_GROWTH_HEADROOM_KIB = 400_000


class SettingsOpsWorkersMixin:
    celery_task_max_retries: int = 3
    celery_task_retry_delay: int = 60  # seconds
    celery_training_time_limit: int = 3600  # 1 hour
    celery_training_soft_limit: int = 3300  # 55 min
    celery_training_dispatch_expires: int = 1800  # Drop stale trigger-dispatch tasks after 30 min
    celery_backtest_time_limit: int = 1800  # 30 min
    # Live signals: soft 5 min, hard 5.5 min (configurable; can exceed under cold/many models)
    celery_generate_signals_time_limit: int = 330
    celery_generate_signals_soft_limit: int = 300
    # RedBeat: lock TTL must exceed worst-case gap between tick() + extend() calls.
    # If beat_max_loop_interval and lock_timeout are both ~300s, jitter can expire the key
    # before extend() → redis.exceptions.LockNotOwnedError (Railway).
    celery_beat_max_loop_interval: int = 60  # seconds; caps how long beat sleeps between ticks
    celery_redbeat_lock_timeout: int = 900  # 15 min; slack vs tick interval
    # OHLCV sync: can exceed under load (cold CCXT, rate limits, many timeframes).
    # Defaults raised after real runs hit 12m soft (720s) on single-symbol / 7 TF / 1d lookback.
    celery_ohlcv_sync_time_limit: int = 30 * 60  # 30 min hard
    celery_ohlcv_sync_soft_limit: int = 25 * 60  # 25 min soft (must stay < hard)
    # 0 = auto-detect: min(cpu_count // 2, 4) in dev, 2 in production
    celery_worker_concurrency: int = 0
    # Memory recycle cap per prefork child (KiB). 0 disables recycling.
    # Keep env-configurable so production can tune churn vs OOM risk without code changes.
    #
    # The cap MUST sit above CELERY_CHILD_POST_PREWARM_BASELINE_KIB, so it is derived from it
    # rather than written as a literal. It was 512_000 -- BELOW the ~870 MB a child weighs the
    # moment it finishes prewarming -- so every child was born already over the limit and was
    # recycled immediately: respawn -> 2.3 s prewarm -> recycle, forever. Locally that reached
    # ForkPoolWorker-9482 with children dying as WorkerLostError signal 11 (SIGSEGV), because a
    # child terminated mid native C-extension call does not unwind cleanly. A recycle cap under
    # the process floor cannot catch a leak; it only guarantees churn.
    celery_worker_max_memory_per_child_kib: int = Field(
        default=CELERY_CHILD_POST_PREWARM_BASELINE_KIB + CELERY_CHILD_GROWTH_HEADROOM_KIB,
        ge=0,
        validation_alias=AliasChoices("CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB"),
        description=("Celery prefork child memory recycle cap in KiB; 0 disables recycle (env CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB)"),
    )
    # Recycle prefork child after N tasks to prevent thread pool / aiohttp leaks (0 = disabled).
    celery_worker_max_tasks_per_child: int = Field(
        default=150,
        ge=0,
        validation_alias=AliasChoices("CELERY_WORKER_MAX_TASKS_PER_CHILD"),
        description=("Celery prefork child task recycle count; 0 disables (env CELERY_WORKER_MAX_TASKS_PER_CHILD)"),
    )
    # Solo-pool RSS watchdog cap (KiB). 0 disables.
    # WHY: ``worker_max_memory_per_child`` above is PREFORK-ONLY — a no-op for ``--pool=solo``
    # workers (monitoring, ohlcv_stream) which run tasks inline with no child to recycle. Those
    # workers grew unbounded on Railway (monitoring: 261 MB import -> 2.8 GB resident). This is the
    # solo equivalent: above the cap the worker warm-shuts-down so the ALWAYS supervisor respawns it.
    #
    # The cap MUST sit above CELERY_SOLO_POST_MODEL_BASELINE_KIB, so it is DERIVED from it rather
    # than written as a literal — the identical mistake the prefork cap above made. It was
    # `900 * 1024` (900 MiB), BELOW the ~1.3 GB this worker weighs once FinBERT is resident, so
    # every sample was already over the limit: respawn -> load FinBERT -> over cap -> warm
    # shutdown -> repeat, six times in three minutes on 2026-08-21, completing no work. A recycle
    # cap under the process floor cannot catch a leak; it only guarantees churn.
    celery_solo_rss_watchdog_max_kib: int = Field(
        default=CELERY_SOLO_POST_MODEL_BASELINE_KIB + CELERY_SOLO_GROWTH_HEADROOM_KIB,
        ge=0,
        validation_alias=AliasChoices("CELERY_SOLO_RSS_WATCHDOG_MAX_KIB"),
        description=("Solo-pool worker RSS recycle cap in KiB; 0 disables (env CELERY_SOLO_RSS_WATCHDOG_MAX_KIB)"),
    )
    # Headline-sentiment snapshot refresh cadence (minutes; use a divisor of 60 for clean
    # wall-clock alignment). MUST stay below TTL_HEADLINE_SENTIMENT_SNAPSHOT (30m).
    # Default 5 = macro/news product SLA (ceasefire, Fed, etc. visible within one cycle).
    # FinBERT no longer loads in this worker: it scores in a spawned child that exits, and the
    # page cache it filled is evicted (headline_sentiment_finbert_in_child_process). Cadence now
    # costs one child spawn per cycle that has uncached headlines (16.7 s measured on prod), not
    # resident memory -- so lowering it saves CPU seconds, not the GB-minutes the bill is made of.
    celery_headline_sentiment_refresh_minutes: int = Field(
        default=5,
        ge=1,
        le=30,
        validation_alias=AliasChoices("CELERY_HEADLINE_SENTIMENT_REFRESH_MINUTES"),
        description=("Headline sentiment refresh cadence in minutes (env CELERY_HEADLINE_SENTIMENT_REFRESH_MINUTES)"),
    )
    # When True (default), Celery workers whose argv declares the ``ohlcv_stream`` queue
    # auto-enqueue ``run_ohlcv_stream_supervisor`` at ``worker_ready`` (Phase 2 Redis tier).
    # Set ``PULSAI_BOOT_OHLCV_STREAM_SUPERVISORS=false`` (or 0/no/off) to skip enqueue; live
    # signals then use REST for OHLCV when heartbeats are missing/stale.
    boot_ohlcv_stream_supervisors: bool = Field(
        default=True,
        validation_alias=AliasChoices("PULSAI_BOOT_OHLCV_STREAM_SUPERVISORS"),
        description="Auto-enqueue OHLCV WS supervisor at boot on ohlcv_stream workers (env PULSAI_BOOT_OHLCV_STREAM_SUPERVISORS)",
    )
    # Safety gate for non-default exchanges in the stream supervisor bootstrap policy.
    # Default False keeps current production architecture Binance-only.
    # Enable only when ALL production models were trained/promoted with another venue.
    ohlcv_stream_allow_non_binance_exchange: bool = Field(
        default=False,
        validation_alias=AliasChoices("PULSAI_OHLCV_STREAM_ALLOW_NON_BINANCE_EXCHANGE"),
        description=(
            "Allow ohlcv_stream worker boot on non-Binance exchange inferred from production "
            "model metadata (env PULSAI_OHLCV_STREAM_ALLOW_NON_BINANCE_EXCHANGE)"
        ),
    )
    # When True, OHLCV stream supervisor deletes namespaced tail + heartbeat keys on cold
    # start so dev hot-reload does not serve stale Redis from a prior process generation.
    # Default: True in development, False in staging/production (override via env).
    clear_ohlcv_stream_redis_on_supervisor_start: bool = Field(
        default=False,
        validation_alias=AliasChoices("PULSAI_CLEAR_OHLCV_STREAM_REDIS_ON_SUPERVISOR_START"),
        description=(
            "Clear namespaced ohlcv tail+heartbeat on supervisor cold start "
            "(env PULSAI_CLEAR_OHLCV_STREAM_REDIS_ON_SUPERVISOR_START; default on in development)"
        ),
    )

    # Epic B deleted the paper_trading_* env vars (lifecycle sync,
    # retention purge, swap reconcile refresh) along with the Celery tasks
    # that read them. Railway env values will get unset on the next deploy.
