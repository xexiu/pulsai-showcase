"""The ONE certification shape: identity, windows, levers, result, lane ladder, disclosures.

C-1 of the cert-engine plan. `python -m src.cert` (C-2) emits it, and every book's cert
migrates onto it (C-6), so a reader stops guessing which of the two layouts on disk it is holding
(`capital_modes.<lane>` vs `capital_x_exit.best_by_capital_lane.<lane>.best`, which
`capital_cert_lanes` has to probe in turn).

LAYER AND PATTERN. A validated data shape -- a DTO in DDD_PATTERNS' terms -- so plain pydantic and no
entity ceremony; its one dependency points INWARD to `src.domain`, the direction the import-linter
contracts allow. Per ARCHITECTURE_PATTERNS it invokes no construction or seam pattern: not a Builder
(anti-fit "a dataclass already says it" -- a frozen model IS that), and deliberately NOT an Adapter
between the two on-disk layouts (anti-fit "two things we control that should have agreed"). It is
the agreement both layouts migrate onto.

NO NEW WIRE VOCABULARY. `role` reuses the grader's `select`/`confirm`, and nothing here reaches the
frontend yet; the one FE consumer of cert levers (`ModelGovernanceDisclosure.certLevers`) renders a
free trimmed string, so this shape cannot break it.

TWO FIELDS ARE THE CONTRACT, and both are required and checked, not merely present:

* `CertificationWindow.role` -- whether a window SELECTED the levers or CONFIRMED them. Without it
  an in-sample grid reads exactly like unseen evidence. The vocabulary is imported from
  `capital_cert_promote`, never retyped here.
* `CertificationWindow.bars` -- how much evidence the window holds. `1d lightgbm v33` was once
  graded on ELEVEN bars; an absent count cannot even reveal that.

NO STORED VERDICT. Every model forbids unknown keys, so `verdict`, `tier` or `precommit_tier` cannot
be written into a cert at any depth. A verdict on disk goes stale the moment a gate changes; C-0
measured three that the fixed engine turned from $12,815 / $26,244 / $13,404 into $0.00. The
verdict is derived at read time (plan item C-5).

REUSE-AUDIT: imports `src.domain.services.edge_lifecycle.capital_cert_promote` for the window-role
vocabulary. Considered `src/research/edge_hunt/edge_inventory_capital_shapes.CapitalLaneRow` --
not reused because `src/` may not import `scripts/`, and a TypedDict validates nothing at runtime.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: The only roles a window may declare -- the grader's own vocabulary, not a copy of it. Re-exported
#: rather than rebuilt: this module used to assemble its own frozenset from the two members, which
#: is a mirror that stays correct only until a third role exists.
from src.domain.services.edge_lifecycle.capital_cert_promote import CERT_WINDOW_ROLES

#: A window must hold at least one bar to be evidence of anything.
MIN_WINDOW_BARS: Final = 1

#: Applied to EVERY section, so a verdict cannot hide one level below the top.
_STRICT: Final = ConfigDict(extra="forbid", frozen=True)


class CertificationIdentity(BaseModel):
    """Which book this certifies, and which harness produced it."""

    model_config = _STRICT

    spec: str = Field(min_length=1)
    harness: str = Field(min_length=1)


class CertificationWindow(BaseModel):
    """One evaluated window. `role` and `bars` are the fields this whole schema exists to require."""

    model_config = _STRICT

    role: str
    start: str = Field(min_length=1)
    #: None for an open-ended confirm window, which is how every `_{split}.json` artifact was written.
    end: str | None
    bars: int = Field(ge=MIN_WINDOW_BARS)

    @field_validator("role")
    @classmethod
    def _role_is_the_graders_vocabulary(cls, role: str) -> str:
        if role not in CERT_WINDOW_ROLES:
            msg = f"role must be one of {sorted(CERT_WINDOW_ROLES)}, got {role!r}"
            raise ValueError(msg)
        return role


class CertificationLevers(BaseModel):
    """The pre-committed cell. None means the lever is off, never that it is unknown."""

    model_config = _STRICT

    lane: str = Field(min_length=1)
    exit_label: str = Field(min_length=1)
    sizing: str = Field(min_length=1)
    holding_periods: int
    dca_depth: int | None
    min_confidence_pct: float | None
    min_compound_step_pct: float | None


class CertificationResult(BaseModel):
    """The money outcome of the certified cell, beside the benchmark it has to beat."""

    model_config = _STRICT

    initial_capital: float
    final_capital: float
    #: None only when the window has no benchmark at all, which must be visible rather than zero.
    spot_bh_final: float | None
    num_trades: int
    max_drawdown: float


class LaneRung(BaseModel):
    """One lane of the ladder. A lane that liquidates condemns the LANE, never the model."""

    model_config = _STRICT

    lane: str = Field(min_length=1)
    leverage: int
    final_capital: float
    max_drawdown: float
    drawdown_basis: str = Field(min_length=1)
    liquidation_exits: int
    account_bankrupt: bool
    num_trades: int


class CertificationDisclosures(BaseModel):
    """What a reader must see before citing the result -- all required, none defaulted."""

    model_config = _STRICT

    liquidation_exits: int
    account_bankrupt: bool
    fantasy_post_ruin_trades: int
    drawdown_contradicts_capital: bool
    thin_sample: bool


class Certification(BaseModel):
    """A book's certification, with no verdict in it."""

    model_config = _STRICT

    identity: CertificationIdentity
    windows: list[CertificationWindow] = Field(min_length=1)
    levers: CertificationLevers
    result: CertificationResult
    lane_ladder: list[LaneRung] = Field(min_length=1)
    disclosures: CertificationDisclosures
