"""The four coordinates that address a ModelSpec book — declared ONCE, in two requiredness shapes.

Owner, 2026-09-11: "shouldnt we jsut use an parent class (base class) and everything extends from
it (sot) and ONLY overwrite if needs something custom??? :S"

YES, AND THE COUNT SAYS SO. Measured across 1,856 files / 594 pydantic models / 4,058 annotated
fields under `src/`:

    field         required  defaulted   total
    symbol              80         19      99
    timeframe           66         23      89
    model_type          12         20      32
    exchange            15          8      23
    version             18          4      22

`symbol` is written out NINETY-NINE times. That is not four call sites arguing for an
abstraction; it is duplication at the scale SoT exists for. The repo already uses this exact
pattern elsewhere -- `SklearnFeatureImportanceMixin` (5 users), `BacktestRequestExitSizingFields`,
`BacktestRequestValidatorsMixin` -- just never for identity.

PATTERN + ANTI-FIT (CODING_STANDARDS 3.1). The row invoked is a shared SCHEMA MIXIN: composition
of field declarations, not inheritance of behaviour. The anti-pattern to clear is
ARCHITECTURE_PATTERNS 9.2 Over-abstraction -- "depth without leverage". It does not apply here:
the leverage is 99 + 89 declarations collapsing to one, and the depth added at call sites is ZERO
(a field mixin introduces no indirection; the fields still read as fields, and nothing has to be
traced through a factory to find the real code). 9.1 Golden hammer does not apply either -- the
two-class split is FORCED by the measured requiredness split, not chosen for tidiness; the single
base was the prettier option and the data rejected it.

WHY TWO CLASSES AND NOT ONE. The requiredness genuinely SPLITS, so a single parent would have to
be wrong for one population: `symbol` is 80 required against 19 defaulted, `timeframe` 66 against
23, and `model_type` is MAJORITY defaulted (20 of 32). Forcing "required" everywhere would break
the deliberate convenience defaults on user-facing backtest/benchmark endpoints
(`symbol='BTC/USDT'`); forcing "optional" everywhere would re-legalise the `model_type='unknown'`
sentinel that was writing real artifacts into a literal `unknown/` directory.

WHAT IS ACTUALLY SHARED -- and it is not requiredness. The TYPE, the DESCRIPTION and the
VALIDATION are identical in all 99 cases; only optionality differs. That is the whole payoff:
`timeframe` gets ONE validator asserting band membership instead of 89 independent declarations,
any one of which can quietly accept `3d` or `1m`. The band itself is READ from `timeframe_bands`,
never retyped here -- `.claude/rules/full-htf-grid-always.md` records four prose sources drifting
to a four-member HTF band for two weeks because the members were written out by hand.

LAYER: `shared/dto/`, not `domain/`. Per DDD_PATTERNS' decision matrix this is "just data
transformation" with no business rule and no state transition, so it is deliberately NOT a domain
value object. `shared/dto/` already holds exactly this kind of cross-layer DTO
(`tradable_classic_signal.py`), so both `api/` and `application/` can import it without either
depending on the other.

REUSE-AUDIT: band membership comes from `shared.constants.timeframe_bands` (`HIGHER_TIMEFRAMES` /
`LOWER_TIMEFRAMES`, both DERIVED from `TimeframeDefinition.band`); nothing here re-lists a band or
re-implements symbol handling, which callers already normalise.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.shared.constants.timeframe_bands import HIGHER_TIMEFRAMES, LOWER_TIMEFRAMES

#: Every timeframe a MODEL may be addressed at, derived from the band registry rather than typed.
#: `3d` / `1w` (chart-only) sit outside both bands on purpose, so they are rejected here rather
#: than silently sorted into a band by duration. (`1m` is an LTF member since 2026-10-11.)
MODEL_TIMEFRAMES: frozenset[str] = frozenset(HIGHER_TIMEFRAMES) | frozenset(LOWER_TIMEFRAMES)

_SYMBOL_DESC = "Trading pair, e.g. BTC/USDT."
_TIMEFRAME_DESC = "Candle timeframe. Must be a member of the HTF or LTF band (see timeframe_bands)."
_VERSION_DESC = "Model version integer, e.g. 51."
_MODEL_TYPE_DESC = (
    "e.g. gradient_boosting_clf. Versions are allocated PER model_type, so symbol+timeframe+"
    "version does not identify a book: measured 2026-09-11, 5 of 204 local version slots carry "
    "the same vN under more than one type, including btc_usdt_1d v2 - the production slot."
)


def _validate_timeframe(value: str | None) -> str | None:
    """One membership check, shared by both variants.

    Returns ``None`` untouched so the optional variant can reuse it: absent is a legitimate answer
    there, and only a PRESENT value has to name a real timeframe.
    """
    if value is None:
        return None
    if value not in MODEL_TIMEFRAMES:
        msg = f"timeframe {value!r} is not a model timeframe; expected one of {sorted(MODEL_TIMEFRAMES)}"
        raise ValueError(msg)
    return value


class ModelIdentity(BaseModel):
    """All four coordinates, REQUIRED — for requests that address one specific book.

    Publish, promote and artifact-upload belong here: each writes to a key BUILT from these four,
    so a missing one is not a convenience, it is a write to a path nobody chose.
    """

    symbol: str = Field(min_length=1, description=_SYMBOL_DESC)
    timeframe: str = Field(min_length=1, description=_TIMEFRAME_DESC)
    version: int = Field(description=_VERSION_DESC)
    model_type: str = Field(min_length=1, description=_MODEL_TYPE_DESC)

    @field_validator("timeframe")
    @classmethod
    def _timeframe_in_band(cls, value: str) -> str:
        validated = _validate_timeframe(value)
        if validated is None:  # pragma: no cover - unreachable: the field is required
            msg = "timeframe is required"
            raise ValueError(msg)
        return validated


class ModelIdentityOptional(BaseModel):
    """The same four, all optional — for RESPONSES and historical rows.

    "This row has no recorded model_type" is honest data, not a guess, and forcing a value here
    would fabricate one. What these still inherit is the shared type, description and band check,
    so a PRESENT timeframe is validated identically to the required variant.
    """

    symbol: str | None = Field(default=None, description=_SYMBOL_DESC)
    timeframe: str | None = Field(default=None, description=_TIMEFRAME_DESC)
    version: int | None = Field(default=None, description=_VERSION_DESC)
    model_type: str | None = Field(default=None, description=_MODEL_TYPE_DESC)

    @field_validator("timeframe")
    @classmethod
    def _timeframe_in_band(cls, value: str | None) -> str | None:
        return _validate_timeframe(value)


__all__ = ["MODEL_TIMEFRAMES", "ModelIdentity", "ModelIdentityOptional"]
