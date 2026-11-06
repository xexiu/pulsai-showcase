"""Single source of truth for capital-certification HARNESS identifiers.

An ``edge_lab/inventory_cryptobacktest/*.json`` artifact records the RESULT of a capital
certification but, until now, essentially never recorded WHICH ENGINE produced it. MEASURED
2026-08-19 across the 127 artifacts on disk: exactly 2 declare any harness identity at all --
``standing_vrp_always_capital_cert.json`` (top-level ``harness: "levered_return_book"``) and
``lowvol_apriori_xs_sleeve_cert.json`` (``harness: "strategy_sleeve_returns_cert"``, nested per
timeframe). The other 125 -- including all 92 full combinatorial certs
(``run_edge_capital_x_exit_grid.py``) and all 11 lane-only ``capital_mode_matrix`` certs -- carry
no harness at all.

That is not cosmetic. A ``levered_return_book`` lane cert (one continuous return series compounded
down leverage lanes only) is a fundamentally different measurement from the full combinatorial
cross-product cert (leverage x DCA x confidence x hold x exit x sizing): reading a lane-only
artifact as though it were the full grid overstates what was actually certified.

CENTRALISED HERE, NOT RE-DECLARED PER WRITER, because a harness identifier copy-pasted into five
files drifts the moment one of them is renamed. Each writer imports exactly the constant naming
ITS OWN engine and stamps it under the ``harness`` key; this module does not decide which cert
used which harness, it only names the values so no writer invents its own spelling.

FRONTEND CONTRACT (checked 2026-08-19, not assumed): ``apps/web/src/types/loop-history.ts``
(``HistoryCapitalCertSchema``) is the only frontend surface that mirrors a capital-cert shape, and
it is the Valibot twin of ``shape_capital_cert`` (``capital_cert_history.py``). Neither reads nor
emits a ``harness`` field, and ``v.object`` strips unrecognised keys rather than rejecting them, so
these artifact-level values never reach the frontend and this module carries no BE/FE contract.

NOTE ON A SIBLING VOCABULARY: ``src/application/services/registry_leaf_capital_harness.py``
already declares its own local ``HARNESS_LEVERED_RETURN_BOOK = "levered_return_book"`` (same
string, separate declaration) as part of a REGISTRY-LEAF ROUTING classification -- "which harness
family handles this leaf" -- which is a coarser question than "which script produced this exact
artifact". Domain-layer writers (``return_book_capital_cert.py``) cannot import that module
without inverting the domain->application dependency direction, so the two vocabularies are kept
separate on purpose rather than merged across a layering boundary.
"""

from __future__ import annotations

from typing import Final

#: `certify_return_book_lanes` (src/domain/services/edge_lifecycle/return_book_capital_cert.py)
#: and `vrp_capital_cert.py` -- one continuous per-bar return series compounded down leverage
#: lanes only (spot / perp_3x / perp_5x / perp_8x). No discrete trades, so DCA depth,
#: min-confidence, holding period and exit strategy are inapplicable by construction (see
#: `INAPPLICABLE_DISCRETE_AXES` in `return_book_capital_cert.py`).
CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK: Final[str] = "levered_return_book"

#: `risk_sized_book.certify_risk_sized_lanes` -- discrete trades (structure stop clamped to the timeframe's ATR,
#: 1R..4R take-profit ladder, breakeven) sized at a FIXED FRACTION OF CURRENT EQUITY AT RISK per trade, isolated
#: margin, down every leverage lane (owner, 2026-10-04: "$20 capital, only $2 risk ... ALL IN should be OTHER
#: case"). Distinct from `levered_return_book`, which compounds the whole account at L x every bar -- the all-in
#: case, disclosed beside this one, never instead of it.
CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK: Final[str] = "risk_sized_book"

#: `portfolio_capital_matrix.build_strategy_sleeve_capital_cert` -- pooled walk-forward OOS return
#: series for a portfolio sleeve (VT-17 / XS ridge / risk-parity combo), leverage lanes x sizing
#: sweep. Distinct from `levered_return_book`: the series is a POOLED PORTFOLIO of daily
#: rebalanced sleeve weights, not one instrument's continuous stream.
CAPITAL_CERT_HARNESS_STRATEGY_SLEEVE_RETURNS: Final[str] = "strategy_sleeve_returns_cert"

#: `capital_mode_matrix.build_capital_cert` -- discrete CryptoBacktester trades (dynamic_tpsl
#: exits) crossed over leverage lanes x sizing sweep ONLY. No DCA / confidence / hold / exit grid
#: -- the "lane-only" tier this ledger item exists to distinguish from the full combo cert.
CAPITAL_CERT_HARNESS_CAPITAL_MODE_MATRIX: Final[str] = "capital_mode_matrix"

#: `run_edge_capital_x_exit_grid.py` -- the full combinatorial cross-product: leverage x DCA
#: depth x min-confidence x holding period x exit strategy x sizing, ranked on a shared ModelSpec
#: joblib. `ml-gate-leverage-capital-cert.md` treats this as the only tier that discharges the
#: "FULL combinatorial cert" requirement.
CAPITAL_CERT_HARNESS_CAPITAL_X_EXIT_GRID: Final[str] = "capital_x_exit_grid"

#: `run_select_confirm_cert.py` -- levers PRE-COMMITTED on a select window and published on a
#: disjoint confirm window. Neither a continuous return series nor a grid over one ModelSpec: its
#: headline is a pre-commitment rather than a search result, which is the whole point of the
#: construction (see `.claude/rules/edge-hunt-loop.md`).
#:
#: Added 2026-08-27 after the undeclared-cert ratchet failed at 130/125. An audit by writer family
#: found select-confirm producing the five most recent undeclared certs, while the larger
#: `model_spec_capital_x_exit` backlog (85) is stationary and pre-dates the field entirely.
CAPITAL_CERT_HARNESS_SELECT_CONFIRM: Final[str] = "select_confirm_precommit"

#: Every recognised harness identifier -- extend this alongside a new writer, never spell one
#: inline in the writer itself.
ALL_CAPITAL_CERT_HARNESSES: Final[frozenset[str]] = frozenset(
    {
        CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK,
        CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK,
        CAPITAL_CERT_HARNESS_STRATEGY_SLEEVE_RETURNS,
        CAPITAL_CERT_HARNESS_CAPITAL_MODE_MATRIX,
        CAPITAL_CERT_HARNESS_CAPITAL_X_EXIT_GRID,
        CAPITAL_CERT_HARNESS_SELECT_CONFIRM,
    }
)

__all__ = [
    "ALL_CAPITAL_CERT_HARNESSES",
    "CAPITAL_CERT_HARNESS_CAPITAL_MODE_MATRIX",
    "CAPITAL_CERT_HARNESS_CAPITAL_X_EXIT_GRID",
    "CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK",
    "CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK",
    "CAPITAL_CERT_HARNESS_SELECT_CONFIRM",
    "CAPITAL_CERT_HARNESS_STRATEGY_SLEEVE_RETURNS",
]
