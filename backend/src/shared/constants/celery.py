"""
Shared Celery runtime policy.

WHY this module exists:
- Training task decorators, Celery app defaults, and Redis lock TTLs must use the
  same runtime contract
- Settings already own the environment-backed values; this module turns them into
  one import surface so worker code cannot drift
"""

from __future__ import annotations

from typing import Final

from sqlalchemy.exc import DisconnectionError, OperationalError

from src.infrastructure.config.settings import settings

# Retries should target transient infra failures only (not logic bugs).
CELERY_AUTORETRY_INFRA_EXCEPTIONS: tuple[type[BaseException], ...] = (
    BrokenPipeError,
    ConnectionError,
    OSError,
    TimeoutError,
    OperationalError,
    DisconnectionError,
)

# Broker queue names (``task_routes`` / Beat ``options.queue``) — SoT, no string drift.
# ``CELERY_DEFAULT_QUEUE`` is Celery's built-in fallback queue used when neither
# ``task_routes`` nor an explicit ``queue=`` is set; broker-prune sweeps must
# include it so unrouted messages can never be silently leaked.
CELERY_DEFAULT_QUEUE: Final[str] = "celery"
CELERY_QUEUE_TRAINING: Final[str] = "training"
CELERY_QUEUE_MONITORING: Final[str] = "monitoring"
CELERY_QUEUE_SIGNALS: Final[str] = "signals"
CELERY_QUEUE_ALERTS: Final[str] = "alerts"
CELERY_QUEUE_EMAIL: Final[str] = "email"
CELERY_QUEUE_OHLCV_STREAM: Final[str] = "ohlcv_stream"

CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = "UTC"
CELERY_RESULT_EXPIRES_SECONDS = 24 * 60 * 60
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_DEFAULT_RATE_LIMIT = "10/m"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
#: How long Redis hides a delivered, un-acked message from every other consumer. kombu's default is 1 h, and
#: CELERY_TASK_ACKS_LATE keeps a message un-acked for its whole run, so a run longer than this is handed out again
#: while it still runs -- and the --pool=solo training lane enforces no task_time_limit (a prefork feature).
#: MEASURED 2026-10-23: select-confirm task 67c5830d ran 4,491-5,262 s a delivery and was handed out 13 times. One
#: day outlasts the hard limit, the largest hunt-loop budget (HUNT_LOOP_MAX_TIME_BUDGET_SECONDS) and the longest
#: solo run measured (10 h 13 m, 2026-09-01). The cost: a message whose worker was SIGKILLed waits up to a day to
#: come back; a clean shutdown requeues its un-acked messages at once (kombu's Channel.close).
CELERY_BROKER_VISIBILITY_TIMEOUT_SECONDS: Final[int] = 24 * 60 * 60
# Recycle worker after this much resident memory (KiB) to reduce OOM (SIGKILL) risk.
# 0 = disabled. @see PERFORMANCE_MONITORING.md § WorkerLostError signal 9
CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB = settings.celery_worker_max_memory_per_child_kib
CELERY_WORKER_MAX_TASKS_PER_CHILD = settings.celery_worker_max_tasks_per_child
# Solo-pool equivalent of worker_max_memory_per_child (which is prefork-only). Recycle a
# ``--pool=solo`` worker (monitoring, ohlcv_stream) via warm shutdown above this resident cap.
# 0 = disabled. @see celery_solo_rss_watchdog.py, PERFORMANCE_MONITORING.md § solo-pool memory guard
CELERY_SOLO_RSS_WATCHDOG_MAX_KIB = settings.celery_solo_rss_watchdog_max_kib
# Headline-sentiment refresh cadence (minutes). Must stay < TTL_HEADLINE_SENTIMENT_SNAPSHOT:
# over-refreshing only spawns extra FinBERT scoring children (CPU seconds; the model is no longer
# resident in the worker) for no freshness gain. @see beat_schedule.py, test_headline_sentiment_beat_schedule.py
HEADLINE_SENTIMENT_REFRESH_MINUTES = settings.celery_headline_sentiment_refresh_minutes
CELERY_REDBEAT_LOCK_TIMEOUT_SECONDS = settings.celery_redbeat_lock_timeout
CELERY_BEAT_MAX_LOOP_INTERVAL_SECONDS = settings.celery_beat_max_loop_interval

OHLCV_SYNC_MAX_RETRIES = settings.celery_task_max_retries
OHLCV_SYNC_RETRY_DELAY_SECONDS = settings.celery_task_retry_delay
# SoT: from settings. Sync can exceed under load (many symbols/timeframes, exchange latency).
OHLCV_SYNC_TIME_LIMIT_SECONDS = settings.celery_ohlcv_sync_time_limit
OHLCV_SYNC_SOFT_TIME_LIMIT_SECONDS = settings.celery_ohlcv_sync_soft_limit

OHLCV_BACKFILL_MAX_RETRIES = 1
OHLCV_BACKFILL_TIME_LIMIT_SECONDS = 60 * 60
OHLCV_BACKFILL_SOFT_TIME_LIMIT_SECONDS = 55 * 60

ARENA_REFRESH_MAX_RETRIES = 1
ARENA_REFRESH_TIME_LIMIT_SECONDS = 60 * 60
ARENA_REFRESH_SOFT_TIME_LIMIT_SECONDS = 55 * 60

MODEL_CLEANUP_MAX_RETRIES = 0
MODEL_CLEANUP_TIME_LIMIT_SECONDS = 6 * 60
MODEL_CLEANUP_SOFT_TIME_LIMIT_SECONDS = 5 * 60

TRAINING_EXECUTE_JOB_MAX_RETRIES = 1
TRAINING_DISPATCH_MAX_RETRIES = 1
# Infra autoretry delay for train_model_task (aligned with health rollback / signal outcomes).
TRAINING_DISPATCH_RETRY_DELAY_SECONDS = settings.celery_task_retry_delay
TRAINING_TRIGGER_CHECK_MAX_RETRIES = settings.celery_task_max_retries
TRAINING_TRIGGER_CHECK_RETRY_DELAY_SECONDS = settings.celery_task_retry_delay
TRAINING_TRIGGER_CHECK_RETRY_BACKOFF = True
# Daily trigger check should finish in minutes; avoid inheriting 55-min training limit.
TRAINING_TRIGGER_CHECK_TIME_LIMIT_SECONDS = 20 * 60  # 20 min hard
TRAINING_TRIGGER_CHECK_SOFT_TIME_LIMIT_SECONDS = 15 * 60  # 15 min soft
TRAINING_CRITICAL_TRIGGER_CHECK_MAX_RETRIES = settings.celery_task_max_retries
TRAINING_CRITICAL_TRIGGER_CHECK_RETRY_DELAY_SECONDS = 30
TRAINING_CRITICAL_TRIGGER_CHECK_RETRY_BACKOFF = True
TRAINING_HEALTH_EVALUATION_MAX_RETRIES = settings.celery_task_max_retries
TRAINING_HEALTH_EVALUATION_RETRY_DELAY_SECONDS = 30
TRAINING_SIGNAL_OUTCOME_MAX_RETRIES = settings.celery_task_max_retries
TRAINING_SIGNAL_OUTCOME_RETRY_DELAY_SECONDS = settings.celery_task_retry_delay
TRAINING_HEALTH_ROLLBACK_MAX_RETRIES = settings.celery_task_max_retries
TRAINING_HEALTH_ROLLBACK_RETRY_DELAY_SECONDS = settings.celery_task_retry_delay

GENERATE_SIGNALS_MAX_RETRIES = 1
GENERATE_SIGNALS_RETRY_DELAY_SECONDS = 30
GENERATE_SIGNALS_RETRY_BACKOFF = False
# SoT: from settings so ops can increase without code change. Can exceed under cold/many models.
GENERATE_SIGNALS_TIME_LIMIT_SECONDS = settings.celery_generate_signals_time_limit
GENERATE_SIGNALS_SOFT_TIME_LIMIT_SECONDS = settings.celery_generate_signals_soft_limit

# Long-lived OHLCV WebSocket supervisor task: same delay SoT as other infra retries.
OHLCV_STREAM_RUNNER_RETRY_DELAY_SECONDS = settings.celery_task_retry_delay

# Celery task name SoT: ``@shared_task(name=...)``, ``send_task``, and ``task_routes`` must match.
OHLCV_STREAM_SUPERVISOR_TASK_NAME = "src.workers.tasks.ohlcv_stream_runner.run_ohlcv_stream_supervisor"
CELERY_TASK_NAME_TRAIN_MODEL: Final[str] = "src.workers.tasks.training_tasks.train_model_task"
CELERY_TASK_NAME_EXECUTE_TRAINING_JOB: Final[str] = "src.workers.tasks.training_tasks.execute_training_job"
# Carry rebalance Beat tick. Defined HERE (not in carry_tasks.py) so Beat schedule and
# task-route imports of the name do NOT pull the ccxt-laden carry execution stack into
# celery_app at module load. @see test_celery_app_no_ccxt_at_module_load.
CARRY_REBALANCE_TASK_NAME: Final[str] = "src.workers.tasks.carry_tasks.carry_rebalance_tick"
# Edge-book daily rebalance tick. Name defined HERE (not in edge_book_tasks.py) so Beat + task-route
# imports don't pull the derivatives/ccxt provider stack into celery_app at module load.
EDGE_BOOK_REBALANCE_TASK_NAME: Final[str] = "src.workers.tasks.edge_book_tasks.edge_book_rebalance_tick"
RESEARCH_LOOP_TICK_TASK_NAME: Final[str] = "src.workers.tasks.research_loop_tasks.research_loop_tick"

#: Capital-cert run task. Lived in `workers/tasks/cert_run_tasks` until 2026-08-25, which
#: forced `celery_task_routes` to import that task module just to name a route — and that one
#: import pulled ALL 11 task modules (and the backtester) into every process importing the API.
#: Its 15 siblings already live here; this is the odd one out catching up, not a new home.
CERT_RUN_TASK_NAME: Final[str] = "src.workers.tasks.cert_run_tasks.run_capital_cert_task"
#: Select→confirm (pre-commitment) wraps ``run_select_confirm_cert`` — same control-plane
#: reasons as CERT_RUN_TASK_NAME (worker compute, training queue, dry_run default).
SELECT_CONFIRM_TASK_NAME: Final[str] = "src.workers.tasks.select_confirm_tasks.run_select_confirm_task"
RUN_HUNT_LOOP_TASK_NAME: Final[str] = "src.workers.tasks.research_loop_tasks.run_hunt_loop_now"

#: Admin-triggered registry publish to R2. Same control-plane reasons as CERT_RUN_TASK_NAME: it is
#: a JOB (every model's metadata, features, readouts and multi-MB joblib binaries, sequentially),
#: so it runs on a worker and is routed to a queue a worker actually consumes.
#:
#: Defined HERE rather than in the task module so `celery_task_routes` can name the route without
#: importing the task — the same reason the 2026-08-25 note above gives for CERT_RUN_TASK_NAME:
#: one such import pulled ALL task modules into every process that imports the API.
REGISTRY_PUBLISH_R2_TASK_NAME: Final[str] = "src.workers.tasks.registry_publish_tasks.publish_registry_to_r2_task"
#: Admin-triggered CAND-WEIGHTLESS repair: copies a candidate bundle's missing required file from its version key.
#: Storage I/O, so a job on a worker, routed and named here for the publish task's reasons.
CANDIDATE_REPAIR_TASK_NAME: Final[str] = "src.workers.tasks.candidate_repair_tasks.repair_weightless_candidates_task"

#: Which model corpus a publish job targets. There are genuinely TWO, keyed differently
#: (`ml-gate-leverage-capital-cert.md`): `hypothesis` books are keyed by the `hypothesis` field
#: inside their artifact and live under `edge_hunt_models/`; `model_spec` books are keyed
#: `symbol x timeframe x model_type x version` and live under `apps/api/models/`.
#:
#: Here, next to the task name and for the same reason: the ADMIN ROUTE validates the value before
#: enqueueing, and it must do so without importing the worker task module — one such import once
#: pulled ALL task modules into every process that imports the API.
CORPUS_HYPOTHESIS: Final[str] = "hypothesis"
CORPUS_MODEL_SPEC: Final[str] = "model_spec"
CORPUS_BOTH: Final[str] = "both"
PUBLISHABLE_CORPORA: Final[tuple[str, ...]] = (CORPUS_HYPOTHESIS, CORPUS_MODEL_SPEC, CORPUS_BOTH)

#: How often the OHLCV stream self-heal re-decides whether a supervisor is missing.
#:
#: ONE number, read by the beat schedule AND by the queue expiry below, because they must agree:
#: the expiry exists so a queued supervisor cannot outlive the decision that queued it.
OHLCV_SUPERVISOR_SELF_HEAL_MINUTES: Final[int] = 2

#: Lifetime of a QUEUED supervisor task.
#:
#: MEASURED 2026-08-25: a supervisor sat in `ohlcv_stream` with `expires: None`, one message, flat
#: for 30 seconds and surviving a full restart of every service -- because a Celery message lives
#: in Redis, not in a process. The stream worker is `--pool=solo --concurrency=1` and its
#: supervisor is long-lived, so the single slot never frees and that copy could never start.
#: `enqueue_missing_ohlcv_stream_supervisors` then declined to enqueue on EVERY tick (correctly --
#: that guard was added after a 2,642-task backlog), and warned about it each time, forever.
#:
#: Both halves were right; together they jammed. An expiry breaks the jam without weakening
#: either: a copy that has not started within one self-heal period is stale by construction, since
#: the next tick re-decides anyway and can only decide correctly against an empty queue.
#:
#: Derived from the cadence rather than chosen, so changing the schedule cannot leave supervisors
#: queued for the old interval.
OHLCV_SUPERVISOR_QUEUE_EXPIRY_SECONDS: Final[int] = OHLCV_SUPERVISOR_SELF_HEAL_MINUTES * 60
XS_TREND_PAPER_FORWARD_TASK_NAME: Final[str] = "src.workers.tasks.xs_trend_paper_forward_tasks.xs_trend_paper_forward_tick"
VT_17_MOMENTUM_PAPER_FORWARD_TASK_NAME: Final[str] = "src.workers.tasks.vt_17_momentum_paper_forward_tasks.vt_17_momentum_paper_forward_tick"
FUNDING_ML_CARRY_PAPER_FORWARD_TASK_NAME: Final[str] = "src.workers.tasks.funding_ml_carry_paper_forward_tasks.funding_ml_carry_paper_forward_tick"
ML_SHORTLIST_PAPER_FORWARD_TASK_NAME: Final[str] = "src.workers.tasks.ml_shortlist_paper_forward_tasks.ml_shortlist_paper_forward_tick"
#: Daily refresh of the lab OHLCV caches every lab book fits on (OHLCV-FRESH-1). Named here, with its
#: siblings, because the task, its route and its beat entry all need it.
LAB_OHLCV_REFRESH_TASK_NAME: Final[str] = "src.workers.tasks.lab_ohlcv_refresh_tasks.lab_ohlcv_refresh_tick"

#: Liquidation-cluster Telegram alert. Declared HERE, with the other task names, rather than in
#: the task module: `celery_task_routes` and `beat_schedule` both need it, and a dotted path typed
#: twice is how a task ends up unrouted — landing on a queue no worker consumes and sitting
#: `pending` forever, which has already been a real prod bug in this repo.
LIQUIDATION_CLUSTER_ALERT_TASK_NAME: Final[str] = "src.workers.tasks.liquidation_cluster_alerts.run_liquidation_cluster_alerts"

#: Aggressor-flow spike sweep. One aggTrades batch per cycle -- the websocket was MEASURED at
#: 3.1 msg/s, so a pull covers minutes of tape without a socket lifecycle in the worker.
DELTA_SPIKE_ALERT_TASK_NAME: Final[str] = "src.workers.tasks.delta_spike_alerts.run_delta_spike_alerts"
#: 5m taker-delta burst sweep (DELTA-1): a VOLATILITY alert scored on closed USDT-M futures bars.
TAKER_DELTA_BURST_ALERT_TASK_NAME: Final[str] = "src.workers.tasks.taker_delta_burst_alerts.run_taker_delta_burst_alerts"
MARKET_PULSE_DIGEST_TASK_NAME: Final[str] = "src.workers.tasks.market_pulse_digest.run_market_pulse_digest"
WHALE_LIQUIDATION_ALERT_TASK_NAME: Final[str] = "src.workers.tasks.whale_liquidation_alerts.run_whale_liquidation_alerts"
#: How often the whale sweep runs. Named once because the ROTATION is derived from it: the beat
#: schedule's crontab and the task's rotation universe must agree, and a "5" typed in two places is
#: the drift that makes a level expire before its address comes round again.
#:
#: 5 -> 1, with the window cut 1,000 -> 200 in the SAME change so throughput is untouched. The
#: sweep is paced HTTP waiting against Hyperliquid's weight budget, and while it waits it owns an
#: ~870 MB prefork child. MEASURED 2026-09-16 on prod `celery-worker` (80 tasks, 0.36 h): the sweep
#: ran 126.6 s while every other task finished inside 23.5 s, and replaying those arrivals through
#: one server put p95 added delay at 128.5 s -- `generate_live_signals` and a BURST alert among the
#: delayed. Excluding this one task dropped that p95 to 13.9 s, so it alone caused ~90% of the
#: head-of-line blocking. A shorter slice at a proportionally shorter interval is the same work.
WHALE_LIQUIDATION_SWEEP_INTERVAL_MINUTES: Final[int] = 1

#: Addresses asked per sweep. DELIBERATELY NOT `DEFAULT_ADDRESS_SAMPLE`, which `whale_cohort_freeze`
#: also reads -- retuning the sweep through that shared constant would silently retune a second task
#: nobody was measuring.
#:
#: 200 -> 150, because 200 MISSED THE BUDGET IN PRODUCTION. b3730d87f shipped 200 on the
#: arithmetic that 200 x weight 2 / 1,200 budget = 20 s, and prod then measured 39.41 s and
#: 39.31 s: pacing is a floor, not the duration, and per-request latency plus the mark fetch and
#: the merge roughly double it. 150 x 2.0 = 30 s, which is the head-of-line budget.
#:
#: This LOWERS venue load (150/min against the old 1,000-per-5-minutes = 200/min) rather than
#: raising it, and a full rotation of the 44,862-address leaderboard takes 44,862 / 150 = 299 min
#: = 5.0 h -- inside `WHALE_POSITION_MAX_AGE_S` (6 h) with an hour of margin, so a level is still
#: refreshed before it expires. `whale_rotation_universe` yields 360 x 150 = 54,000, comfortably
#: over the leaderboard.
WHALE_LIQUIDATION_SWEEP_WINDOW: Final[int] = 150
WHALE_COHORT_FREEZE_TASK_NAME: Final[str] = "src.workers.tasks.whale_cohort_freeze.run_whale_cohort_freeze"
LANE_B_ELASTICNET_4H_PAPER_FORWARD_TASK_NAME: Final[str] = (
    "src.workers.tasks.lane_b_elasticnet_4h_paper_forward_tasks.lane_b_elasticnet_4h_paper_forward_tick"
)
VRP_PAPER_FORWARD_TASK_NAME: Final[str] = "src.workers.tasks.vrp_paper_forward_tasks.vrp_paper_forward_tick"
EDGE_BOOK_PAPER_FORWARD_TASK_NAME: Final[str] = "src.workers.tasks.edge_book_paper_forward_tasks.edge_book_paper_forward_tick"
VOL_SURFACE_FORWARD_LOG_TASK_NAME: Final[str] = "src.workers.tasks.vol_surface_forward_log_tasks.vol_surface_forward_log_tick"
#: L2 bookTicker (touch-of-book) forward-log tick — self-collects Binance best bid/ask FORWARD so a
#: microstructure history accumulates for a future backtest (owner 2026-07-24 "START"). DATA ONLY.
L2_BOOK_FORWARD_LOG_TASK_NAME: Final[str] = "src.workers.tasks.l2_book_forward_log_tasks.l2_book_forward_log_tick"

# Canonical no-op result for a research-loop task that did not run. SoT for the
# @research_loop_task decorator.
#
# TWO reasons, deliberately distinct. Both skip and both report SUCCESS (a skip is not a failure,
# and raising here would feed the redelivery loop `replay_stored_result_if_finished` exists to
# stop) — but they mean opposite things to an operator, and collapsing them cost real time on
# 2026-09-03: a hunt run reported `research_loop_enabled=false` while the API and a standalone
# process both read the switch as TRUE, so the switch got hunted instead of the failing check.
# Worse, the endpoint takes its redis claim on the API's reading and the worker releases it only
# after passing its own — so a disagreement leaks the claim for the full 6h TTL. One was measured
# holding a finished task's id with 5.6h left, blocking every re-run of that hypothesis.
RESEARCH_LOOP_SKIPPED_DISABLED_STATUS: Final[str] = "SKIPPED_DISABLED"
#: The master switch is genuinely off.
RESEARCH_LOOP_DISABLED_REASON: Final[str] = "research_loop_enabled=false"
#: The enabled-check itself raised; fail-secure treated it as off. The switch may well be ON.
RESEARCH_LOOP_CHECK_FAILED_REASON: Final[str] = "research_loop_enabled_check_failed"

BACKTEST_EXECUTE_MAX_RETRIES = 2
BACKTEST_EXECUTE_RETRY_DELAY_SECONDS = 30
BACKTEST_EXECUTE_RETRY_BACKOFF = True

TRAINING_TIME_LIMIT = settings.celery_training_time_limit
TRAINING_SOFT_TIME_LIMIT = settings.celery_training_soft_limit
#: The most ONE hunt-loop run may ask for through the run-loop route: 4 x the soft limit. MEASURED 2026-09-28:
#: dvs_ml_feat_full needed 10,234 s for its 4h slot alone, so the default budget can never measure an ML-zoo
#: hypothesis; a per-run budget up to this ceiling can, one timeframe per run.
HUNT_LOOP_MAX_TIME_BUDGET_SECONDS: Final[float] = 4 * TRAINING_SOFT_TIME_LIMIT
TRAINING_TASK_DISPATCH_EXPIRES = settings.celery_training_dispatch_expires

# If a job waits longer than a full execution window in the queue, its DB/runtime
# view is already stale. Keep the execute-job expiry aligned with the hard limit.
TRAINING_EXECUTE_JOB_EXPIRES = TRAINING_TIME_LIMIT
TRAINING_LOCK_TIMEOUT_SECONDS = TRAINING_TIME_LIMIT

# Celery 5.6 docs: `worker_process_init` should not block more than ~4s or the child may be
# killed. Our real init (Numba + ccxt load_markets + Redis) often exceeds 4s; the prefork
# handshake uses CELERY_WORKER_PROC_ALIVE_TIMEOUT_SECONDS instead. Kept for tests/docs parity
# with Celery guidance (not used as the model-prewarm deadline — see below).
# @see https://docs.celeryq.dev/en/stable/userguide/signals.html#worker-process-init
CELERY_WORKER_PROCESS_INIT_MAX_SECONDS = 4.0

# Max wall time for loading production models into the signal use case **after** Numba and
# OHLCV prewarm complete. Separate from CELERY_WORKER_PROCESS_INIT_MAX_SECONDS: a deadline
# of (t0 + 4s) meant OHLCV alone could exhaust the budget and skip every model (loaded=0).
# @see prewarm_worker_pool_child in celery_app.py
CELERY_SIGNAL_MODEL_PREWARM_MAX_SECONDS = 8.0

# Prefork pool: parent waits for each child to send the "UP" readiness handshake.
# Celery default (~4s) is shorter than our real init: Numba + ccxt load_markets (1000s of
# markets) + Redis + model prewarm — children were SIGKILL'd in a tight loop with
# "Timed out waiting for UP message".
# @see https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-proc-alive-timeout
CELERY_WORKER_PROC_ALIVE_TIMEOUT_SECONDS = 60.0
