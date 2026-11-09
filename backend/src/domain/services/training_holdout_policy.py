"""Whether a training run has DECIDED about its holdout — shared by every training door.

WHY THIS IS NOT IN THE CLI (measured 2026-08-11). The rule existed only as an `argparse`
``parser.error`` inside ``src/scripts/train_model_cli.py``, so it guarded exactly ONE of the
three entrypoints that call ``ModelTrainingPipeline``:

    train_model_cli.py                      holdout guard YES   data_end  8 refs
    train_model.py                          no                  data_end  9 refs
    workers/tasks/training_job_pipeline.py  no                  data_end  0 — no concept of it
    application/services/training_job_service.py  no            data_end  0

The worker path is what admin ``/training/new`` and every scheduled retrain use, and it cannot
reserve a holdout at all. A model trained up to now has ``test_end_date`` on its own training
date, so nothing follows it and the capital cert has no window to score. That is why **43 of 51
existing models can never be validated** — they came through a door with no guard.

The consequence is silent and expensive: the cert dutifully reports ``no_publishable_cell`` and
a reader concludes the BOOK failed, when in fact it was never measurable. Three separate
verdicts were drawn that way in one session before the cause was found.

An `argparse` error cannot be reused by a Celery task. A pure predicate can.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil, sqrt
from typing import Final

from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE
from src.domain.services.min_track_record_length import Z_95
from src.shared.constants.backtest import ARENA_BACKTEST_MIN_ROWS
from src.shared.constants.timeframes import bars_per_day, days_for_bars


class MissingHoldoutDecisionError(ValueError):
    """Raised when a training run neither reserves a holdout nor says it is skipping one."""


#: The message every door shows, so the fix reads identically from a CLI, a worker log or an
#: admin API response. Neither choice is assumed — only FORGETTING is refused.
HOLDOUT_DECISION_REQUIRED = (
    "refusing to train with no holdout: reserve an out-of-sample window by passing a "
    "data-end cutoff (YYYY-MM-DD), or state explicitly that this run trains up to now. "
    "43 of 51 existing models were trained to their own save date and can never be "
    "validated; this rule exists so that is always a decision, never an oversight."
)


#: What a caller writes to ask for the POLICY instead of a date. A word rather than a number, so
#: nobody copies a cutoff that is only correct for one timeframe on one day — and it lives HERE
#: rather than in either door, because the CLI and the admin request must recognise the same token.
DATA_END_AUTO: Final[str] = "auto"

#: The one spelling of a training cutoff, so a CLI flag and an admin request cannot disagree.
#: Midnight UTC because candle timestamps are UTC -- a naive cutoff compares wrongly against them.
DATA_END_FORMAT = "%Y-%m-%d"


class InvalidDataEndCutoffError(ValueError):
    """Raised when a cutoff was supplied but cannot be read as a date."""


def parse_data_end_cutoff(value: object) -> datetime | None:
    """The reserved cutoff as an aware UTC datetime, or None when none was reserved.

    WHY THIS EXISTS (proven 2026-08-21). ``require_holdout_decision`` passed on
    ``custom_params["data_end"]`` while ``ModelTrainingPipeline`` read its cutoff from a
    ``data_end`` KEYWORD that the worker never passed -- so a caller who reserved a holdout got a
    model trained up to now, and the gate reported success. A gate satisfiable without the effect
    it gates is decorative.

    A malformed cutoff RAISES rather than returning None: silently dropping it would reproduce
    exactly the false holdout this function was written to remove.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, DATA_END_FORMAT).replace(tzinfo=UTC)
    except ValueError as exc:
        raise InvalidDataEndCutoffError(
            f"data-end must be {DATA_END_FORMAT.replace('%Y', 'YYYY').replace('%m', 'MM').replace('%d', 'DD')}, got {value!r}"
        ) from exc


def has_holdout_decision(*, data_end: object, no_holdout: bool) -> bool:
    """True when the caller either reserved a holdout or opted out on purpose.

    ``data_end`` is deliberately typed loosely: the CLI passes a parsed date, the worker DTO a
    string, and both must satisfy the same rule. Anything empty-ish counts as "not reserved".
    """
    if no_holdout:
        return True
    if data_end is None:
        return False
    return bool(str(data_end).strip())


def require_holdout_decision(*, data_end: object, no_holdout: bool) -> None:
    """Raise unless the run has decided about its holdout. No return value — a gate, not a query."""
    if not has_holdout_decision(data_end=data_end, no_holdout=no_holdout):
        raise MissingHoldoutDecisionError(HOLDOUT_DECISION_REQUIRED)


#: Bars an automated retrain reserves out of sample. Bound to `ARENA_BACKTEST_MIN_ROWS` rather
#: than chosen here: that constant already answers "how many raw bars before a model can be
#: backtested at all" for the arena, and a holdout smaller than the smallest measurable backtest
#: is a holdout in name only. One number, one meaning.
HOLDOUT_MIN_BARS: Final[int] = ARENA_BACKTEST_MIN_ROWS

#: …and never a shorter CALENDAR window than this, whatever the bar count says. On 5m, 100 bars
#: is about eight hours: real as a sample, meaningless as a market regime. Same recency floor the
#: rolling retraining window uses, for the same reason.
HOLDOUT_MIN_DAYS: Final[int] = 7


#: The trade distribution MinTRL is evaluated against when reporting what a window could prove.
#: Normal (skew 0, raw kurtosis 3) because at training time no returns exist yet to measure —
#: stated as an assumption rather than smuggled in. Real books are usually worse than normal, so
#: this is the OPTIMISTIC end: the answer it gives is a lower bound on what is needed.
CERT_TRADE_DISTRIBUTION_SKEW: Final[float] = 0.0
CERT_TRADE_DISTRIBUTION_KURTOSIS: Final[float] = 3.0

#: WHY THE WINDOW IS NOT SIZED FROM MinTRL, measured 2026-09-18 by trying it. Sizing the holdout to
#: PROVE an annualised Sharpe of 1.0 (the bar `train_model_cli` warns against) needs ~5,900 confirm
#: trades, which at the measured cadence is **9,817 days on 4h and 58,900 on 1d** — longer than the
#: asset has existed. That is not a bug in the arithmetic; it is what MinTRL says about a modest
#: Sharpe, and it is the same wall prod v2 (needs 3,089-5,520, has ~300) and v42 (needs 1,454, has
#: 71) already hit.
#:
#: So the window is sized to the gate that ACTUALLY decides `unmeasured` today —
#: `MIN_TRADES_FOR_SHARPE`, the grader's own fallback floor — and `provable_per_trade_sharpe`
#: reports what that window could establish, so the gap is DISCLOSED rather than papered over.
#: A window that clears the live gate is buildable; a window that clears MinTRL is not, and
#: pretending otherwise would reserve a holdout no training run could ever use.

#: Trades per BAR the reserved window is planned against. MEASURED on the two twins this rule was
#: written from: `1d v42` took 71 trades in 259 bars (0.274) and `4h v411` took 738 in 4,900
#: (0.151). The lower of the two is used, because planning on the faster cadence would under-reserve
#: exactly where the measurement disagrees.
CERT_TRADES_PER_BAR: Final[float] = 0.151

#: How much SELECT costs on top of CONFIRM. The select→confirm door spends a whole window ranking
#: levers and then throws its money away, so the reserved span is CONFIRM plus this share of it.
#: 0.5 matches the split the corpus actually runs (2023-06-01 → 2024-06-01 select against
#: 2024-06-01 → now confirm, 12 months against 27).
CERT_SELECT_SHARE_OF_CONFIRM: Final[float] = 0.5


def expected_confirm_trades(bars: float) -> float:
    """Trades a confirm window of ``bars`` bars is planned to produce, at the measured cadence."""
    return max(0.0, float(bars)) * CERT_TRADES_PER_BAR


def cert_ready_holdout_days(timeframe: str) -> int:
    """Calendar days a run must reserve so its CERT can reach a verdict instead of `unmeasured`.

    THE DEFECT THIS REPLACES, measured 2026-09-18 on two twins of one family trained by the same
    rule: `1d v42` reserved 473 days, confirmed on **71 trades**, and is unmeasurable; `4h v411`
    reserved 1,205 days, confirmed on **738**, and produced a real (failing) verdict. The holdout
    was never the model's problem — it was the arithmetic nobody did.

    `automated_retrain_data_end` sizes the window by `ARENA_BACKTEST_MIN_BARS`, which answers "can
    this be backtested at all". A cert asks for two disjoint windows: SELECT ranks the levers and
    its money is discarded, CONFIRM evaluates ONE pre-committed cell and must carry enough trades
    for its Sharpe to mean anything. So the window is derived in TRADES and converted to days:

        observations = min_track_record_length(target per-trade Sharpe, normal moments)
        confirm bars = observations / measured trades-per-bar
        reserved     = confirm bars * (1 + select share), as calendar days for THIS timeframe

    Which is why a faster timeframe legitimately needs a SHORTER calendar holdout: it buys the same
    number of observations in less time. Raises on an unknown timeframe, via `days_for_bars`.
    """
    confirm_bars = MIN_TRADES_FOR_SHARPE / CERT_TRADES_PER_BAR
    reserved_bars = confirm_bars * (1.0 + CERT_SELECT_SHARE_OF_CONFIRM)
    return days_for_bars(timeframe, bars=ceil(reserved_bars), floor_days=HOLDOUT_MIN_DAYS)


def provable_per_trade_sharpe(timeframe: str, *, holdout_days: int | None = None) -> float | None:
    """The smallest per-trade Sharpe a holdout of this length could ESTABLISH, or None if unknowable.

    The companion to `cert_ready_holdout_days`, and the reason that function is allowed to size
    itself against a trade FLOOR instead of MinTRL: the gap has to be visible. Inverts Bailey &
    Lopez de Prado on the normal moments above — with ``n`` confirm trades,

        n = 1 + (1 - skew*sr + (kurt-1)/4 * sr^2) * (z / sr)^2

    solved for the smallest ``sr`` that fits. A book weaker than the answer cannot be proven on
    this window however good it looks, which is exactly the disclosure the corpus keeps needing.
    """
    days = cert_ready_holdout_days(timeframe) if holdout_days is None else int(holdout_days)
    confirm_days = days / (1.0 + CERT_SELECT_SHARE_OF_CONFIRM)
    trades = expected_confirm_trades(confirm_days * bars_per_day(timeframe))
    if trades <= 1.0:
        return None
    # Solve (1 + (kurt-1)/4 * sr^2) * z^2 / sr^2 = n - 1 for sr, with skew 0 (the assumption above).
    z_squared = Z_95 * Z_95
    denominator = (trades - 1.0) - (CERT_TRADE_DISTRIBUTION_KURTOSIS - 1.0) / 4.0 * z_squared
    if denominator <= 0.0:
        return None  # even an infinite Sharpe cannot be established on this many observations
    return float(sqrt(z_squared / denominator))


def cert_ready_data_end(timeframe: str, *, now: datetime | None = None) -> str:
    """`cert_ready_holdout_days` as the ``YYYY-MM-DD`` cutoff a training door can pass straight in."""
    moment = now or datetime.now(UTC)
    return (moment - timedelta(days=cert_ready_holdout_days(timeframe))).strftime(DATA_END_FORMAT)


def automated_retrain_data_end(timeframe: str, *, now: datetime | None = None) -> str:
    """The cutoff an AUTOMATED retrain reserves, as ``YYYY-MM-DD``.

    MEASURED IN PRODUCTION 2026-09-03, and this function exists because of it: the entire
    `training_jobs` table was 8 rows, all FAILED at `progress=0`, seven of them created in one
    sweep on 2026-08-25 and every one refused by `require_holdout_decision` above. The gate is
    correct — it refuses only FORGETTING — but nothing on the automated path ever REMEMBERED.
    `_finalize_retrain_config` copies the previous run's config snapshot, and that snapshot
    carries neither a cutoff nor an explicit opt-out, so the gate could only ever refuse.

    The consequence was not a slow queue, it was an INERT one: health fires, a PENDING row is
    written, and the job kills itself before touching data. A degraded model therefore stays
    deployed indefinitely, which is the expensive half.

    WHY RESERVE RATHER THAN OPT OUT. Both answers satisfy the gate, and the opt-out would have
    been one line. But this module's own docstring records what that produces: 43 of 51 existing
    models were trained up to their own save date and "can never be validated", so the cert
    reports `no_publishable_cell` and a reader concludes the BOOK failed when it was never
    measurable. An automated retrain is exactly the caller that will never be there to make the
    choice by hand, so it must reserve.

    THE WINDOW SCALES WITH THE TIMEFRAME, via `days_for_bars`: a fixed number of days holds 288x
    more 5m bars than 1d bars, so a fixed cutoff would over-reserve on the fast end and
    under-reserve on the slow end. Raises on an unknown timeframe rather than guessing — a
    fabricated cutoff is a FALSE holdout, which `parse_data_end_cutoff` above already refuses to
    create by a different route.
    """
    moment = now or datetime.now(UTC)
    reserved = days_for_bars(timeframe, bars=HOLDOUT_MIN_BARS, floor_days=HOLDOUT_MIN_DAYS)
    return (moment - timedelta(days=reserved)).strftime(DATA_END_FORMAT)
