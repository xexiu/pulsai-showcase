"""Tests for the capital-cert HARNESS SoT constants (``capital_cert_harness``)."""

from __future__ import annotations

from src.shared.constants.capital_cert_harness import (
    ALL_CAPITAL_CERT_HARNESSES,
    CAPITAL_CERT_HARNESS_CAPITAL_MODE_MATRIX,
    CAPITAL_CERT_HARNESS_CAPITAL_X_EXIT_GRID,
    CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK,
    CAPITAL_CERT_HARNESS_STRATEGY_SLEEVE_RETURNS,
)

# One writer family per harness: levered_return_book, strategy_sleeve_returns_cert,
# capital_mode_matrix, capital_x_exit_grid.
# 5 since 2026-08-27: `select_confirm_precommit` joined the taxonomy so the select-confirm
# writer stamps which engine produced its cert, like every other writer.
# 6 since 2026-10-08 (P1-0): `risk_sized_book`, the door's risk-sized lane ladder -- stamped on the cell's
# risk_sized_cert and on the money decision's in-memory publish; no on-disk artifact carries it yet, and
# `cert_artifact_supports_production_promote` fails CLOSED on it until one does.
# Pinned so a harness is ADDED deliberately rather than as a side effect.
EXPECTED_HARNESS_COUNT = 6


def test_all_harnesses_is_complete_and_deduplicated() -> None:
    """Every value distinct -> a copy-paste duplicate would shrink the set."""
    assert len(ALL_CAPITAL_CERT_HARNESSES) == EXPECTED_HARNESS_COUNT


def test_levered_return_book_matches_the_one_precedent_on_disk() -> None:
    """The single existing on-disk declaration (`standing_vrp_always_capital_cert.json`)."""
    assert CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK == "levered_return_book"
    assert CAPITAL_CERT_HARNESS_LEVERED_RETURN_BOOK in ALL_CAPITAL_CERT_HARNESSES


def test_strategy_sleeve_returns_matches_the_one_precedent_on_disk() -> None:
    """The single existing on-disk declaration (`lowvol_apriori_xs_sleeve_cert.json`)."""
    assert CAPITAL_CERT_HARNESS_STRATEGY_SLEEVE_RETURNS == "strategy_sleeve_returns_cert"
    assert CAPITAL_CERT_HARNESS_STRATEGY_SLEEVE_RETURNS in ALL_CAPITAL_CERT_HARNESSES


def test_the_two_grid_depth_harnesses_are_distinct() -> None:
    """Lane-only and full-combinatorial must never collapse to the same value.

    That distinction is the whole point of this module: reading a lane-only cert as the full
    leverage x DCA x confidence x hold x exit x sizing grid overstates what was certified.
    """
    assert CAPITAL_CERT_HARNESS_CAPITAL_MODE_MATRIX != CAPITAL_CERT_HARNESS_CAPITAL_X_EXIT_GRID
    assert CAPITAL_CERT_HARNESS_CAPITAL_MODE_MATRIX in ALL_CAPITAL_CERT_HARNESSES
    assert CAPITAL_CERT_HARNESS_CAPITAL_X_EXIT_GRID in ALL_CAPITAL_CERT_HARNESSES
