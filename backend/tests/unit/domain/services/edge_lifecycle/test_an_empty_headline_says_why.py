"""An empty headline must say WHY it is empty.

MEASURED 2026-09-02 on the deployed 1h book (`btc_usdt_1h_xgboost_3class_v15`): its cert wrote
`combo_top25: []` and every lane reported `n_valid=0, n_excluded_dd=0`. Read literally that says
"no result". The truth was the opposite of uninformative -- 9,723 cells WERE computed, and every
one of them was a single-trade cell, so the turnover floor correctly removed all of them.

Those two states are not the same fact and must not share a spelling:

  * nothing was computed          -> the run is broken / never ran
  * everything computed was thin  -> the BOOK does not trade enough to be measured
  * everything computed was ruin  -> the book trades and loses the account

The first is an infrastructure defect. The second is a verdict about the model. The third is a
KILL. Silence made the deployed 1h model's cert read as the first when it was the second, and
`.claude/rules/` already records the inverse error costing a real model: `1d lightgbm v32` was
KILLED on a headline of "zero valid cells" while its OOS run held 4,123 survivors beating B&H 2x.

Companion to memory `silent-emptiness-reports-ok`: a stage returning ok while producing nothing
is the dominant defect; check the denominator, not the status.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.services.edge_lifecycle.capital_cert_headline import (
    EMPTY_ALL_RUINED,
    EMPTY_ALL_THIN,
    EMPTY_NO_CELLS,
    headline_empty_reason,
)
from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE

_FAT = MIN_TRADES_FOR_SHARPE + 5


def _cell(**over: Any) -> dict[str, Any]:
    """A measurable, liquidation-clean cell. Overrides make it thin or ruined."""
    base: dict[str, Any] = {
        "num_trades": _FAT,
        "liquidation_exits": 0,
        "account_bankrupt": False,
        "max_drawdown": -0.1,
        "final_capital": 12_000.0,
    }
    base.update(over)
    return base


class TestAMeasurableCellMeansNoReason:
    def test_one_fat_clean_cell_is_not_empty(self) -> None:
        assert headline_empty_reason([_cell()]) is None

    def test_a_fat_clean_cell_survives_thin_and_ruined_siblings(self) -> None:
        cells = [_cell(num_trades=1), _cell(liquidation_exits=3), _cell()]
        assert headline_empty_reason(cells) is None


class TestNothingComputed:
    def test_an_empty_list_reports_no_cells(self) -> None:
        assert headline_empty_reason([]) == EMPTY_NO_CELLS

    def test_none_reports_no_cells(self) -> None:
        assert headline_empty_reason(None) == EMPTY_NO_CELLS

    def test_only_malformed_rows_report_no_cells(self) -> None:
        assert headline_empty_reason(["nope", 7, None]) == EMPTY_NO_CELLS


class TestEverythingWasThin:
    def test_the_deployed_1h_shape_reports_all_thin(self) -> None:
        """9,723 cells, every one a single trade -- the case that motivated this."""
        assert headline_empty_reason([_cell(num_trades=1) for _ in range(9_723)]) == EMPTY_ALL_THIN

    def test_zero_trade_cells_are_thin_not_measurable(self) -> None:
        """A zero-trade cell ends at exactly its initial capital, so it can never lose."""
        assert headline_empty_reason([_cell(num_trades=0, final_capital=10_000.0)]) == EMPTY_ALL_THIN

    def test_an_unrecorded_trade_count_is_thin_not_adequate(self) -> None:
        cell = _cell()
        del cell["num_trades"]
        assert headline_empty_reason([cell]) == EMPTY_ALL_THIN


class TestEverythingWasRuin:
    @pytest.mark.parametrize(
        "ruin",
        [
            {"liquidation_exits": 2},
            {"account_bankrupt": True},
            {"max_drawdown": -1.0},
        ],
    )
    def test_fat_but_ruined_cells_report_all_ruined(self, ruin: dict[str, Any]) -> None:
        assert headline_empty_reason([_cell(**ruin)]) == EMPTY_ALL_RUINED


class TestThinIsReportedBeforeRuin:
    def test_a_thin_ruined_mix_reports_thin(self) -> None:
        """Thin outranks ruin: too few trades means the ruin count is not measured either.

        Calling a 1-trade liquidation "the book loses accounts" over-claims from one sample.
        """
        cells = [_cell(num_trades=1, liquidation_exits=1), _cell(num_trades=1)]
        assert headline_empty_reason(cells) == EMPTY_ALL_THIN


class TestTheReasonsAreDistinct:
    def test_no_two_reasons_share_a_spelling(self) -> None:
        assert len({EMPTY_NO_CELLS, EMPTY_ALL_THIN, EMPTY_ALL_RUINED}) == 3
